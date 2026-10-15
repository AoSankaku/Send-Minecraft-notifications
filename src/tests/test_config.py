import asyncio
import json

import pytest

from handlers.secrets import BotEnv
from server.server import Server
from utils.miscutil import normalize_message_newlines


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in BotEnv:
        monkeypatch.delenv(name.value, raising=False)


@pytest.mark.parametrize("quote", ["", "'", '"'])
def test_newlines_in_all_dotenv_quote_styles(tmp_path, quote):
    config = tmp_path / ".env"
    config.write_text(
        'WEBHOOK_URL=https://discord.com/api/webhooks/123456789012345678/test-tokentest-tokentest-tokentest-tokentest-tokentest-token\n'
        f'SERVER_START_MESSAGE={quote}日本語\\n二行目{quote}\n', encoding="utf-8",
    )
    BotEnv.init(config)
    assert BotEnv.ServerStartMessage.get() == "日本語\n二行目"
    assert BotEnv.TargetDir.get() == str((tmp_path / "logs").resolve())


def test_environment_newlines_and_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WEBHOOK_URL", "https://discord.com/api/webhooks/123456789012345678/test-tokentest-tokentest-tokentest-tokentest-tokentest-token")
    monkeypatch.setenv("SERVER_STOP_MESSAGE", r"日本語\n二行目\r\n三行目")
    monkeypatch.setenv("TARGET_DIR", r"C:\new\logs")
    BotEnv.init()
    assert BotEnv.ServerStopMessage.get() == "日本語\n二行目\n三行目"
    assert "\n" not in BotEnv.TargetDir.get()


def test_environment_overrides_file(tmp_path, monkeypatch):
    config = tmp_path / ".env"
    config.write_text('SERVER_START_MESSAGE="file"\nSENDER_ICON_PLAYER="FilePlayer"\n', encoding="utf-8")
    monkeypatch.setenv("WEBHOOK_URL", "https://discord.com/api/webhooks/123456789012345678/test-tokentest-tokentest-tokentest-tokentest-tokentest-token")
    monkeypatch.setenv("SERVER_START_MESSAGE", r"environment\nmessage")
    monkeypatch.setenv("SENDER_ICON_PLAYER", "EnvironmentPlayer")
    BotEnv.init(config)
    assert BotEnv.ServerStartMessage.get() == "environment\nmessage"
    assert BotEnv.SenderIconPlayer.get() == "EnvironmentPlayer"


@pytest.mark.parametrize("icon_player", ["", "AdminPlayer"])
def test_optional_sender_icon_player_in_config(tmp_path, monkeypatch, icon_player):
    config = tmp_path / ".env"
    # Existing configurations do not need to add the new optional setting.
    config.write_text(
        'SENDER_ICON="https://example.com/custom.png"\n'
        + (f'SENDER_ICON_PLAYER="{icon_player}"\n' if icon_player else ""),
        encoding="utf-8",
    )
    monkeypatch.setenv("WEBHOOK_URL", "https://discord.com/api/webhooks/123456789012345678/test-tokentest-tokentest-tokentest-tokentest-tokentest-token")
    BotEnv.init(config)
    assert BotEnv.SenderIcon.get() == "https://example.com/custom.png"
    assert BotEnv.SenderIconPlayer.get() == icon_player


def test_server_initialization_uses_configured_icon_player(tmp_path):
    config = tmp_path / ".env"
    config.write_text(
        'WEBHOOK_URL=https://discord.com/api/webhooks/123456789012345678/test-tokentest-tokentest-tokentest-tokentest-tokentest-token\n'
        'SENDER_ICON=""\n'
        'SENDER_ICON_PLAYER="AdminPlayer"\n'
        'PLAYER_ICON_API="https://example.com/avatars/"\n',
        encoding="utf-8",
    )

    async def initialize():
        server = Server()
        try:
            server.init(config)
            assert server.webhook.server_console_pic == "https://example.com/avatars/AdminPlayer"
        finally:
            await server.shutdown()

    asyncio.run(initialize())


def test_tips_preserve_commas_unicode_and_newlines(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WEBHOOK_URL", "https://discord.com/api/webhooks/123456789012345678/test-tokentest-tokentest-tokentest-tokentest-tokentest-token")
    messages = ["日本語, comma", "一行目\n二行目", r"三行目\n四行目"]
    monkeypatch.setenv("TIPS_MESSAGES", json.dumps(messages, ensure_ascii=False))
    BotEnv.init()
    assert [normalize_message_newlines(tip) for tip in json.loads(BotEnv.TipsMessages.get())] == [
        "日本語, comma", "一行目\n二行目", "三行目\n四行目",
    ]


@pytest.mark.parametrize("value", ['["tip", 2]', '"tip"', 'not-json', '[]'])
def test_invalid_tips_report_setting_name(tmp_path, monkeypatch, value):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WEBHOOK_URL", "https://discord.com/api/webhooks/123456789012345678/test-tokentest-tokentest-tokentest-tokentest-tokentest-token")
    monkeypatch.setenv("TIPS_MESSAGES", value)
    with pytest.raises(ValueError, match="TIPS_MESSAGES"):
        BotEnv.init()


def test_invalid_webhook_does_not_expose_token(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WEBHOOK_URL", "https://example.com/private-token")
    with pytest.raises(ValueError, match="WEBHOOK_URL") as exc:
        BotEnv.init()
    assert "private-token" not in str(exc.value)


def test_newline_normalization_preserves_other_escapes():
    assert normalize_message_newlines(r"日本語\n\t\u3042") == "日本語\n" + r"\t\u3042"
    assert normalize_message_newlines(r"literal\\n") == r"literal\n"
    assert normalize_message_newlines("one\r\ntwo\nthree") == "one\ntwo\nthree"


def test_legacy_config_defaults_leave_japanese_conversion_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBHOOK_URL", "https://discord.com/api/webhooks/123456789012345678/" + "test-token" * 6)
    BotEnv.init(tmp_path / ".env")
    assert not BotEnv.JapanizeEnabled.getBool()
    assert BotEnv.JapanizeMode.get() == "auto"
    assert json.loads(BotEnv.JapanizeDictionary.get()) == {}
    assert json.loads(BotEnv.JapanizePublicChannels.get()) == []


@pytest.mark.parametrize("name,value", [
    ("JAPANIZE_ENABLED", "yes"), ("JAPANIZE_MODE", "online"),
    ("JAPANIZE_DICTIONARY", '[]'), ("JAPANIZE_DICTIONARY", '{"word": 1}'),
    ("JAPANIZE_PUBLIC_CHANNELS", '"global"'), ("JAPANIZE_PUBLIC_CHANNELS", '["Alice -> Bob"]'),
    ("JAPANIZE_SERVER_FORMAT", '{original}'),
])
def test_invalid_japanese_settings_report_only_the_setting_name(tmp_path, monkeypatch, name, value):
    monkeypatch.setenv("WEBHOOK_URL", "https://discord.com/api/webhooks/123456789012345678/" + "test-token" * 6)
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        BotEnv.init(tmp_path / ".env")
