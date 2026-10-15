"""Reuse legacy Python installations without copying or modifying their secrets."""
from pathlib import Path
import sys
import tomllib

import pytest

import main as entrypoint
from handlers.secrets import BotEnv
from main import cli
from utils.config import CONFIG_FILENAME, TEMPLATE_FILENAME
from utils.runtime import resource_path


WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/" + "test-token" * 6


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in BotEnv:
        monkeypatch.delenv(name.value, raising=False)


def legacy_installation(directory: Path, *, markers: bool = True) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    if markers:
        for relative in ("src/main.py", "src/handlers/secrets.py"):
            marker = directory / relative
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("# Legacy Python installation\n", encoding="utf-8")
    config = directory / ".env"
    config.write_text(
        f'WEBHOOK_URL={WEBHOOK}\nTARGET_DIR="./server/logs"\nPLUGIN_DIR="./plugins"\n'
        'SERVER_START_MESSAGE="旧版の設定\\n二行目"\n',
        encoding="utf-8-sig",
    )
    return config


def frozen_installation(directory: Path, monkeypatch) -> Path:
    bundle = resource_path(TEMPLATE_FILENAME).parent
    directory.mkdir(parents=True, exist_ok=True)
    executable = directory / "notifier.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    return directory / CONFIG_FILENAME


def test_explicit_old_directory_is_accepted_and_relative_paths_stay_at_source(tmp_path, capsys):
    old_config = legacy_installation(tmp_path / "old project")
    original = old_config.read_bytes()
    assert cli(["--config", str(old_config.parent), "--check-config"]) == 0
    assert BotEnv.TargetDir.get() == str(old_config.parent / "server" / "logs")
    assert BotEnv.PluginDir.get() == str(old_config.parent / "plugins")
    assert BotEnv.ServerStartMessage.get() == "旧版の設定\n二行目"
    assert BotEnv.SenderIconPlayer.get() == ""
    assert old_config.read_bytes() == original
    assert (old_config.parent / CONFIG_FILENAME).is_file()
    assert WEBHOOK not in capsys.readouterr().out


@pytest.mark.parametrize("location", ["working-directory", "child", "sibling"])
def test_frozen_binary_automatically_reuses_a_legacy_installation(tmp_path, monkeypatch, capsys, location):
    installed = tmp_path / "standalone"
    adjacent_config = frozen_installation(installed, monkeypatch)
    if location == "working-directory":
        old = tmp_path / "renamed-old-project"
    elif location == "child":
        old = installed / "Send-Minecraft-notifications"
    else:
        old = tmp_path / "Send-Minecraft-notifications"
    old_config = legacy_installation(old)
    original = old_config.read_bytes()
    monkeypatch.chdir(old if location == "working-directory" else installed)
    assert cli(["--check-config"]) == 0
    assert BotEnv.TargetDir.get() == str(old / "server" / "logs")
    assert not adjacent_config.exists()
    assert old_config.read_bytes() == original
    output = capsys.readouterr().out
    assert str(old_config) in output
    assert "Legacy" in output
    assert WEBHOOK not in output


def test_configuration_beside_binary_has_priority_over_legacy_settings(tmp_path, monkeypatch):
    installed = tmp_path / "standalone"
    adjacent_config = frozen_installation(installed, monkeypatch)
    legacy_installation(tmp_path / "Send-Minecraft-notifications")
    adjacent_config.write_text(f'WEBHOOK_URL = "{WEBHOOK}"\nTARGET_DIR = "./new-logs"\n', encoding="utf-8")
    monkeypatch.chdir(installed)
    assert cli(["--check-config"]) == 0
    assert BotEnv.TargetDir.get() == str(installed / "new-logs")


def test_normal_startup_passes_legacy_configuration_to_server(tmp_path, monkeypatch):
    installed = tmp_path / "standalone"
    adjacent_config = frozen_installation(installed, monkeypatch)
    old_config = legacy_installation(tmp_path / "Send-Minecraft-notifications")
    selected = []

    async def run_without_network(config_path):
        selected.append(config_path)
        return 0

    monkeypatch.setattr(entrypoint, "main", run_without_network)
    monkeypatch.chdir(installed)
    assert cli([]) == 0
    assert selected == [old_config.parent / CONFIG_FILENAME]
    assert not adjacent_config.exists()


def test_explicit_config_has_priority_over_automatic_detection(tmp_path, monkeypatch):
    installed = tmp_path / "standalone"
    frozen_installation(installed, monkeypatch)
    legacy_installation(tmp_path / "Send-Minecraft-notifications")
    requested = legacy_installation(tmp_path / "requested", markers=False)
    monkeypatch.chdir(installed)
    assert cli(["--config", str(requested), "--check-config"]) == 0
    assert BotEnv.TargetDir.get() == str(requested.parent / "server" / "logs")


def test_unrelated_working_directory_env_is_not_automatically_loaded(tmp_path, monkeypatch):
    installed = tmp_path / "standalone"
    adjacent_config = frozen_installation(installed, monkeypatch)
    unrelated = legacy_installation(tmp_path / "other-app", markers=False)
    monkeypatch.chdir(unrelated.parent)
    assert cli(["--check-config"]) == 1
    assert not adjacent_config.exists()


def test_ambiguous_neighboring_installations_require_explicit_config(tmp_path, monkeypatch, capsys):
    installed = tmp_path / "standalone"
    frozen_installation(installed, monkeypatch)
    legacy_installation(installed / "Send-Minecraft-notifications")
    legacy_installation(tmp_path / "Send-Minecraft-notifications")
    monkeypatch.chdir(installed)
    assert cli(["--check-config"]) == 1
    output = capsys.readouterr().err
    assert "--config" in output
    assert WEBHOOK not in output


def test_working_directory_is_preferred_over_neighboring_installations(tmp_path, monkeypatch):
    installed = tmp_path / "standalone"
    frozen_installation(installed, monkeypatch)
    legacy_installation(tmp_path / "Send-Minecraft-notifications")
    requested = legacy_installation(tmp_path / "working-project")
    monkeypatch.chdir(requested.parent)
    assert cli(["--check-config"]) == 0
    assert BotEnv.TargetDir.get() == str(requested.parent / "server" / "logs")


def test_init_config_still_creates_a_new_template_beside_binary(tmp_path, monkeypatch):
    installed = tmp_path / "standalone"
    adjacent_config = frozen_installation(installed, monkeypatch)
    old_config = legacy_installation(tmp_path / "Send-Minecraft-notifications")
    original = old_config.read_bytes()
    monkeypatch.chdir(installed)
    assert cli(["--init-config"]) == 0
    assert "PASTE_YOUR_WEBHOOK_URL_HERE" in adjacent_config.read_text(encoding="utf-8")
    assert old_config.read_bytes() == original


def test_legacy_custom_translation_is_used(tmp_path, monkeypatch):
    installed = tmp_path / "standalone"
    frozen_installation(installed, monkeypatch)
    old_config = legacy_installation(tmp_path / "Send-Minecraft-notifications")
    translations = old_config.parent / "translations"
    translations.mkdir()
    (translations / "ja_jp.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(installed)
    assert cli(["--check-config"]) == 1


def test_source_mode_keeps_working_directory_default(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    legacy_installation(tmp_path / "Send-Minecraft-notifications")
    monkeypatch.chdir(tmp_path)
    assert cli(["--check-config"]) == 1


def test_missing_explicit_directory_config_does_not_create_a_template(tmp_path, monkeypatch):
    installed = tmp_path / "standalone"
    frozen_installation(installed, monkeypatch)
    empty = tmp_path / "empty-old-project"
    empty.mkdir()
    assert cli(["--config", str(empty)]) == 1
    assert not (empty / ".env").exists()
    assert not (empty / CONFIG_FILENAME).exists()


def test_missing_explicit_file_does_not_create_a_template(tmp_path, monkeypatch):
    frozen_installation(tmp_path / "standalone", monkeypatch)
    missing = tmp_path / "old-project" / ".env"
    assert cli(["--config", str(missing)]) == 1
    assert not missing.exists()


def test_adjacent_old_config_migrates_once_then_toml_has_priority(tmp_path, monkeypatch):
    installed = tmp_path / "standalone"
    canonical = frozen_installation(installed, monkeypatch)
    old_config = legacy_installation(installed, markers=False)
    original = old_config.read_bytes()
    monkeypatch.chdir(installed)
    assert cli(["--check-config"]) == 0
    assert canonical.is_file()
    migrated = canonical.read_bytes()
    # The existing TOML wins even if the old file is later malformed.
    old_config.write_text("=invalid legacy content\n", encoding="utf-8")
    assert cli(["--check-config"]) == 0
    assert cli(["--config", str(old_config), "--check-config"]) == 0
    assert canonical.read_bytes() == migrated
    assert original != old_config.read_bytes()


def test_cli_migration_never_saves_environment_overrides(tmp_path, monkeypatch):
    old_config = legacy_installation(tmp_path / "old")
    monkeypatch.setenv("WEBHOOK_URL", WEBHOOK.replace("test-token", "other-token"))
    monkeypatch.setenv("TARGET_DIR", "./environment-logs")
    assert cli(["--config", str(old_config), "--check-config"]) == 0
    migrated = tomllib.loads((old_config.parent / CONFIG_FILENAME).read_text(encoding="utf-8"))
    assert migrated["WEBHOOK_URL"] == WEBHOOK
    assert migrated["TARGET_DIR"] == "./server/logs"
    assert BotEnv.TargetDir.get() == str(old_config.parent / "environment-logs")


def test_init_config_migrates_adjacent_old_file_without_masking_it(tmp_path, monkeypatch):
    installed = tmp_path / "standalone"
    canonical = frozen_installation(installed, monkeypatch)
    old_config = legacy_installation(installed, markers=False)
    original = old_config.read_bytes()
    assert cli(["--init-config"]) == 0
    migrated = tomllib.loads(canonical.read_text(encoding="utf-8"))
    assert migrated["WEBHOOK_URL"] == WEBHOOK
    assert old_config.read_bytes() == original


def test_init_config_rejects_new_dotenv_filename(tmp_path):
    legacy = tmp_path / ".env"
    assert cli(["--config", str(legacy), "--init-config"]) == 1
    assert not legacy.exists()


def test_invalid_toml_is_not_replaced_by_old_config(tmp_path, capsys):
    old_config = legacy_installation(tmp_path / "old")
    canonical = old_config.parent / CONFIG_FILENAME
    secret = "private-token-in-broken-toml"
    canonical.write_text(f'WEBHOOK_URL = "{secret}\n', encoding="utf-8")
    original = canonical.read_bytes()
    assert cli(["--config", str(old_config), "--check-config"]) == 1
    assert canonical.read_bytes() == original
    assert secret not in capsys.readouterr().err


def test_named_toml_in_working_directory_can_be_found_without_old_source(tmp_path, monkeypatch):
    installed = tmp_path / "standalone"
    frozen_installation(installed, monkeypatch)
    working = tmp_path / "minecraft"
    working.mkdir()
    (working / CONFIG_FILENAME).write_text(f'WEBHOOK_URL = "{WEBHOOK}"\n', encoding="utf-8")
    monkeypatch.chdir(working)
    assert cli(["--check-config"]) == 0
    assert BotEnv.TargetDir.get() == str(working / "logs")


def test_first_source_startup_creates_named_toml_instead_of_dotenv(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.chdir(tmp_path)
    assert cli([]) == 0
    created = tmp_path / CONFIG_FILENAME
    assert isinstance(tomllib.loads(created.read_text(encoding="utf-8"))["EMBED_MODE"], bool)
    assert not (tmp_path / ".env").exists()


def test_environment_only_config_check_never_writes_process_secrets(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WEBHOOK_URL", WEBHOOK)
    assert cli(["--check-config"]) == 0
    assert list(tmp_path.iterdir()) == []


def test_default_config_directory_is_reported_instead_of_ignored(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.chdir(tmp_path)
    canonical = tmp_path / CONFIG_FILENAME
    canonical.mkdir()
    monkeypatch.setenv("WEBHOOK_URL", WEBHOOK)
    assert cli(["--check-config"]) == 1
    assert list(canonical.iterdir()) == []
