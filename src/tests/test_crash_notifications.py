"""Offline integration tests for server-crash detection and notification routing."""

import asyncio
from pathlib import Path

import pytest

from handlers.secrets import BotEnv
from main import cli
from message.constant import EventIds
from message.i18n import I18n
from message.locales import SUPPORTED_LOCALES
from server.server import Server


WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/" + "main-token-" * 6
ADMIN_WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/" + "admin-token-" * 6


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in BotEnv:
        monkeypatch.delenv(name.value, raising=False)


class RecordingUploader:
    instances = []
    failure = None

    def __init__(self, *args, **kwargs):
        self.uploaded_contents = []
        self.closed = False
        type(self).instances.append(self)

    async def upload(self, content, *, source=None):
        self.uploaded_contents.append(content)
        if type(self).failure is not None:
            raise type(self).failure
        return "https://mclo.gs/Cr4sh1"

    async def close(self):
        self.closed = True


class RecordingWebhook:
    def __init__(self, url, *args, **kwargs):
        self.url = url
        self.players = []
        self.system = []
        self.closed = False

    async def sendPlayerMessage(self, message, player):
        self.players.append((message, player))

    async def sendServerMessage(self, message):
        self.system.append(message)

    async def onClose(self):
        self.closed = True


def make_server(tmp_path, monkeypatch, *, extra="", locale="ja", upload=False, uploader_class=RecordingUploader):
    config = tmp_path / "config.toml"
    config.write_text(
        f'WEBHOOK_URL = "{WEBHOOK}"\n'
        f'LANGUAGE = "{locale}"\n'
        'TARGET_DIR = "./server-logs"\n'
        'CRASH_REPORTS_DIR = "./crash-reports"\n'
        f'CRASH_REPORT_UPLOAD_ENABLED = {str(upload).lower()}\n'
        + extra,
        encoding="utf-8",
    )
    webhooks = {}

    def webhook_factory(url, *args, **kwargs):
        webhooks[url] = RecordingWebhook(url)
        return webhooks[url]

    monkeypatch.setattr("server.server.DiscordWebhook", webhook_factory)
    import importlib

    try:
        crash_module = importlib.import_module("server.crash")
    except ModuleNotFoundError:
        crash_module = None
    if crash_module is not None:
        monkeypatch.setattr(crash_module, "MclogsUploader", uploader_class)
    RecordingUploader.instances.clear()
    RecordingUploader.failure = None
    server = Server()
    server.init(config)
    return server, webhooks


def crash_message_count(webhook):
    return sum(
        "異常終了" in message or "crashed unexpectedly" in message.lower()
        for message in webhook.system
    )


def test_server_fatal_is_notified_once_stop_is_suppressed_and_next_start_resets(
    tmp_path, monkeypatch
):
    server, webhooks = make_server(tmp_path, monkeypatch)

    async def exercise():
        try:
            main = webhooks[WEBHOOK]
            await server.on_line_added(
                "[27Oct2026 10:00:00.000] [Server thread/ERROR] "
                "[net.minecraft.server.MinecraftServer/]: Encountered an unexpected exception"
            )
            await server.on_line_added(
                "[27Oct2026 10:00:00.010] [Server Watchdog/FATAL]: "
                "Considering it to be crashed, server will forcibly shutdown."
            )
            await server.on_line_added(
                "[27Oct2026 10:00:00.020] [Server thread/ERROR] "
                "[net.minecraft.server.MinecraftServer/]: This crash report has been saved"
            )
            assert crash_message_count(main) == 1

            await server.on_line_added(
                "[27Oct2026 10:00:01.000] [Server thread/INFO] "
                "[net.minecraft.server.MinecraftServer/]: Stopping the server"
            )
            assert crash_message_count(main) == 1
            assert not any("オフライン" in message or "shutting down" in message.lower() for message in main.system)

            await server.on_line_added(
                '[27Oct2026 10:01:00.000] [Server thread/INFO] '
                '[net.minecraft.server.dedicated.DedicatedServer/]: Done (3.0s)! For help, type "help"'
            )
            await server.on_line_added(
                "[27Oct2026 10:02:00.000] [Server thread/ERROR] "
                "[net.minecraft.server.MinecraftServer/]: Encountered an unexpected exception"
            )
            assert crash_message_count(main) == 2
        finally:
            await server.shutdown()

    asyncio.run(exercise())
    assert all(webhook.closed for webhook in webhooks.values())


@pytest.mark.parametrize("record", [
    "[27Oct2026 10:00:00.000] [Server thread/ERROR] [net.minecraft.server.MinecraftServer/]: Encountered an unexpected exception",
    "[27Oct2026 10:00:00.000] [Server thread/FATAL]: Failed to start the minecraft server",
    "[10:00:00] [main/FATAL] [minecraft/Main]: Failed to start the minecraft server",
    "[27Oct2026 10:00:00.000] [Server Watchdog/FATAL]: Considering it to be crashed, server will forcibly shutdown.",
])
def test_supported_server_crash_records_trigger_alert(tmp_path, monkeypatch, record):
    server, webhooks = make_server(tmp_path, monkeypatch)

    async def exercise():
        try:
            await server.on_line_added(record)
            assert crash_message_count(webhooks[WEBHOOK]) == 1
        finally:
            await server.shutdown()

    asyncio.run(exercise())


@pytest.mark.parametrize("record", [
    "[27Oct2026 10:00:00.000] [Server thread/ERROR] [examplemod/]: Could not load an optional recipe",
    "[27Oct2026 10:00:00.000] [Render thread/ERROR] [net.minecraft.client.Minecraft/]: Unreported exception thrown!",
    "[27Oct2026 10:00:00.001] [Render thread/FATAL] [net.neoforged.neoforge.common.NeoForgeMod/]: Preparing crash report with UUID 00000000-0000-0000-0000-000000000000",
    "[27Oct2026 10:00:00.001] [main/FATAL] [net.neoforged.neoforge.common.NeoForgeMod/]: Preparing crash report with UUID 00000000-0000-0000-0000-000000000000",
    "[27Oct2026 10:00:00.002] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: <Alice> I crashed the server",
    "[27Oct2026 10:00:00.003] [Server thread/ERROR] [examplemod/]: Stack includes net.minecraft.server.dedicated.ServerWatchdog",
])
def test_generic_errors_chat_and_client_crash_records_do_not_claim_server_crashed(
    tmp_path, monkeypatch, record
):
    server, webhooks = make_server(tmp_path, monkeypatch)

    async def exercise():
        try:
            await server.on_line_added(record)
            assert crash_message_count(webhooks[WEBHOOK]) == 0
            assert not getattr(getattr(server, "crash_reporter", None), "has_crashed", False)
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_trusted_server_boot_record_resets_incident_before_ready_but_chat_does_not(
    tmp_path, monkeypatch
):
    server, webhooks = make_server(tmp_path, monkeypatch)

    async def exercise():
        try:
            fatal = (
                "[27Oct2026 10:00:00.000] [Server thread/ERROR] "
                "[net.minecraft.server.MinecraftServer/]: Encountered an unexpected exception"
            )
            await server.on_line_added(fatal)
            await server.on_line_added(
                "[27Oct2026 10:01:00.000] [Server thread/INFO] "
                "[net.minecraft.server.MinecraftServer/]: <Alice> Starting minecraft server version 1.21.10"
            )
            await server.on_line_added(fatal)
            assert crash_message_count(webhooks[WEBHOOK]) == 1

            await server.on_line_added(
                "[27Oct2026 10:02:00.000] [Server thread/INFO] "
                "[net.minecraft.server.MinecraftServer/]: Starting minecraft server version 1.21.10"
            )
            await server.on_line_added(fatal)
            assert crash_message_count(webhooks[WEBHOOK]) == 2
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_report_pending_before_new_server_start_cannot_alert_new_generation(
    tmp_path, monkeypatch
):
    report_dir = tmp_path / "crash-reports"
    report_dir.mkdir()
    server, webhooks = make_server(tmp_path, monkeypatch)

    async def exercise():
        try:
            fatal = (
                "[27Oct2026 10:00:00.000] [Server thread/ERROR] "
                "[net.minecraft.server.MinecraftServer/]: Encountered an unexpected exception"
            )
            await server.on_line_added(fatal, now=100.0)
            prior_report = report_dir / "crash-2026-10-27_10.00.00-server.txt"
            prior_report.write_text(
                "---- Minecraft Crash Report ----\nDescription: old generation\n",
                encoding="utf-8",
            )
            await server.poll_crashes(now=101.0)

            await server.on_line_added(
                "[27Oct2026 10:01:00.000] [Server thread/INFO] "
                "[net.minecraft.server.MinecraftServer/]: Starting minecraft server version 1.21.10",
                now=102.0,
            )
            await server.poll_crashes(now=102.0)
            assert crash_message_count(webhooks[WEBHOOK]) == 1
            assert not server.crash_reporter.has_crashed

            fresh_report = report_dir / "crash-2026-10-27_10.01.00-server.txt"
            fresh_report.write_text(
                "---- Minecraft Crash Report ----\nDescription: new generation\n",
                encoding="utf-8",
            )
            await server.poll_crashes(now=103.0)
            await server.poll_crashes(now=104.0)
            assert crash_message_count(webhooks[WEBHOOK]) == 2
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_report_created_before_new_start_without_poll_is_uploaded_without_new_alert(
    tmp_path, monkeypatch
):
    report_dir = tmp_path / "crash-reports"
    report_dir.mkdir()
    server, webhooks = make_server(tmp_path, monkeypatch, upload=True)

    async def exercise():
        try:
            await server.on_line_added(
                "[27Oct2026 10:00:00.000] [Server thread/ERROR] "
                "[net.minecraft.server.MinecraftServer/]: Encountered an unexpected exception",
                now=100.0,
            )
            report = report_dir / "crash-2026-10-27_10.00.00-server.txt"
            report.write_text(
                "---- Minecraft Crash Report ----\nDescription: previous generation\n",
                encoding="utf-8",
            )
            await server.on_line_added(
                "[27Oct2026 10:01:00.000] [Server thread/INFO] "
                "[net.minecraft.server.MinecraftServer/]: Starting minecraft server version 1.21.10",
                now=100.5,
            )

            await server.poll_crashes(now=101.0)
            await server.poll_crashes(now=102.0)
            await server.crash_reporter.drain()

            assert len(RecordingUploader.instances[0].uploaded_contents) == 1
            assert crash_message_count(webhooks[WEBHOOK]) == 1
            assert not server.crash_reporter.has_crashed
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_only_new_stable_server_report_is_alerted_once_and_old_client_report_is_ignored(
    tmp_path, monkeypatch
):
    report_dir = tmp_path / "crash-reports"
    report_dir.mkdir()
    old = report_dir / "crash-2026-10-01_00.00.00-server.txt"
    old.write_text("---- Minecraft Crash Report ----\n", encoding="utf-8")
    client = report_dir / "crash-2026-10-01_00.00.01-client.txt"
    client.write_text("---- Minecraft Crash Report ----\n", encoding="utf-8")
    server, webhooks = make_server(tmp_path, monkeypatch)

    async def exercise():
        try:
            assert await server.poll_crashes(now=100.0) == 0
            assert crash_message_count(webhooks[WEBHOOK]) == 0

            fresh = report_dir / "crash-2026-10-27_10.00.00-server.txt"
            fresh.write_text(
                "---- Minecraft Crash Report ----\nDescription: Server tick loop\n",
                encoding="utf-8",
            )
            assert await server.poll_crashes(now=101.0) == 0
            assert crash_message_count(webhooks[WEBHOOK]) == 0
            assert await server.poll_crashes(now=102.0) == 1
            assert crash_message_count(webhooks[WEBHOOK]) == 1
            assert await server.poll_crashes(now=103.0) == 0
            assert crash_message_count(webhooks[WEBHOOK]) == 1
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_incomplete_crash_report_is_retried_when_content_arrives(tmp_path, monkeypatch):
    report_dir = tmp_path / "crash-reports"
    report_dir.mkdir()
    server, webhooks = make_server(tmp_path, monkeypatch)

    async def exercise():
        try:
            incomplete = report_dir / "crash-2026-10-27_10.00.00-server.txt"
            incomplete.write_text("", encoding="utf-8")
            assert await server.poll_crashes(now=10.0) == 0
            assert crash_message_count(webhooks[WEBHOOK]) == 0
            incomplete.write_text(
                "---- Minecraft Crash Report ----\nDescription: Server tick loop\n",
                encoding="utf-8",
            )
            assert await server.poll_crashes(now=11.0) == 0
            assert crash_message_count(webhooks[WEBHOOK]) == 0
            assert await server.poll_crashes(now=12.0) == 1
            assert crash_message_count(webhooks[WEBHOOK]) == 1
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_missing_crash_report_directory_is_created_later_without_stopping_monitoring(
    tmp_path, monkeypatch
):
    report_dir = tmp_path / "crash-reports"
    server, webhooks = make_server(tmp_path, monkeypatch)

    async def exercise():
        try:
            assert await server.poll_crashes(now=10.0) == 0
            report_dir.mkdir()
            (report_dir / "crash-2026-10-27_10.00.00-server.txt").write_text(
                "---- Minecraft Crash Report ----\nDescription: Server tick loop\n",
                encoding="utf-8",
            )
            assert await server.poll_crashes(now=11.0) == 0
            assert await server.poll_crashes(now=12.0) == 1
            assert crash_message_count(webhooks[WEBHOOK]) == 1
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_symlinked_crash_report_is_never_opened_or_uploaded(tmp_path, monkeypatch):
    report_dir = tmp_path / "crash-reports"
    report_dir.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("---- Minecraft Crash Report ----\nDescription: private\n", encoding="utf-8")
    link = report_dir / "crash-2026-10-27_10.00.00-server.txt"
    server, webhooks = make_server(tmp_path, monkeypatch, upload=True)
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError) as error:
        asyncio.run(server.shutdown())
        pytest.skip(f"symbolic links are unavailable: {error}")

    async def exercise():
        try:
            await server.poll_crashes(now=10.0)
            await server.poll_crashes(now=11.0)
            await server.crash_reporter.drain()
            assert crash_message_count(webhooks[WEBHOOK]) == 0
            assert not any(uploader.uploaded_contents for uploader in RecordingUploader.instances)
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_symlink_check_rejects_new_report_path_independent_of_windows_link_privileges(
    tmp_path, monkeypatch
):
    report_dir = tmp_path / "crash-reports"
    report_dir.mkdir()
    report = report_dir / "crash-2026-10-27_10.00.00-server.txt"
    server, webhooks = make_server(tmp_path, monkeypatch, upload=True)
    report.write_text("---- Minecraft Crash Report ----\nDescription: private\n", encoding="utf-8")
    is_symlink = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda candidate: candidate == report or is_symlink(candidate))

    async def exercise():
        try:
            await server.poll_crashes(now=10.0)
            await server.poll_crashes(now=11.0)
            await server.crash_reporter.drain()
            assert crash_message_count(webhooks[WEBHOOK]) == 0
            assert not any(uploader.uploaded_contents for uploader in RecordingUploader.instances)
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_symlinked_crash_reports_directory_is_never_scanned(tmp_path, monkeypatch):
    report_dir = tmp_path / "crash-reports"
    report_dir.mkdir()
    server, webhooks = make_server(tmp_path, monkeypatch)
    report = report_dir / "crash-2026-10-27_10.00.00-server.txt"
    report.write_text("---- Minecraft Crash Report ----\n", encoding="utf-8")
    is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda candidate: candidate == report_dir or is_symlink(candidate),
    )

    async def exercise():
        try:
            assert await server.poll_crashes(now=10.0) == 0
            assert await server.poll_crashes(now=11.0) == 0
            assert crash_message_count(webhooks[WEBHOOK]) == 0
        finally:
            await server.shutdown()

    asyncio.run(exercise())


@pytest.mark.parametrize("targets", [
    '["main"]', '["admin"]', '["main", "admin"]',
])
def test_alert_and_report_targets_route_through_configured_channels(
    tmp_path, monkeypatch, targets
):
    server, webhooks = make_server(
        tmp_path,
        monkeypatch,
        extra=f'ADMIN_WEBHOOK_URL = "{ADMIN_WEBHOOK}"\nCRASH_ALERT_TARGETS = {targets}\n',
    )

    async def exercise():
        try:
            await server.on_line_added(
                "[27Oct2026 10:00:00.000] [Server thread/ERROR] "
                "[net.minecraft.server.MinecraftServer/]: Encountered an unexpected exception"
            )
            assert crash_message_count(webhooks[WEBHOOK]) == (0 if targets == '["admin"]' else 1)
            assert crash_message_count(webhooks[ADMIN_WEBHOOK]) == (0 if targets == '["main"]' else 1)
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_identical_main_and_admin_webhooks_receive_only_one_alert(tmp_path, monkeypatch):
    server, webhooks = make_server(
        tmp_path,
        monkeypatch,
        extra=(
            f'ADMIN_WEBHOOK_URL = "{WEBHOOK}"\n'
            'CRASH_ALERT_TARGETS = ["main", "admin"]\n'
        ),
    )

    async def exercise():
        try:
            await server.on_line_added(
                "[27Oct2026 10:00:00.000] [Server thread/ERROR] "
                "[net.minecraft.server.MinecraftServer/]: Encountered an unexpected exception"
            )
            assert crash_message_count(webhooks[WEBHOOK]) == 1
            assert len(webhooks) == 1
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_report_upload_is_opt_in_and_details_route_independently(tmp_path, monkeypatch):
    report_dir = tmp_path / "crash-reports"
    report_dir.mkdir()
    server, webhooks = make_server(
        tmp_path,
        monkeypatch,
        extra=(
            f'ADMIN_WEBHOOK_URL = "{ADMIN_WEBHOOK}"\n'
            'CRASH_ALERT_TARGETS = ["main"]\n'
            'CRASH_REPORT_TARGETS = ["admin"]\n'
        ),
        upload=True,
    )

    async def exercise():
        try:
            await server.on_line_added(
                "[27Oct2026 10:00:00.000] [Server thread/ERROR] "
                "[net.minecraft.server.MinecraftServer/]: Encountered an unexpected exception",
                now=100.0,
            )
            assert crash_message_count(webhooks[WEBHOOK]) == 1
            assert crash_message_count(webhooks[ADMIN_WEBHOOK]) == 0

            (report_dir / "crash-2026-10-27_10.00.00-server.txt").write_text(
                "---- Minecraft Crash Report ----\nDescription: Server tick loop\n",
                encoding="utf-8",
            )
            await server.poll_crashes(now=101.0)
            await server.poll_crashes(now=102.0)
            await server.crash_reporter.drain()

            assert len(RecordingUploader.instances[0].uploaded_contents) == 1
            assert any("https://mclo.gs/Cr4sh1" in message for message in webhooks[ADMIN_WEBHOOK].system)
            assert not any("https://mclo.gs/Cr4sh1" in message for message in webhooks[WEBHOOK].system)
            assert crash_message_count(webhooks[WEBHOOK]) == 1
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_default_crash_settings_send_alert_to_main_without_upload(tmp_path, monkeypatch):
    server, webhooks = make_server(tmp_path, monkeypatch)

    async def exercise():
        try:
            await server.on_line_added(
                "[27Oct2026 10:00:00.000] [Server thread/ERROR] "
                "[net.minecraft.server.MinecraftServer/]: Encountered an unexpected exception"
            )
            await server.crash_reporter.drain()
            assert crash_message_count(webhooks[WEBHOOK]) == 1
            assert not RecordingUploader.instances[0].uploaded_contents
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_upload_opt_out_and_delayed_log_tail_fallback(tmp_path, monkeypatch):
    server, webhooks = make_server(
        tmp_path,
        monkeypatch,
        upload=False,
    )

    async def exercise():
        try:
            await server.on_line_added(
                "[27Oct2026 10:00:00.000] [Server thread/ERROR] "
                "[net.minecraft.server.MinecraftServer/]: Encountered an unexpected exception",
                now=100.0,
            )
            logfile = tmp_path / "server-logs" / "latest.log"
            logfile.write_text("last useful server record\n", encoding="utf-8")
            await server.poll_crashes(now=106.0)
            await server.crash_reporter.drain()
            assert crash_message_count(webhooks[WEBHOOK]) == 1
            assert not RecordingUploader.instances[0].uploaded_contents
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_late_crash_report_gets_one_more_link_without_repeating_alert(tmp_path, monkeypatch):
    report_dir = tmp_path / "crash-reports"
    report_dir.mkdir()
    server, webhooks = make_server(tmp_path, monkeypatch, upload=True)

    async def exercise():
        try:
            logfile = tmp_path / "server-logs" / "latest.log"
            logfile.write_text("last useful server record\n", encoding="utf-8")
            await server.on_line_added(
                "[27Oct2026 10:00:00.000] [Server thread/ERROR] "
                "[net.minecraft.server.MinecraftServer/]: Encountered an unexpected exception",
                now=100.0,
            )
            await server.poll_crashes(now=106.0)
            await server.crash_reporter.drain()
            assert len(RecordingUploader.instances[0].uploaded_contents) == 1

            (report_dir / "crash-2026-10-27_10.00.00-server.txt").write_text(
                "---- Minecraft Crash Report ----\nDescription: final server report\n",
                encoding="utf-8",
            )
            await server.poll_crashes(now=107.0)
            await server.poll_crashes(now=108.0)
            await server.crash_reporter.drain()

            assert len(RecordingUploader.instances[0].uploaded_contents) == 2
            assert crash_message_count(webhooks[WEBHOOK]) == 1
            assert sum("https://mclo.gs/Cr4sh1" in message for message in webhooks[WEBHOOK].system) == 2
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_one_webhook_failure_does_not_block_other_crash_channels(tmp_path, monkeypatch):
    server, webhooks = make_server(
        tmp_path,
        monkeypatch,
        extra=(
            f'ADMIN_WEBHOOK_URL = "{ADMIN_WEBHOOK}"\n'
            'CRASH_ALERT_TARGETS = ["main", "admin"]\n'
        ),
    )

    async def fail_admin(_message):
        raise OSError("admin webhook token must not be logged")

    webhooks[ADMIN_WEBHOOK].sendServerMessage = fail_admin

    async def exercise():
        try:
            await server.on_line_added(
                "[27Oct2026 10:00:00.000] [Server thread/ERROR] "
                "[net.minecraft.server.MinecraftServer/]: Encountered an unexpected exception"
            )
            assert crash_message_count(webhooks[WEBHOOK]) == 1
            assert crash_message_count(webhooks[ADMIN_WEBHOOK]) == 0
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_upload_failure_keeps_alert_and_sends_only_safe_failure_status(tmp_path, monkeypatch):
    report_dir = tmp_path / "crash-reports"
    report_dir.mkdir()
    server, webhooks = make_server(
        tmp_path,
        monkeypatch,
        extra=(
            f'ADMIN_WEBHOOK_URL = "{ADMIN_WEBHOOK}"\n'
            'CRASH_ALERT_TARGETS = ["main"]\n'
            'CRASH_REPORT_TARGETS = ["admin"]\n'
        ),
        upload=True,
    )
    RecordingUploader.failure = RuntimeError("private token: should not appear")

    async def exercise():
        try:
            await server.on_line_added(
                "[27Oct2026 10:00:00.000] [Server thread/ERROR] "
                "[net.minecraft.server.MinecraftServer/]: Encountered an unexpected exception",
                now=100.0,
            )
            (report_dir / "crash-2026-10-27_10.00.00-server.txt").write_text(
                "---- Minecraft Crash Report ----\nDescription: Server tick loop\n",
                encoding="utf-8",
            )
            await server.poll_crashes(now=101.0)
            await server.poll_crashes(now=102.0)
            await server.crash_reporter.drain()
            assert crash_message_count(webhooks[WEBHOOK]) == 1
            assert any("upload" in message.lower() or "アップロード" in message for message in webhooks[ADMIN_WEBHOOK].system)
            assert all("private token" not in message for hook in webhooks.values() for message in hook.system)
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_optional_server_pid_exit_after_grace_is_reported_once(tmp_path, monkeypatch):
    class FakeProcess:
        def __init__(self, pid):
            self.pid = pid
            self.alive = True

        def is_running(self):
            return self.alive

        def status(self):
            return "running" if self.alive else "terminated"

        def create_time(self):
            return 1.0

    process = FakeProcess(4321)
    import importlib

    try:
        crash_module = importlib.import_module("server.crash")
    except ModuleNotFoundError:
        crash_module = None
    if crash_module is not None:
        monkeypatch.setattr(crash_module.psutil, "Process", lambda _pid: process)
    server, webhooks = make_server(
        tmp_path,
        monkeypatch,
        extra="SERVER_PID = 4321\n",
    )

    async def exercise():
        try:
            assert await server.poll_crashes(now=100.0) == 0
            process.alive = False
            assert await server.poll_crashes(now=100.5) == 0
            assert await server.poll_crashes(now=104.0) == 1
            assert await server.poll_crashes(now=105.0) == 0
            assert crash_message_count(webhooks[WEBHOOK]) == 1
            await server.on_line_added(
                "[27Oct2026 10:01:00.000] [Server thread/INFO] "
                "[net.minecraft.server.MinecraftServer/]: Starting minecraft server version 1.21.10",
                now=106.0,
            )
            assert await server.poll_crashes(now=110.0) == 0
            assert crash_message_count(webhooks[WEBHOOK]) == 1
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_configured_server_pid_clean_shutdown_does_not_report_crash(tmp_path, monkeypatch):
    class FakeProcess:
        def __init__(self, pid):
            self.pid = pid
            self.alive = True

        def is_running(self):
            return self.alive

        def status(self):
            return "running" if self.alive else "terminated"

        def create_time(self):
            return 1.0

    process = FakeProcess(4321)
    import importlib

    try:
        crash_module = importlib.import_module("server.crash")
    except ModuleNotFoundError:
        crash_module = None
    if crash_module is not None:
        monkeypatch.setattr(crash_module.psutil, "Process", lambda _pid: process)
    server, webhooks = make_server(
        tmp_path,
        monkeypatch,
        extra="SERVER_PID = 4321\n",
    )

    async def exercise():
        try:
            assert await server.poll_crashes(now=100.0) == 0
            await server.on_line_added(
                "[27Oct2026 10:00:00.000] [Server thread/INFO] "
                "[net.minecraft.server.MinecraftServer/]: Stopping the server",
                now=101.0,
            )
            process.alive = False
            assert await server.poll_crashes(now=105.0) == 0
            assert crash_message_count(webhooks[WEBHOOK]) == 0
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_quiet_file_watcher_timeout_still_polls_crash_reports(tmp_path, monkeypatch):
    server, _webhooks = make_server(tmp_path, monkeypatch)
    ticks = []

    async def no_changes(*targets, **kwargs):
        assert kwargs["yield_on_timeout"] is True
        assert kwargs["rust_timeout"] <= 1000
        ticks.append("subscribed")
        yield set()
        ticks.append("first-timeout")
        yield set()
        ticks.append("second-timeout")

    poll_calls = []

    async def poll(*, now=None):
        poll_calls.append(now)
        return 0

    monkeypatch.setattr("server.server.awatch", no_changes)
    monkeypatch.setattr(server, "poll_crashes", poll)

    async def exercise():
        try:
            await server.listen_file_change()
            assert len(poll_calls) == 2
            assert all(now is not None for now in poll_calls)
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_stalled_upload_does_not_block_player_chat_and_shutdown_cancels_it(
    tmp_path, monkeypatch
):
    class SlowUploader:
        instances = []

        def __init__(self, *args, **kwargs):
            self.started = asyncio.Event()
            self.cancelled = False
            self.closed = False
            type(self).instances.append(self)

        async def upload(self, content, *, source=None):
            self.started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                self.cancelled = True
                raise

        async def close(self):
            self.closed = True

    server, webhooks = make_server(
        tmp_path,
        monkeypatch,
        upload=True,
        uploader_class=SlowUploader,
    )

    async def exercise():
        await server.on_line_added(
            "[27Oct2026 10:00:00.000] [Server thread/ERROR] "
            "[net.minecraft.server.MinecraftServer/]: Encountered an unexpected exception",
            now=100.0,
        )
        report_dir = tmp_path / "crash-reports"
        report_dir.mkdir()
        (report_dir / "crash-2026-10-27_10.00.00-server.txt").write_text(
            "---- Minecraft Crash Report ----\nDescription: Server tick loop\n",
            encoding="utf-8",
        )
        await server.poll_crashes(now=101.0)
        await server.poll_crashes(now=102.0)
        uploader = SlowUploader.instances[0]
        try:
            await asyncio.wait_for(uploader.started.wait(), timeout=2.0)
            await server.on_line_added(
                "[27Oct2026 10:00:03.000] [Server thread/INFO]: <Alice> still playing",
                now=103.0,
            )
            assert webhooks[WEBHOOK].players == [("`still playing`", "Alice")]
        finally:
            await server.shutdown()

        assert uploader.cancelled
        assert uploader.closed

    asyncio.run(exercise())


def test_server_report_upload_suppresses_later_latest_log_fallback(tmp_path, monkeypatch):
    report_dir = tmp_path / "crash-reports"
    report_dir.mkdir()
    server, webhooks = make_server(tmp_path, monkeypatch, upload=True)

    async def exercise():
        try:
            (tmp_path / "server-logs" / "latest.log").write_text("log tail\n", encoding="utf-8")
            (report_dir / "crash-2026-10-27_10.00.00-server.txt").write_text(
                "---- Minecraft Crash Report ----\nDescription: Server tick loop\n",
                encoding="utf-8",
            )
            await server.poll_crashes(now=10.0)
            await server.poll_crashes(now=11.0)
            await server.crash_reporter.drain()
            await server.poll_crashes(now=16.0)
            await server.crash_reporter.drain()
            assert len(RecordingUploader.instances[0].uploaded_contents) == 1
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_reports_skipped_when_upload_queue_is_full_remain_eligible(tmp_path, monkeypatch):
    class GatedUploader:
        instances = []

        def __init__(self, *args, **kwargs):
            self.started_count = 0
            self.two_started = asyncio.Event()
            self.release = asyncio.Event()
            self.uploaded_contents = []
            self.closed = False
            type(self).instances.append(self)

        async def upload(self, content, *, source=None):
            self.started_count += 1
            if self.started_count >= 2:
                self.two_started.set()
            await self.release.wait()
            self.uploaded_contents.append(content)
            return "https://mclo.gs/Cr4sh1"

        async def close(self):
            self.closed = True

    report_dir = tmp_path / "crash-reports"
    report_dir.mkdir()
    server, _webhooks = make_server(
        tmp_path, monkeypatch, upload=True, uploader_class=GatedUploader
    )
    for index in range(3):
        (report_dir / f"crash-2026-10-27_10.00.0{index}-server.txt").write_text(
            f"---- Minecraft Crash Report ----\nDescription: report {index}\n",
            encoding="utf-8",
        )

    async def exercise():
        try:
            await server.poll_crashes(now=10.0)
            await server.poll_crashes(now=11.0)
            uploader = GatedUploader.instances[0]
            await uploader.two_started.wait()
            assert len(uploader.uploaded_contents) == 0
            uploader.release.set()
            await server.crash_reporter.drain()
            await server.poll_crashes(now=12.0)
            await server.crash_reporter.drain()
            assert len(uploader.uploaded_contents) == 3
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_malformed_report_does_not_block_bounded_latest_log_fallback(tmp_path, monkeypatch):
    report_dir = tmp_path / "crash-reports"
    report_dir.mkdir()
    server, _webhooks = make_server(tmp_path, monkeypatch, upload=True)

    async def exercise():
        try:
            (tmp_path / "server-logs" / "latest.log").write_text("useful tail\n", encoding="utf-8")
            await server.on_line_added(
                "[27Oct2026 10:00:00.000] [Server thread/ERROR] "
                "[net.minecraft.server.MinecraftServer/]: Encountered an unexpected exception",
                now=100.0,
            )
            (report_dir / "crash-2026-10-27_10.00.00-server.txt").write_text(
                "still being written without a report header\n", encoding="utf-8"
            )
            await server.poll_crashes(now=101.0)
            await server.poll_crashes(now=102.0)
            await server.poll_crashes(now=106.0)
            await server.crash_reporter.drain()
            assert len(RecordingUploader.instances[0].uploaded_contents) == 1
            assert "useful tail" in RecordingUploader.instances[0].uploaded_contents[0]
        finally:
            await server.shutdown()

    asyncio.run(exercise())


def test_old_reports_outside_active_window_never_replay_as_new(tmp_path, monkeypatch):
    import os

    report_dir = tmp_path / "crash-reports"
    report_dir.mkdir()
    old_reports = []
    base = 1_700_000_000_000_000_000
    for index in range(520):
        report = report_dir / f"crash-2020-01-01_00.{index:04d}-server.txt"
        report.write_text("---- Minecraft Crash Report ----\n", encoding="utf-8")
        os.utime(report, ns=(base + index * 1_000_000_000, base + index * 1_000_000_000))
        old_reports.append(report)
    server, webhooks = make_server(tmp_path, monkeypatch)

    async def exercise():
        try:
            for report in old_reports[-20:]:
                report.unlink()
            fresh = report_dir / "crash-2026-10-27_10.00.00-server.txt"
            fresh.write_text(
                "---- Minecraft Crash Report ----\nDescription: latest crash\n",
                encoding="utf-8",
            )
            await server.poll_crashes(now=10.0)
            await server.poll_crashes(now=11.0)
            assert crash_message_count(webhooks[WEBHOOK]) == 1

            # Removing the new file causes old baseline entries to enter the
            # bounded active window; they still must not replay notifications.
            fresh.unlink()
            await server.poll_crashes(now=12.0)
            await server.poll_crashes(now=13.0)
            assert crash_message_count(webhooks[WEBHOOK]) == 1
        finally:
            await server.shutdown()

    asyncio.run(exercise())


@pytest.mark.parametrize("report_text, should_alert", [
    ("---- Minecraft Crash Report ----\nDescription: Client render failure\n", False),
    (
        "---- Minecraft Crash Report ----\nThread: Render thread\n"
        "Server type: Dedicated Server\n"
        "at net.minecraft.server.dedicated.DedicatedServer.run(DedicatedServer.java:10)\n",
        False,
    ),
    (
        "---- Minecraft Crash Report ----\nThread: Server thread\n"
        "Description: Forge mod loading failure\n",
        True,
    ),
])
def test_fml_report_requires_server_evidence(tmp_path, monkeypatch, report_text, should_alert):
    report_dir = tmp_path / "crash-reports"
    report_dir.mkdir()
    server, webhooks = make_server(tmp_path, monkeypatch)

    async def exercise():
        try:
            (report_dir / "crash-2026-10-27_10.00.00-fml.txt").write_text(
                report_text, encoding="utf-8"
            )
            await server.poll_crashes(now=10.0)
            await server.poll_crashes(now=11.0)
            assert crash_message_count(webhooks[WEBHOOK]) == int(should_alert)
        finally:
            await server.shutdown()

    asyncio.run(exercise())
@pytest.mark.parametrize("setting", [
    'CRASH_ALERT_TARGETS = ["admin"]',
    'CRASH_REPORT_TARGETS = ["discord"]',
    'CRASH_ALERT_TARGETS = ["main", 7]',
    'CRASH_REPORT_UPLOAD_ENABLED = "true"',
    'ADMIN_WEBHOOK_URL = "http://discord.com/api/webhooks/123456789012345678/' + "admin-token-" * 6 + '"',
    'SERVER_PID = -1',
    'SERVER_PID = "4321"',
])
def test_invalid_crash_settings_fail_config_check(tmp_path, monkeypatch, setting, capsys):
    config = tmp_path / "invalid.toml"
    config.write_text(f'WEBHOOK_URL = "{WEBHOOK}"\n{setting}\n', encoding="utf-8")
    monkeypatch.setattr(
        "server.server.DiscordWebhook",
        lambda *_args, **_kwargs: pytest.fail("config validation must happen before webhook creation"),
    )

    assert cli(["--config", str(config), "--check-config"]) == 1
    error = capsys.readouterr().err
    setting_name = setting.split(" =", 1)[0]
    assert setting_name in error


def test_crash_catalogs_are_complete_for_every_supported_locale_and_have_safe_placeholders():
    expected = {event.value for event in EventIds if event is not EventIds.NONE}
    for locale in SUPPORTED_LOCALES:
        catalog = I18n.for_config(Path("unused-config.toml"), locale)
        assert set(catalog.lang_data[catalog.current_lang]) == expected
        assert "%crash-url%" in catalog.translate(EventIds.ON_CRASH_REPORT_UPLOADED)


def test_server_pid_is_optional_and_defaults_to_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBHOOK_URL", WEBHOOK)
    BotEnv.init(tmp_path / "missing.toml")
    assert BotEnv.ServerPid.get() == "0"

