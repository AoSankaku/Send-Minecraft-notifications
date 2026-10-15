"""Exercise real configuration -> log parsing -> outbound webhook arguments."""

import asyncio
import json
import socket

import pytest

from main import cli
from message.locales import SUPPORTED_LOCALES
from server.server import Server
from utils.runtime import resource_path


WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/" + "test-token-" * 6


class RecordingWebhook:
    def __init__(self, *args, **kwargs):
        self.players = []
        self.system = []
        self.closed = False

    async def sendPlayerMessage(self, message, player):
        self.players.append((message, player))

    async def sendServerMessage(self, message):
        self.system.append(message)

    async def onClose(self):
        self.closed = True


@pytest.mark.parametrize("locale", list(SUPPORTED_LOCALES))
def test_configured_locale_reaches_player_notification_without_network(tmp_path, monkeypatch, locale):
    def no_network(*args, **kwargs):
        pytest.fail("The configuration and translation pipeline must be offline")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr("server.server.DiscordWebhook", RecordingWebhook)
    config = tmp_path / "config.toml"
    config.write_text(f'WEBHOOK_URL = "{WEBHOOK}"\nLANGUAGE = "{locale}"\n', encoding="utf-8")
    catalog = json.loads(resource_path("translations/minecraft.json").read_text(encoding="utf-8"))
    expected_title = catalog["versions"]["26.3"][locale]["advancements.story.mine_stone.title"]

    async def exercise():
        server = Server()
        try:
            server.init(config)
            await server.on_line_added("[12:34:56] [Server thread/INFO]: Alice has made the advancement [Stone Age]")
            await server.on_line_added("[12:34:57] [Server thread/INFO]: Alice has made the advancement [Unknown Mod Title]")
            assert len(server.webhook.players) == 2
            assert expected_title in server.webhook.players[0][0]
            assert server.webhook.players[0][1] == "Alice"
            assert "Unknown Mod Title" in server.webhook.players[1][0]
            assert not server.webhook.system
        finally:
            await server.shutdown()
        assert server.webhook.closed

    asyncio.run(exercise())


@pytest.mark.parametrize("setting", [
    'LANGUAGE = "unknown"',
    'ADVANCEMENT_TRANSLATION_ENABLED = "yes"',
    'ADVANCEMENT_DICTIONARY = { "Title" = 42 }',
    'ADVANCEMENT_DICTIONARY = { "Title" = "" }',
    'MINECRAFT_VERSION = "unknown-version"',
])
def test_check_config_rejects_invalid_locale_settings_without_sending(tmp_path, monkeypatch, capsys, setting):
    config = tmp_path / "config.toml"
    config.write_text(f'WEBHOOK_URL = "{WEBHOOK}"\n{setting}\n', encoding="utf-8")
    monkeypatch.setattr("server.server.DiscordWebhook", lambda *args, **kwargs: pytest.fail("must not connect"))
    assert cli(["--config", str(config), "--check-config"]) == 1
    assert setting.split(" =")[0] in capsys.readouterr().err


def test_frozen_bundle_loads_minecraft_dictionary_without_external_files(tmp_path, monkeypatch):
    import shutil
    import sys
    from message.advancements import AdvancementTranslator, _bundled_catalog

    bundle = tmp_path / "bundle"
    (bundle / "translations").mkdir(parents=True)
    shutil.copyfile(resource_path("translations/minecraft.json"), bundle / "translations" / "minecraft.json")
    _bundled_catalog.cache_clear()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    try:
        assert AdvancementTranslator("ja").translate("Stone Age") == "石器時代"
    finally:
        _bundled_catalog.cache_clear()


@pytest.mark.parametrize("verb,event_key,token", [
    ("made the advancement", "on_advancement_complete", "%advancement-name%"),
    ("reached the goal", "on_goal_complete", "%goal-name%"),
    ("completed the challenge", "on_challenge_complete", "%challenge-name%"),
    ("just earned the achievement", "on_achievements_complete_old", "%challenge-name%"),
])
def test_custom_and_unknown_titles_keep_literal_template_tokens(tmp_path, monkeypatch, verb, event_key, token):
    monkeypatch.setattr("server.server.DiscordWebhook", RecordingWebhook)
    config = tmp_path / "config.toml"
    config.write_text(
        f'WEBHOOK_URL = "{WEBHOOK}"\n'
        'ADVANCEMENT_DICTIONARY = { "Custom" = "Literal %server-count%" }\n',
        encoding="utf-8",
    )
    custom = tmp_path / "translations"
    custom.mkdir()
    (custom / "ja_jp.json").write_text(json.dumps({
        event_key: "Online %server-count%: " + token,
    }), encoding="utf-8")

    async def exercise():
        server = Server()
        try:
            server.init(config)
            server.player_count = 7
            for title in ("Custom", "Unknown %server-count%"):
                await server.on_line_added(f"[12:34:56] [Server thread/INFO]: Alice has {verb} [{title}]")
            assert server.webhook.players == [
                ("Online 7: Literal %server-count%", "Alice"),
                ("Online 7: Unknown %server-count%", "Alice"),
            ]
        finally:
            await server.shutdown()

    asyncio.run(exercise())
