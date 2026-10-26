"""Privacy-conscious, bounded uploads to the official mclo.gs API."""

from __future__ import annotations

import asyncio
import ipaddress
import re
from urllib.parse import urlsplit

import aiohttp


MAX_UPLOAD_BYTES = 9 * 1024 * 1024
MAX_UPLOAD_LINES = 24_000
UPLOAD_TIMEOUT_SECONDS = 10
API_URL = "https://api.mclo.gs/1/log"

_DISCORD_WEBHOOK = re.compile(
    r"https://(?:ptb\.|canary\.)?(?:discord(?:app)?\.com)/api/webhooks/"
    r"[0-9]{17,20}/[A-Za-z0-9._-]+",
    re.IGNORECASE,
)
_SECRET_ASSIGNMENT = re.compile(
    r'''(?ix)
    (?<![A-Za-z0-9_.-])
    (?P<prefix>["']?
        (?:[A-Za-z][A-Za-z0-9_.-]{0,31})?
        (?:access[_-]?token|access[_-]?key|api[_-]?key|token|password|passwd|secret|credential|session|cookie)
        ["']?\s*[:=]\s*)
    (?:
        (?P<quote>["'])(?P<quoted>[^\r\n]*?)(?P=quote)
        |(?P<bare>[^\s,;}]+)
    )
    '''
)
_AUTHORIZATION = re.compile(
    r'''(?imx)(?P<prefix>\bauthorization\s*["']?\s*[:=]\s*["']?(?:bearer|basic)\s+)
    [^\s,;}"']+'''
)
_CLI_SECRET = re.compile(
    r'''(?ix)(?P<prefix>--?(?:access[_-]?token|access[_-]?key|api[_-]?key|token|password|passwd|secret|credential|session|cookie)(?:\s+|=))
    (?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;]+)'''
)
_IPV4 = re.compile(r"(?<![\w.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![\w.])")
_IPV6_CANDIDATE = re.compile(
    r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{0,4}:){2,}"
    r"(?:[0-9A-Fa-f]{0,4}|(?:[0-9]{1,3}\.){3}[0-9]{1,3})"
    r"(?:%[A-Za-z0-9_.-]+)?(?![0-9A-Fa-f:])"
)
_WINDOWS_HOME = re.compile(r"(?i)([A-Z]:[\\/]Users[\\/])[^\\/\s]+")
_POSIX_HOME = re.compile(r"(?i)(/(?:home|Users)/)[^/\s]+")
_PROFILE_VARIABLE = re.compile(r"(?i)%USERPROFILE%")
_SECRET_HINT = re.compile(
    r"(?i)(?:authorization|token|password|passwd|secret|credential|session|cookie|api[_-]?key|access[_-]?token|access[_-]?key)"
)


class LogUploadError(Exception):
    """Safe, non-sensitive failure shown to callers."""


def _redact_ip(match: re.Match[str]) -> str:
    value = match.group(0)
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return value
    return "[IP redacted]"


def sanitize_crash_log(
    content: str,
    *,
    secrets: tuple[str, ...] | list[str] = (),
    home_paths: tuple[str, ...] | list[str] = (),
) -> str:
    """Redact common identifiers and credentials, then enforce API bounds.

    Redaction covers configured webhook URLs, common Discord webhook URLs,
    secret-like assignments, bearer/basic authorization, IPs, and home-directory
    usernames. This is best-effort scrubbing; it cannot identify every private
    value in arbitrary mod output.
    """
    if not isinstance(content, str):
        raise TypeError("Log content must be text")

    for secret in sorted((item for item in secrets if item), key=len, reverse=True):
        content = content.replace(secret, "[REDACTED]")
    content = _DISCORD_WEBHOOK.sub("[Discord webhook redacted]", content)
    content = _AUTHORIZATION.sub(r"\1[REDACTED]", content)
    if _SECRET_HINT.search(content):
        content = _SECRET_ASSIGNMENT.sub(lambda match: match["prefix"] + "[REDACTED]", content)
    content = _CLI_SECRET.sub(lambda match: match["prefix"] + "[REDACTED]", content)

    for home_path in sorted((item.rstrip("\\/") for item in home_paths if item), key=len, reverse=True):
        content = re.sub(re.escape(home_path), "[home directory]", content, flags=re.IGNORECASE)
    content = _WINDOWS_HOME.sub(r"\1[user]", content)
    content = _POSIX_HOME.sub(r"\1[user]", content)
    content = _PROFILE_VARIABLE.sub("[home directory]", content)
    content = _IPV6_CANDIDATE.sub(_redact_ip, content)
    content = _IPV4.sub(_redact_ip, content)

    lines = content.splitlines()
    if len(lines) > MAX_UPLOAD_LINES:
        lines = lines[: MAX_UPLOAD_LINES - 1]
        lines.append("[Log truncated: line limit reached]")
    content = "\n".join(lines)
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_UPLOAD_BYTES:
        marker = " [Log truncated: byte limit reached]"
        prefix = encoded[: MAX_UPLOAD_BYTES - len(marker.encode("utf-8"))]
        content = prefix.decode("utf-8", errors="ignore").rstrip() + marker
    return content


def _trusted_log_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "mclo.gs"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port is not None
            or parsed.query
            or parsed.fragment
            or not re.fullmatch(r"/[A-Za-z0-9]{4,64}", parsed.path)
        ):
            return None
    except ValueError:
        return None
    return f"https://mclo.gs{parsed.path}"


class MclogsUploader:
    """Upload a sanitized log and return only a validated public log URL."""

    def __init__(
        self,
        *,
        secrets: tuple[str, ...] | list[str] = (),
        home_paths: tuple[str, ...] | list[str] = (),
        timeout_seconds: int = UPLOAD_TIMEOUT_SECONDS,
    ):
        self.secrets = tuple(secrets)
        self.home_paths = tuple(home_paths)
        self.timeout_seconds = min(max(1, int(timeout_seconds)), UPLOAD_TIMEOUT_SECONDS)
        self._session: aiohttp.ClientSession | None = None

    async def upload(self, content: str, *, source: str = "Minecraft server") -> str:
        cleaned = sanitize_crash_log(
            content,
            secrets=self.secrets,
            home_paths=self.home_paths,
        )
        if not cleaned.strip():
            raise LogUploadError("The crash log is empty after sanitizing.")

        try:
            if self._session is None or self._session.closed:
                timeout = aiohttp.ClientTimeout(
                    total=self.timeout_seconds,
                    connect=min(5, self.timeout_seconds),
                    sock_read=self.timeout_seconds,
                )
                self._session = aiohttp.ClientSession(timeout=timeout, trust_env=False)

            async with self._session.post(
                API_URL,
                json={"content": cleaned, "source": source},
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(
                    total=self.timeout_seconds,
                    connect=min(5, self.timeout_seconds),
                    sock_read=self.timeout_seconds,
                ),
            ) as response:
                if response.status != 200:
                    raise LogUploadError("mclo.gs returned an unsuccessful response.")
                result = await response.json(content_type=None)
        except asyncio.CancelledError:
            raise
        except LogUploadError:
            raise
        except Exception:
            raise LogUploadError("Could not upload the crash log to mclo.gs.") from None

        url = _trusted_log_url(result.get("url") if isinstance(result, dict) and result.get("success") is True else None)
        if url is None:
            raise LogUploadError("mclo.gs did not return a valid log link.")
        return url

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None
