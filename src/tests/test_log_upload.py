"""No-network tests for sanitized, bounded mclo.gs crash-log uploads."""

import asyncio

import pytest

WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/" + "secret-hook-token-" * 5


def load_log_upload_module():
    import importlib

    try:
        return importlib.import_module("message.log_upload")
    except ModuleNotFoundError as error:
        pytest.fail(f"mclo.gs upload implementation is missing: {error}")


class FakeResponse:
    status = 200

    def __init__(self, body):
        self.body = body

    async def json(self, *, content_type=None):
        return self.body


class FakeRequest:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, *args):
        return False


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.closed = False

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeRequest(self.response)

    async def close(self):
        self.closed = True


def run_upload(tmp_path, monkeypatch, response, text, *, secrets=(), home_paths=()):
    log_upload = load_log_upload_module()
    session = FakeSession(FakeResponse(response))
    monkeypatch.setattr(log_upload.aiohttp, "ClientSession", lambda **_kwargs: session)
    uploader = log_upload.MclogsUploader(secrets=secrets, home_paths=home_paths)

    async def exercise():
        try:
            result = await uploader.upload(text, source="Send-Minecraft-notifications")
            return result, session, uploader
        except Exception as error:
            return error, session, uploader
        finally:
            await uploader.close()

    return asyncio.run(exercise())


def test_upload_posts_only_sanitized_bounded_content_and_accepts_official_url(
    tmp_path, monkeypatch
):
    text = (
        f"config webhook: {WEBHOOK}\n"
        "Authorization: Bearer abcdef0123456789\n"
        "server-token=abcdefghijklmnopqrstuvwxyz0123456789\n"
        "Player IP: 203.0.113.84\n"
        r"User home: C:\Users\alice\AppData\Roaming\.minecraft" + "\n"
        + "safe crash record\n"
    )
    result, session, uploader = run_upload(
        tmp_path,
        monkeypatch,
        {"success": True, "url": "https://mclo.gs/AbC123"},
        text,
        secrets=(WEBHOOK, "abcdefghijklmnopqrstuvwxyz0123456789"),
        home_paths=(r"C:\Users\alice",),
    )

    assert result == "https://mclo.gs/AbC123"
    assert len(session.calls) == 1
    url, request = session.calls[0]
    assert url == "https://api.mclo.gs/1/log"
    assert request["allow_redirects"] is False
    assert request["json"]["source"] == "Send-Minecraft-notifications"
    uploaded = request["json"]["content"]
    for secret in (WEBHOOK, "abcdef0123456789", "abcdefghijklmnopqrstuvwxyz0123456789", "203.0.113.84", r"C:\Users\alice"):
        assert secret not in uploaded
    assert "safe crash record" in uploaded
    assert uploader.timeout_seconds <= 15

    assert session.closed


@pytest.mark.parametrize("response", [
    {"success": False, "error": "private server token abc123"},
    {"success": True, "url": "https://mclo.gs.evil.example/AbC123"},
    {"success": True, "url": "http://mclo.gs/AbC123"},
    {"success": True, "url": "https://mclo.gs/../delete"},
    {"success": True, "url": "https://mclo.gs/AbC123?token=secret"},
])
def test_untrusted_or_failed_upload_responses_do_not_become_discord_links(
    tmp_path, monkeypatch, response
):
    log_upload = load_log_upload_module()
    result, _session, _uploader = run_upload(
        tmp_path, monkeypatch, response, "---- Minecraft Crash Report ----\n"
    )
    assert isinstance(result, log_upload.LogUploadError)
    assert "private server token" not in str(result)
    assert "secret" not in str(result)


def test_non_json_api_response_is_a_safe_upload_failure(tmp_path, monkeypatch):
    log_upload = load_log_upload_module()
    session = FakeSession(FakeResponse({}))

    async def invalid_json(**kwargs):
        raise ValueError("response included a private token")

    session.response.json = invalid_json
    monkeypatch.setattr(log_upload.aiohttp, "ClientSession", lambda **_kwargs: session)
    uploader = log_upload.MclogsUploader()

    async def exercise():
        with pytest.raises(log_upload.LogUploadError) as raised:
            await uploader.upload("crash report")
        assert "private token" not in str(raised.value)
        await uploader.close()

    asyncio.run(exercise())


def test_upload_never_redirects_and_passes_strict_request_timeout(tmp_path, monkeypatch):
    result, session, uploader = run_upload(
        tmp_path,
        monkeypatch,
        {"success": True, "url": "https://mclo.gs/AbC123"},
        "crash",
    )
    assert result == "https://mclo.gs/AbC123"
    assert session.calls[0][1]["allow_redirects"] is False
    assert session.calls[0][1]["timeout"].total <= 15
def test_upload_content_is_limited_to_both_service_size_and_line_bounds():
    log_upload = load_log_upload_module()
    MAX_UPLOAD_BYTES = log_upload.MAX_UPLOAD_BYTES
    MAX_UPLOAD_LINES = log_upload.MAX_UPLOAD_LINES

    assert MAX_UPLOAD_BYTES < 10 * 1024 * 1024
    assert MAX_UPLOAD_LINES <= 25_000
    content = "x" * (MAX_UPLOAD_BYTES + 1024) + "\n" + "second line"
    sanitized = log_upload.sanitize_crash_log(content)
    assert len(sanitized.encode("utf-8")) <= MAX_UPLOAD_BYTES
    many_lines = "\n".join(f"line {index}" for index in range(MAX_UPLOAD_LINES + 10))
    assert len(log_upload.sanitize_crash_log(many_lines).splitlines()) <= MAX_UPLOAD_LINES

