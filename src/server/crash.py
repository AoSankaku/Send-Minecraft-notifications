"""Watch trusted server crash signals and manage crash notifications/uploads."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
import heapq
import os
from pathlib import Path
import re
import stat
import time
from typing import Any

import psutil

from message.log_upload import LogUploadError, MAX_UPLOAD_BYTES, MclogsUploader


CRASH_REPORT_STABLE_SECONDS = 1.0
PROCESS_EXIT_GRACE_SECONDS = 2.0
UPLOAD_FALLBACK_DELAY_SECONDS = 5.0
REPORT_READINESS_GRACE_SECONDS = 5.0
MAX_TRACKED_REPORTS = 512
MAX_PENDING_UPLOADS = 2

_COLORS = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|§[0-9a-fk-orx]", re.IGNORECASE)
_HEADER = re.compile(
    r"^\[[^\]\r\n]+\]\s+\[(?P<thread>[^/\]\r\n]+)/"
    r"(?P<level>INFO|ERROR|FATAL)\](?:\s+\[(?P<logger>[^\]\r\n]+)\])?:\s*"
    r"(?P<body>[\s\S]*)$",
    re.IGNORECASE,
)
_SERVER_THREADS = {"server thread", "server watchdog", "main"}
_SERVER_CRASH_MARKERS = (
    "encountered an unexpected exception",
    "exception caught during server tick",
    "considering it to be crashed, server will forcibly shutdown",
    "this crash report has been saved to:",
    "preparing crash report with uuid",
    "a fatal error has been detected by the java runtime environment",
)
_SERVER_START_FAILURE = re.compile(
    r"^(?:failed to start (?:(?:the )?minecraft |the )?server|server startup failed)\b",
    re.IGNORECASE,
)
_DEDICATED_SERVER_LOGGER = re.compile(
    r"(?:dedicatedserver|net\.minecraft\.server(?:[./]|$)|serverlifecyclehooks)",
    re.IGNORECASE,
)
_SERVER_MOD_LOADER_LOGGER = re.compile(
    r"^(?:(?:net\.minecraftforge|net\.neoforged\.neoforge)\.server\.loading\.ServerModLoader"
    r"|(?:forge|neoforge)/ServerModLoader)(?:/[^\r\n]*)?$",
    re.IGNORECASE,
)
_SERVER_MOD_LOADER_FAILURES = ("crash report saved to", "failed to save crash report")
_FABRIC_BOOT = re.compile(r"^Loading Minecraft \S+ with Fabric Loader \S+(?:\s|$)")
_FABRIC_LOGGER = re.compile(r"^FabricLoader(?:/[^\r\n]*)?$", re.IGNORECASE)
_MOD_LAUNCHER_LOGGER = re.compile(
    r"^(?:cpw\.mods\.modlauncher\.Launcher|modlauncher/Launcher)(?:/[^\r\n]*)?$",
    re.IGNORECASE,
)
_SERVER_LAUNCH_TARGET = re.compile(
    r"(?:^|[\[,\s])--launchTarget(?:,\s*|=|\s+)(?:forge|neoforge|fml)server(?=[,\s\]])"
)
_LEGACY_SERVER_TWEAKER = re.compile(
    r"^Loading tweak class name (?:net\.minecraftforge\.fml|cpw\.mods\.fml)"
    r"\.common\.launcher\.FMLServerTweaker$"
)
_REPORT_NAME = re.compile(r"^crash-.+-(?P<kind>server|fml)\.txt$", re.IGNORECASE)
_REPORT_HEADER = "---- minecraft crash report ----"
_FML_SERVER_EVIDENCE = re.compile(
    r"(?im)^(?:Thread:\s*(?:Server thread|Server Watchdog)\s*|"
    r"(?:Server type|Type):\s*Dedicated Server\s*)$"
)
_FML_CLIENT_EVIDENCE = re.compile(
    r"(?im)^(?:Thread:\s*(?:Render thread|Client thread)\s*|"
    r"(?:Server type|Type):\s*(?:Client|Integrated Server)\s*)$"
)


def _record(line: str) -> re.Match[str] | None:
    return _HEADER.fullmatch(_COLORS.sub("", line).strip("\r\n\ufeff"))


def _starts_with_marker(body: str, markers: Iterable[str]) -> bool:
    return any(
        body.startswith(marker)
        and (len(body) == len(marker) or not body[len(marker)].isalnum())
        for marker in markers
    )


def is_server_crash_record(line: str) -> bool:
    """Return true only for a specific fatal record on a server-side thread."""
    match = _record(line)
    if match is None or match["level"].casefold() not in {"error", "fatal"}:
        return False
    body = match["body"].casefold()
    thread = match["thread"].strip().casefold()
    if thread not in _SERVER_THREADS:
        return False
    if _SERVER_START_FAILURE.match(body):
        return True
    if thread == "main":
        logger = match["logger"] or ""
        if _SERVER_MOD_LOADER_LOGGER.fullmatch(logger):
            return _starts_with_marker(body, _SERVER_MOD_LOADER_FAILURES)
        dedicated_logger = bool(
            logger and _DEDICATED_SERVER_LOGGER.search(logger)
        )
        return (
            dedicated_logger and _starts_with_marker(body, _SERVER_CRASH_MARKERS)
        )
    return _starts_with_marker(body, _SERVER_CRASH_MARKERS)


def is_server_start_record(line: str) -> bool:
    """Recognize a new loader/server boot, including failures before readiness."""
    match = _record(line)
    if match is None or match["level"].casefold() != "info":
        return False
    body = match["body"]
    thread = match["thread"].strip().casefold()
    if thread == "server thread":
        return bool(re.match(r"^Starting minecraft server version\b", body, re.IGNORECASE))
    if thread != "main":
        return False
    logger = match["logger"] or ""
    # Fabric's boot record is shared with clients. It only resets incident
    # deduplication; it does not establish evidence of a server crash.
    if (not logger or _FABRIC_LOGGER.fullmatch(logger)) and _FABRIC_BOOT.match(body):
        return True
    if _MOD_LAUNCHER_LOGGER.fullmatch(logger):
        return body.startswith("ModLauncher running: args [") and bool(
            _SERVER_LAUNCH_TARGET.search(body)
        )
    if logger.casefold() in {"launchwrapper", "net.minecraft.launchwrapper.launch"}:
        return _LEGACY_SERVER_TWEAKER.fullmatch(body) is not None
    return False


def _path_signature(file_stat: os.stat_result) -> tuple[int, int, int, int]:
    return (file_stat.st_dev, file_stat.st_ino, file_stat.st_size, file_stat.st_mtime_ns)


def _is_link_or_junction(candidate: Path) -> bool:
    try:
        return candidate.is_symlink() or bool(getattr(os.path, "isjunction", lambda _p: False)(candidate))
    except OSError:
        return True


class _ProcessMonitor:
    """Track the configured process identity without owning or killing it."""

    def __init__(self, pid: int):
        self.pid = pid
        self.process: psutil.Process | None = None
        self.create_time: float | None = None
        self.ever_running = False
        self.exited_at: float | None = None
        self.exit_consumed = False
        if pid:
            self._attach()

    @staticmethod
    def _ended(process: psutil.Process) -> bool:
        try:
            if not process.is_running():
                return True
            return process.status() in {
                psutil.STATUS_ZOMBIE,
                getattr(psutil, "STATUS_DEAD", "dead"),
            }
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            return True
        except psutil.AccessDenied:
            # An inaccessible process is not evidence that it crashed.
            return False

    def _attach(self) -> None:
        try:
            process = psutil.Process(self.pid)
            if self._ended(process):
                return
            self.create_time = process.create_time()
            self.ever_running = True
            self.process = process
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            return
        except psutil.AccessDenied:
            return

    def poll(self, now: float) -> float | None:
        if not self.pid or self.exit_consumed:
            return None
        if self.process is None:
            self._attach()
            if self.process is None:
                return None
            return None

        process = self.process
        if self._ended(process):
            if self.exited_at is None:
                self.exited_at = now
            return self.exited_at
        try:
            if self.create_time is not None and process.create_time() != self.create_time:
                if self.exited_at is None:
                    self.exited_at = now
                return self.exited_at
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            if self.exited_at is None:
                self.exited_at = now
            return self.exited_at
        except psutil.AccessDenied:
            pass
        self.exited_at = None
        return None

    def consume_exit(self) -> None:
        self.exit_consumed = True


class CrashReporter:
    """Detect crash events, route localized notices and schedule bounded uploads."""

    def __init__(
        self,
        *,
        crash_reports_dir: Path,
        latest_log_path: Path,
        enabled: bool,
        upload_enabled: bool,
        server_pid: int,
        alert_targets: Iterable[str],
        report_targets: Iterable[str],
        crash_message: str,
        translate: Callable[[str], str | None],
        send_message: Callable[[str, Iterable[str]], Awaitable[None]],
        secrets: Iterable[str] = (),
        home_paths: Iterable[str] = (),
        uploader: MclogsUploader | None = None,
    ):
        self.crash_reports_dir = Path(crash_reports_dir)
        self.latest_log_path = Path(latest_log_path)
        self.enabled = enabled
        self.upload_enabled = upload_enabled
        self.alert_targets = tuple(alert_targets)
        self.report_targets = tuple(report_targets)
        self.crash_message = crash_message.strip()
        self.translate = translate
        self.send_message = send_message
        self.secrets = tuple(secrets)
        self.home_paths = tuple(home_paths)
        self.uploader = uploader or MclogsUploader(
            secrets=self.secrets,
            home_paths=self.home_paths,
        )

        self.has_crashed = False
        self.graceful_stop = False
        self._incident_started_at: float | None = None
        self._fallback_uploaded = False
        self._uploaded_reports: set[Path] = set()
        self._pending_report = False
        self._pending_report_since: float | None = None
        self._pending_upload_queue = False
        self._closed = False
        self._tasks: set[asyncio.Task[Any]] = set()
        self._alert_tasks: set[asyncio.Task[Any]] = set()
        self._upload_tasks: set[asyncio.Task[Any]] = set()
        self._pid_monitor = _ProcessMonitor(server_pid)
        self._report_signatures: dict[
            Path, tuple[tuple[int, int, int, int], float | None, str]
        ] = {}
        self._baseline_report_signatures: dict[str, tuple[int, int, int, int]] = {}
        self._initial_report_signatures: dict[str, tuple[int, int, int, int]] = {}
        self._suppressed_report_names: set[str] = set()
        self._initialize_report_baseline()

    def _reports_root(self) -> Path | None:
        root = self.crash_reports_dir
        if _is_link_or_junction(root):
            return None
        try:
            resolved = root.resolve(strict=True)
            if _is_link_or_junction(resolved) or not resolved.is_dir():
                return None
            return resolved
        except OSError:
            return None

    def _server_report_paths(self) -> list[Path]:
        root = self.crash_reports_dir
        if self._reports_root() is None:
            return []

        def recent_paths():
            try:
                with os.scandir(root) as entries:
                    for entry in entries:
                        if not _REPORT_NAME.fullmatch(entry.name):
                            continue
                        try:
                            file_stat = entry.stat(follow_symlinks=False)
                        except OSError:
                            continue
                        if stat.S_ISREG(file_stat.st_mode):
                            yield (file_stat.st_mtime_ns, entry.name.casefold(), Path(entry.path))
            except OSError:
                return

        newest = heapq.nlargest(MAX_TRACKED_REPORTS, recent_paths())
        return [item[2] for item in newest]

    def _file_info(self, candidate: Path) -> os.stat_result | None:
        try:
            root = self._reports_root()
            if root is None:
                return None
            parent = candidate.parent.resolve(strict=True)
            if parent != root or _is_link_or_junction(candidate):
                return None
            info = candidate.lstat()
            if not stat.S_ISREG(info.st_mode):
                return None
            return info
        except OSError:
            return None

    def _initialize_report_baseline(self) -> None:
        self._snapshot_report_baseline(suppress_alerts=False, initial=True)

    def _snapshot_report_baseline(
        self,
        *,
        suppress_alerts: bool,
        now: float | None = None,
        initial: bool = False,
    ) -> None:
        root = self._reports_root()
        if root is None:
            return
        current_time = time.monotonic() if now is None else now
        present: dict[str, tuple[Path, tuple[int, int, int, int]]] = {}
        try:
            with os.scandir(root) as entries:
                for entry in entries:
                    if not _REPORT_NAME.fullmatch(entry.name):
                        continue
                    try:
                        report = Path(entry.path)
                        info = report.lstat()
                    except OSError:
                        continue
                    if stat.S_ISREG(info.st_mode):
                        name = entry.name.casefold()
                        signature = _path_signature(info)
                        self._baseline_report_signatures[name] = signature
                        present[name] = (report, signature)
        except OSError:
            return
        if initial:
            self._initial_report_signatures = {
                name: signature for name, (_path, signature) in present.items()
            }
        if suppress_alerts:
            self._suppressed_report_names = set(present)
        for name, (report, signature) in present.items():
            current = self._report_signatures.get(report)
            if current is None:
                if (
                    not initial
                    and self._initial_report_signatures.get(name) != signature
                ):
                    self._report_signatures[report] = (signature, current_time, "new")
                    self._pending_report = True
                else:
                    self._report_signatures[report] = (signature, None, "baseline")
            elif current[2] == "baseline":
                if (
                    not initial
                    and self._initial_report_signatures.get(name) != signature
                ):
                    self._report_signatures[report] = (signature, current_time, "new")
                    self._pending_report = True
                else:
                    self._report_signatures[report] = (signature, None, "baseline")
            elif current[2] == "new":
                self._pending_report = True
                if current[0] != signature:
                    self._report_signatures[report] = (signature, current_time, "new")
        if self._pending_report and self._pending_report_since is None:
            self._pending_report_since = current_time

    def _read_stable_report(
        self,
        path: Path,
        expected_signature: tuple[int, int, int, int],
    ) -> str | None:
        info = self._file_info(path)
        if info is None or _path_signature(info) != expected_signature:
            return None
        try:
            with path.open("rb") as report:
                opened = os.fstat(report.fileno())
                after_lstat = path.lstat()
                if (
                    stat.S_ISLNK(after_lstat.st_mode)
                    or not stat.S_ISREG(opened.st_mode)
                    or _path_signature(opened) != expected_signature
                    or _path_signature(after_lstat) != expected_signature
                ):
                    return None
                raw = report.read(MAX_UPLOAD_BYTES + 1)
        except OSError:
            return None
        text = raw.decode("utf-8", errors="replace")
        if not raw or not text.lstrip("\ufeff\r\n").casefold().startswith(_REPORT_HEADER):
            return None
        name_match = _REPORT_NAME.fullmatch(path.name)
        if (
            name_match is not None
            and name_match["kind"].casefold() == "fml"
            and (
                _FML_CLIENT_EVIDENCE.search(text) is not None
                or _FML_SERVER_EVIDENCE.search(text) is None
            )
        ):
            return None
        return text

    def observe_line(self, line: str, *, now: float | None = None) -> bool:
        """Record fatal log evidence once; return whether the line was evidence."""
        if self._closed or not self.enabled or not is_server_crash_record(line):
            return False
        self._start_incident(time.monotonic() if now is None else now)
        return True

    def on_clean_stop(self) -> None:
        self.graceful_stop = True

    def on_server_start(self, *, now: float | None = None) -> None:
        """A parsed server-ready event starts a fresh incident generation."""
        current = time.monotonic() if now is None else now
        self.has_crashed = False
        self.graceful_stop = False
        self._incident_started_at = None
        self._fallback_uploaded = False
        self._pending_report = False
        self._pending_report_since = None
        self._pending_upload_queue = False
        self._snapshot_report_baseline(suppress_alerts=True, now=current)
        exited_at = self._pid_monitor.poll(current)
        if exited_at is not None:
            # This PID identifies the old JVM. Do not attach to a later process
            # that happens to reuse it; operators update SERVER_PID explicitly.
            self._pid_monitor.consume_exit()

    def _start_incident(self, now: float) -> bool:
        if self.has_crashed:
            return False
        self.has_crashed = True
        self.graceful_stop = False
        self._incident_started_at = now
        self._fallback_uploaded = False
        message = self.crash_message or self.translate("on_server_crash") or (
            "The server crashed and terminated unexpectedly."
        )
        self._schedule(self._safe_send(message, self.alert_targets), alert=True)
        return True

    async def _safe_send(self, message: str, targets: Iterable[str]) -> None:
        try:
            await self.send_message(message, targets)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Do not log messages, webhook URLs, or remote API error bodies.
            return

    def _schedule(
        self,
        coroutine: Awaitable[Any],
        *,
        alert: bool = False,
        upload: bool = False,
    ) -> None:
        if self._closed:
            if hasattr(coroutine, "close"):
                coroutine.close()
            return
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        if alert:
            self._alert_tasks.add(task)
        if upload:
            self._upload_tasks.add(task)

        def discard(done_task):
            self._tasks.discard(done_task)
            self._alert_tasks.discard(done_task)
            self._upload_tasks.discard(done_task)

        task.add_done_callback(discard)

    async def _send_uploaded_link(self, url: str) -> None:
        template = self.translate("on_crash_report_uploaded") or "Crash report: %crash-url%"
        message = template.replace("%crash-url%", url)
        await self._safe_send(message, self.report_targets)

    async def _send_upload_failure(self) -> None:
        message = self.translate("on_crash_report_failed") or (
            "The crash report could not be uploaded to mclo.gs."
        )
        await self._safe_send(message, self.report_targets)

    async def _upload(self, text: str) -> None:
        try:
            url = await self.uploader.upload(text, source="Send-Minecraft-notifications")
        except asyncio.CancelledError:
            raise
        except LogUploadError:
            await self._send_upload_failure()
        except Exception:
            # The uploader is also a test and extension seam; keep failures safe.
            await self._send_upload_failure()
        else:
            await self._send_uploaded_link(url)

    def _track_report(
        self,
        path: Path,
        signature: tuple[int, int, int, int],
        now: float,
    ) -> tuple[bool, str | None]:
        if path in self._uploaded_reports:
            return False, None
        if path not in self._report_signatures:
            baseline = self._baseline_report_signatures.get(path.name.casefold())
            if baseline == signature:
                self._report_signatures[path] = (signature, None, "baseline")
                return False, None
            self._report_signatures[path] = (signature, now, "new")
            self._pending_report = True
            return False, None

        old_signature, first_seen, status = self._report_signatures[path]
        if status == "baseline":
            if old_signature == signature:
                return False, None
            self._report_signatures[path] = (signature, now, "new")
            self._pending_report = True
            return False, None
        if old_signature != signature:
            self._report_signatures[path] = (signature, now, "new")
            self._pending_report = True
            return False, None
        if status == "new":
            if first_seen is None or now - first_seen < CRASH_REPORT_STABLE_SECONDS:
                self._pending_report = True
                return False, None

        text = self._read_stable_report(path, signature)
        if text is None:
            self._pending_report = True
            return False, None
        self._report_signatures[path] = (signature, first_seen, "ready")
        return True, text

    def _poll_reports(self, now: float) -> tuple[int, bool]:
        alerts = 0
        found_report = False
        self._pending_report = False
        self._pending_upload_queue = False
        reports = self._server_report_paths()
        current_paths = set(reports)
        for stale_path in set(self._report_signatures) - current_paths:
            self._report_signatures.pop(stale_path, None)
            self._uploaded_reports.discard(stale_path)
        for report in reports:
            info = self._file_info(report)
            if info is None:
                continue
            report_ready, text = self._track_report(report, _path_signature(info), now)
            state = self._report_signatures.get(report)
            if (
                state is not None
                and state[2] == "ready"
                and report not in self._uploaded_reports
            ):
                found_report = True
            if not report_ready:
                continue
            if (
                report.name.casefold() not in self._suppressed_report_names
                and self._start_incident(now)
            ):
                alerts += 1
            if not self.upload_enabled:
                self._uploaded_reports.add(report)
                continue
            if len(self._upload_tasks) >= MAX_PENDING_UPLOADS:
                self._pending_report = True
                self._pending_upload_queue = True
                continue
            self._uploaded_reports.add(report)
            # A real report has been selected for sharing; don't also upload
            # the less useful latest.log tail after the grace interval.
            self._fallback_uploaded = True
            self._schedule(self._upload(text), upload=True)
        if self._pending_report:
            if self._pending_report_since is None:
                self._pending_report_since = now
        else:
            self._pending_report_since = None
        return alerts, found_report

    def _read_log_tail(self) -> str | None:
        path = self.latest_log_path
        try:
            if path.is_symlink() or not path.is_file():
                return None
            info = path.stat()
            if not stat.S_ISREG(info.st_mode):
                return None
            with path.open("rb") as log_file:
                opened = os.fstat(log_file.fileno())
                after_stat = path.lstat()
                if (
                    stat.S_ISLNK(after_stat.st_mode)
                    or not stat.S_ISREG(opened.st_mode)
                    or _path_signature(opened) != _path_signature(after_stat)
                ):
                    return None
                if opened.st_size > MAX_UPLOAD_BYTES:
                    log_file.seek(-MAX_UPLOAD_BYTES, os.SEEK_END)
                raw = log_file.read(MAX_UPLOAD_BYTES + 1)
        except OSError:
            return None
        return raw.decode("utf-8", errors="replace")

    def _upload_fallback_if_due(self, now: float, report_found: bool) -> None:
        if (
            not self.upload_enabled
            or not self.has_crashed
            or self._incident_started_at is None
            or self._fallback_uploaded
            or report_found
            or self._pending_upload_queue
            or len(self._upload_tasks) >= MAX_PENDING_UPLOADS
        ):
            return
        fallback_due_at = self._incident_started_at + UPLOAD_FALLBACK_DELAY_SECONDS
        if self._pending_report_since is not None:
            fallback_due_at = max(
                fallback_due_at,
                self._pending_report_since + REPORT_READINESS_GRACE_SECONDS,
            )
        if now < fallback_due_at:
            return
        text = self._read_log_tail()
        self._fallback_uploaded = True
        if text:
            self._schedule(self._upload(text), upload=True)

    async def poll(self, *, now: float | None = None) -> int:
        if self._closed or not self.enabled:
            return 0
        current = time.monotonic() if now is None else now
        alerts, report_found = self._poll_reports(current)

        exited_at = self._pid_monitor.poll(current)
        if exited_at is not None:
            if self.graceful_stop:
                self._pid_monitor.consume_exit()
            elif current - exited_at >= PROCESS_EXIT_GRACE_SECONDS:
                self._pid_monitor.consume_exit()
                if self._start_incident(current):
                    alerts += 1

        self._upload_fallback_if_due(current, report_found)
        return alerts

    async def drain(self) -> None:
        """Wait for scheduled notice/upload work; designed for deterministic tests."""
        while self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)

    async def drain_alerts(self) -> None:
        """Wait for crash notices without waiting for any report upload."""
        while self._alert_tasks:
            await asyncio.gather(*tuple(self._alert_tasks), return_exceptions=True)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        try:
            await self.uploader.close()
        except Exception:
            return
