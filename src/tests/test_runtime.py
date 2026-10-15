import asyncio
import sys
import os
import subprocess
from pathlib import Path

from main import cli
from utils.config import CONFIG_FILENAME
from utils.runtime import default_config_path, resource_path
from utils.logutil import LogUtil
from server.server import Server


def test_first_run_outputs_utf8_even_with_a_western_console_encoding(tmp_path):
    entrypoint = Path(__file__).resolve().parents[1] / "main.py"
    result = subprocess.run(
        [sys.executable, str(entrypoint), "--config", str(tmp_path / CONFIG_FILENAME), "--init-config"],
        env=os.environ | {"PYTHONIOENCODING": "cp1252"},
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert "WEBHOOK_URL と TARGET_DIR" in result.stdout.decode("utf-8")


def test_frozen_resources_and_config_have_separate_locations(tmp_path, monkeypatch):
    bundle = tmp_path / "temporary-bundle"
    executable = tmp_path / "installed" / "notifier.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    assert resource_path("translations/ja_jp.json") == bundle / "translations/ja_jp.json"
    assert default_config_path() == executable.parent / CONFIG_FILENAME


def test_source_config_uses_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert default_config_path() == tmp_path / CONFIG_FILENAME
    assert resource_path("translations/ja_jp.json").is_file()


def test_init_config_never_overwrites_existing_settings(tmp_path):
    config = tmp_path / "config" / CONFIG_FILENAME
    assert cli(["--config", str(config), "--init-config"]) == 0
    original = config.read_bytes()
    assert b"WEBHOOK_URL =" in original
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
