import asyncio
import sys

from main import cli
from utils.runtime import default_config_path, resource_path
from utils.logutil import LogUtil
from server.server import Server


def test_frozen_resources_and_config_have_separate_locations(tmp_path, monkeypatch):
    bundle = tmp_path / "temporary-bundle"
    executable = tmp_path / "installed" / "notifier.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    assert resource_path("translations/ja_jp.json") == bundle / "translations/ja_jp.json"
    assert default_config_path() == executable.parent / ".env"


def test_source_config_uses_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert default_config_path() == tmp_path / ".env"
    assert resource_path("translations/ja_jp.json").is_file()


def test_init_config_never_overwrites_existing_settings(tmp_path):
    config = tmp_path / "config" / ".env"
    assert cli(["--config", str(config), "--init-config"]) == 0
    original = config.read_bytes()
    assert b"WEBHOOK_URL=" in original
    assert cli(["--config", str(config), "--init-config"]) == 1
    assert config.read_bytes() == original


def test_config_check_from_another_directory_without_network(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / ".env"
    config.write_text(
        'WEBHOOK_URL=https://discord.com/api/webhooks/123456789012345678/test-tokentest-tokentest-tokentest-tokentest-tokentest-token\n',
        encoding="utf-8",
    )
    assert cli(["--config", str(config), "--check-config"]) == 0


def test_waiting_for_first_log_file(tmp_path):
    logfile = tmp_path / "latest.log"
    logutil = LogUtil()
    logutil.load_to_prev(str(logfile))
    logfile.write_text("日本語のログ\n", encoding="utf-8")
    assert logutil.get_log_diff(str(logfile)) == ["日本語のログ\n"]


def test_shutdown_before_webhook_initialization():
    asyncio.run(Server().shutdown())
