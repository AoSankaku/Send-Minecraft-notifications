import json
import os
import stat
import tomllib
from pathlib import Path

import pytest

from utils.config import (
    CONFIG_FILENAME,
    TEMPLATE_FILENAME,
    load_config_values,
    migrate_legacy_config,
    write_private_config,
)


TEMPLATE = Path(__file__).resolve().parents[2] / TEMPLATE_FILENAME
WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/" + "secret-token-" * 6


def test_toml_template_has_botenv_compatible_defaults(tmp_path):
    values = load_config_values(tmp_path / CONFIG_FILENAME, TEMPLATE, environment={})

    assert values["WEBHOOK_URL"].startswith("https://discord.com/api/webhooks/")
    assert values["KILL_AFTER_CLOSED"] == "true"
    assert json.loads(values["IGNORE_NAMES"]) == [
        "ChunkTaskScheduler", "ChunkHolderManager", "BE", "Simple_Harvest",
        "Dynmap", "Nbt Crafting", "STDOUT", "Chunky",
    ]
    assert json.loads(values["JAPANIZE_DICTIONARY"]) == {}
    assert json.loads(values["JAPANIZE_PUBLIC_CHANNELS"]) == []
    assert values["SERVER_START_MESSAGE"] == "==================================>\n:door: **【サーバーがオンラインになりました！】**\n==================================>"


def test_native_toml_types_and_json_dictionary_sections(tmp_path):
    config = tmp_path / CONFIG_FILENAME
    config.write_text(
        'KILL_AFTER_CLOSED = false\n'
        'EMBED_MODE = true\n'
        'IGNORE_NAMES = ["名前,一", "名前\\\\二"]\n'
        'TIPS_MESSAGES = ["一行目\\\\n二行目"]\n'
        'JAPANIZE_PUBLIC_CHANNELS = ["global"]\n'
        '[JAPANIZE_DICTIONARY]\nmaikura = "マイクラ"\n',
        encoding="utf-8",
    )

    values = load_config_values(config, TEMPLATE, environment={})

    assert values["KILL_AFTER_CLOSED"] == "false"
    assert values["EMBED_MODE"] == "true"
    assert json.loads(values["IGNORE_NAMES"]) == ["名前,一", "名前\\二"]
    # Native TOML strings retain their literal backslash-n semantics.
    assert json.loads(values["TIPS_MESSAGES"]) == [r"一行目\n二行目"]
    assert json.loads(values["JAPANIZE_PUBLIC_CHANNELS"]) == ["global"]
    assert json.loads(values["JAPANIZE_DICTIONARY"]) == {"maikura": "マイクラ"}


def test_environment_overrides_only_known_keys_and_decodes_message_newlines(tmp_path):
    values = load_config_values(
        tmp_path / CONFIG_FILENAME,
        TEMPLATE,
        environment={
            "WEBHOOK_URL": WEBHOOK,
            "SERVER_START_MESSAGE": r"一行目\n二行目",
            "TIPS_MESSAGES": '["一行目\\n二行目"]',
            "UNRECOGNIZED_SETTING": "must not be loaded",
        },
    )

    assert values["WEBHOOK_URL"] == WEBHOOK
    assert values["SERVER_START_MESSAGE"] == "一行目\n二行目"
    assert json.loads(values["TIPS_MESSAGES"]) == ["一行目\n二行目"]
    assert "UNRECOGNIZED_SETTING" not in values


def test_legacy_dotenv_migration_converts_types_and_preserves_source(tmp_path):
    legacy = tmp_path / ".env"
    original = (
        "\ufeffWEBHOOK_URL=" + WEBHOOK + "\n"
        'TARGET_DIR="C:\\\\Minecraft\\\\logs"\n'
        "IGNORE_NAMES=alpha, beta, gamma\n"
        'KILL_AFTER_CLOSED="false"\n'
        'SERVER_START_MESSAGE="一行目\\\\n二行目"\n'
        'TIPS_MESSAGES=["日本語,カンマ","一行目\\\\n二行目"]\n'
        'JAPANIZE_DICTIONARY={"maikura":"マイクラ"}\n'
        'JAPANIZE_PUBLIC_CHANNELS=["global"]\n'
        "OLD_EXTENSION=keep-me\n"
    )
    legacy.write_bytes(original.encode("utf-8"))

    destination, created = migrate_legacy_config(legacy, TEMPLATE)

    assert destination == tmp_path / CONFIG_FILENAME
    assert created
    assert legacy.read_bytes() == original.encode("utf-8")
    migrated = tomllib.loads(destination.read_text(encoding="utf-8"))
    assert migrated["TARGET_DIR"] == r"C:\Minecraft\logs"
    assert migrated["IGNORE_NAMES"] == ["alpha", "beta", "gamma"]
    assert migrated["KILL_AFTER_CLOSED"] is False
    assert migrated["SERVER_START_MESSAGE"] == "一行目\n二行目"
    assert migrated["TIPS_MESSAGES"] == ["日本語,カンマ", "一行目\n二行目"]
    assert migrated["JAPANIZE_DICTIONARY"] == {"maikura": "マイクラ"}
    assert migrated["JAPANIZE_PUBLIC_CHANNELS"] == ["global"]
    assert migrated["OLD_EXTENSION"] == "keep-me"
    assert load_config_values(destination, TEMPLATE, environment={})["TARGET_DIR"] == r"C:\Minecraft\logs"


def test_migration_does_not_persist_process_environment(tmp_path, monkeypatch):
    legacy = tmp_path / ".env"
    legacy.write_text("WEBHOOK_URL=https://discord.com/api/webhooks/old\n", encoding="utf-8")
    monkeypatch.setenv("WEBHOOK_URL", WEBHOOK)

    destination, created = migrate_legacy_config(legacy, TEMPLATE)

    assert created
    assert tomllib.loads(destination.read_text(encoding="utf-8"))["WEBHOOK_URL"].endswith("/old")


def test_migration_does_not_expand_legacy_values_from_process_environment(tmp_path, monkeypatch):
    legacy = tmp_path / ".env"
    legacy.write_text("SENDER_NAME=${WEBHOOK_URL}\n", encoding="utf-8")
    monkeypatch.setenv("WEBHOOK_URL", WEBHOOK)

    destination, created = migrate_legacy_config(legacy, TEMPLATE)

    assert created
    assert tomllib.loads(destination.read_text(encoding="utf-8"))["SENDER_NAME"] == "${WEBHOOK_URL}"


def test_migration_expands_only_prior_file_values_and_explicit_defaults(tmp_path, monkeypatch):
    legacy = tmp_path / ".env"
    legacy.write_text(
        "BASE_DIR=./local-server\n"
        "TARGET_DIR=${BASE_DIR}/logs\n"
        "SENDER_NAME=${MISSING_NAME:-Local bot}\n"
        "PLAYER_ICON_API=${PROCESS_ONLY}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BASE_DIR", "./process-server")
    monkeypatch.setenv("MISSING_NAME", "Process bot")
    monkeypatch.setenv("PROCESS_ONLY", "must-not-expand")

    destination, created = migrate_legacy_config(legacy, TEMPLATE)
    migrated = tomllib.loads(destination.read_text(encoding="utf-8"))

    assert created
    assert migrated["BASE_DIR"] == "./local-server"
    assert migrated["TARGET_DIR"] == "./local-server/logs"
    assert migrated["SENDER_NAME"] == "Local bot"
    assert migrated["PLAYER_ICON_API"] == "${PROCESS_ONLY}"


def test_migration_rejects_malformed_dotenv_without_leaking_source_or_partial_file(tmp_path):
    legacy = tmp_path / ".env"
    secret = "malformed-private-secret"
    legacy.write_text(f"WEBHOOK_URL={WEBHOOK}\n={secret}\n", encoding="utf-8")

    with pytest.raises(ValueError) as error:
        migrate_legacy_config(legacy, TEMPLATE)

    assert str(legacy) in str(error.value)
    assert secret not in str(error.value)
    assert not (tmp_path / CONFIG_FILENAME).exists()


def test_migration_is_idempotent_and_existing_destination_has_priority(tmp_path):
    legacy = tmp_path / ".env"
    legacy.write_text("not valid dotenv = but not read\n", encoding="utf-8")
    destination = tmp_path / CONFIG_FILENAME
    destination.write_text('WEBHOOK_URL = "existing"\n', encoding="utf-8")

    returned, created = migrate_legacy_config(legacy, TEMPLATE)

    assert returned == destination
    assert not created
    assert destination.read_text(encoding="utf-8") == 'WEBHOOK_URL = "existing"\n'


def test_migration_rejects_invalid_source_without_creating_destination(tmp_path):
    legacy = tmp_path / ".env"
    secret = "sensitive-invalid-setting-value"
    legacy.write_text(f"KILL_AFTER_CLOSED={secret}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="KILL_AFTER_CLOSED") as error:
        migrate_legacy_config(legacy, TEMPLATE)

    assert secret not in str(error.value)
    assert not (tmp_path / CONFIG_FILENAME).exists()
    assert legacy.read_text(encoding="utf-8") == f"KILL_AFTER_CLOSED={secret}\n"


@pytest.mark.parametrize(
    "name,value",
    [
        ("KILL_AFTER_CLOSED", '"true"'),
        ("IGNORE_NAMES", '["ok", 3]'),
        ("TIPS_MESSAGES", '"not an array"'),
        ("JAPANIZE_DICTIONARY", '{ key = 1 }'),
        ("JAPANIZE_PUBLIC_CHANNELS", '[true]'),
        ("TARGET_DIR", "4"),
    ],
)
def test_invalid_native_types_report_only_name_and_path(tmp_path, name, value):
    config = tmp_path / CONFIG_FILENAME
    secret = "private-value"
    config.write_text(f"{name} = {value.replace('ok', secret)}\n", encoding="utf-8")

    with pytest.raises(ValueError, match=name) as error:
        load_config_values(config, TEMPLATE, environment={})

    assert secret not in str(error.value)
    assert str(config) in str(error.value)


def test_invalid_legacy_json_never_echoes_value(tmp_path):
    config = tmp_path / ".env"
    secret = "private-tips-token"
    config.write_text(f"TIPS_MESSAGES=[{secret}]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="TIPS_MESSAGES") as error:
        load_config_values(config, TEMPLATE, environment={})

    assert secret not in str(error.value)


def test_write_private_config_is_exclusive_and_private_on_posix(tmp_path):
    config = tmp_path / CONFIG_FILENAME
    write_private_config(config, "WEBHOOK_URL = \"secret\"\n")

    if os.name == "posix":
        assert stat.S_IMODE(config.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        write_private_config(config, "WEBHOOK_URL = \"replacement\"\n")
    assert config.read_text(encoding="utf-8") == 'WEBHOOK_URL = "secret"\n'


def test_private_config_is_complete_before_atomic_publication(tmp_path, monkeypatch):
    import utils.config as config_module

    config = tmp_path / CONFIG_FILENAME
    text = 'WEBHOOK_URL = "complete"\n'
    original_fsync = os.fsync
    observed = []

    def inspect_before_publish(descriptor):
        assert not config.exists()
        temporary_files = list(tmp_path.glob(f".{CONFIG_FILENAME}.*.tmp"))
        assert len(temporary_files) == 1
        assert temporary_files[0].read_text(encoding="utf-8") == text
        observed.append(True)
        return original_fsync(descriptor)

    monkeypatch.setattr(config_module.os, "fsync", inspect_before_publish)
    write_private_config(config, text)

    assert observed == [True]
    assert config.read_text(encoding="utf-8") == text
    assert list(tmp_path.glob(f".{CONFIG_FILENAME}.*.tmp")) == []


def test_publish_race_keeps_existing_destination_and_cleans_temporary_file(tmp_path, monkeypatch):
    import utils.config as config_module

    config = tmp_path / CONFIG_FILENAME
    original_fsync = os.fsync

    def create_destination_during_write(descriptor):
        config.write_text('WEBHOOK_URL = "concurrent"\n', encoding="utf-8")
        return original_fsync(descriptor)

    monkeypatch.setattr(config_module.os, "fsync", create_destination_during_write)
    with pytest.raises(FileExistsError):
        write_private_config(config, 'WEBHOOK_URL = "ours"\n')

    assert config.read_text(encoding="utf-8") == 'WEBHOOK_URL = "concurrent"\n'
    assert list(tmp_path.glob(f".{CONFIG_FILENAME}.*.tmp")) == []


def test_write_failure_removes_only_its_partial_file(tmp_path, monkeypatch):
    import utils.config as config_module

    config = tmp_path / CONFIG_FILENAME
    other = tmp_path / "other.txt"
    other.write_text("keep", encoding="utf-8")

    def fail_fsync(_descriptor):
        raise OSError("write failed")

    monkeypatch.setattr(config_module.os, "fsync", fail_fsync)
    with pytest.raises(OSError):
        write_private_config(config, "partial")

    assert not config.exists()
    assert other.read_text(encoding="utf-8") == "keep"
    assert list(tmp_path.glob(f".{CONFIG_FILENAME}.*.tmp")) == []


def test_migration_never_follows_or_replaces_destination_symlink(tmp_path):
    legacy = tmp_path / ".env"
    legacy.write_text("WEBHOOK_URL=https://discord.com/api/webhooks/legacy\n", encoding="utf-8")
    outside = tmp_path / "outside.toml"
    outside.write_text('WEBHOOK_URL = "preserve"\n', encoding="utf-8")
    destination = tmp_path / CONFIG_FILENAME
    try:
        destination.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")

    returned, created = migrate_legacy_config(legacy, TEMPLATE)

    assert returned == destination
    assert not created
    assert destination.is_symlink()
    assert outside.read_text(encoding="utf-8") == 'WEBHOOK_URL = "preserve"\n'


def test_template_filename_constant_matches_checked_in_template():
    assert TEMPLATE.name == TEMPLATE_FILENAME
