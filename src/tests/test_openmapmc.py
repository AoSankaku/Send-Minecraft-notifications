import asyncio
import json

import pytest

from main import cli
from message.parser import LogParser
from server.server import Server


EVENT = "on_shared_waypoint_created"
MARKER = "OPENMAPMC_EVENT "
DATA = {
    "schema_version": 1, "event": "shared_waypoint_created",
    "waypoint_id": "b7a57784-31af-4c35-9953-bd0065a144e3",
    "creator_uuid": "ea16f807-6fa0-4d1a-89cb-7f1dc1125e92",
    "creator_name": "Alice", "name": "拠点",
    "dimension": "minecraft:overworld", "x": 123, "y": 64, "z": -456,
}
WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/" + "test-token-" * 6


class Templates:
    def translate(self, event):
        return "%waypoint-name% | %waypoint-dimension% | %waypoint-x%, %waypoint-y%, %waypoint-z%" if event == EVENT else "%player-message%"


def line(data=None, header="[12:34:56] [Server thread/INFO] [OpenMapDelta/]: "):
    return header + MARKER + json.dumps(DATA if data is None else data, ensure_ascii=False)


@pytest.mark.parametrize("header", [
    "[12:34:56] [Server thread/INFO]: ",
    "[15Oct2026 12:34:56.123] [Server thread/INFO] [OpenMapDelta/]: ",
    "[12:34:56] [Server thread/INFO] [OpenMapDelta]: ",
    "[12:34:56 INFO]: ",
    "2026-10-15 12:34:56 [INFO] ",
])
def test_shared_creation_event_extracts_creator_name_location_and_dimension(header):
    result = LogParser("", "", "", "", []).parse(line(header=header), Templates())
    assert result is not None
    assert result.event_id == EVENT
    assert result.playerId == "Alice"
    assert result.text == "拠点 | minecraft:overworld | 123, 64, -456"
    assert result.literal_text


@pytest.mark.parametrize("change", [
    {"event": "shared_waypoint_updated"}, {"event": "shared_waypoint_deleted"},
    {"schema_version": 2}, {"schema_version": True},
    {"waypoint_id": "invalid"}, {"creator_uuid": "invalid"},
    {"creator_name": "invalid name"}, {"name": ""}, {"name": " "},
    {"name": "a\nb"}, {"name": "a" * 257}, {"name": "\ud800"},
    {"dimension": "invalid dimension"}, {"dimension": ""},
    {"x": True}, {"x": "123"}, {"x": float("nan")}, {"z": float("inf")},
    {"x": 30000001}, {"y": -2049}, {"y": 4097},
])
def test_invalid_or_non_create_events_are_not_reinterpreted_as_other_notifications(change):
    assert LogParser("", "", "", "", []).parse(line(DATA | change), Templates()) is None


@pytest.mark.parametrize("body", [
    "not json", "[]", "null", '{"schema_version":1,"schema_version":1}',
    '{"name":"Alice joined the game"}', "{" * 10000,
])
def test_malformed_reserved_events_are_dropped(body):
    text = "[12:34:56] [Server thread/INFO]: " + MARKER + body
    assert LogParser("", "", "", "", []).parse(text, Templates()) is None


@pytest.mark.parametrize("header", [
    "[12:34:56] [Async Chat Thread/INFO]: ",
    "[12:34:56] [Server thread/INFO] [SomeOtherMod/]: ",
])
def test_untrusted_event_logger_or_chat_thread_is_not_forwarded(header):
    assert LogParser("", "", "", "", []).parse(line(header=header), Templates()) is None


def test_chat_and_say_cannot_impersonate_waypoint_events():
    parser = LogParser("", "", "", "", [])
    for prefix in ("<Alice> ", "[Server] ", "[CHAT] ", "[Not Secure] "):
        result = parser.parse(line(header="[12:34:56] [Server thread/INFO]: " + prefix), Templates())
        assert result is None or result.event_id != EVENT


def test_names_are_inserted_literally_without_recursive_placeholder_expansion():
    name = '「拠点」 §a %waypoint-x% %server-count% @everyone `x`'
    result = LogParser("", "", "", "", []).parse(line(DATA | {"name": name}), Templates())
    assert result is not None
    assert result.text.startswith(name + " | ")


def test_notifications_can_be_disabled():
    parser = LogParser("", "", "", "", [], openmapmc_waypoints=False)
    assert parser.parse(line(), Templates()) is None


def test_duplicate_json_keys_are_rejected_even_for_otherwise_valid_event():
    body = json.dumps(DATA)[:-1] + ',"name":"second"}'
    text = "[12:34:56] [Server thread/INFO]: " + MARKER + body
    assert LogParser("", "", "", "", []).parse(text, Templates()) is None


def test_config_validates_waypoint_notification_switch(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text(f'WEBHOOK_URL = "{WEBHOOK}"\nOPENMAPMC_WAYPOINT_NOTIFICATIONS = "yes"\n', encoding="utf-8")
    assert cli(["--config", str(config), "--check-config"]) == 1
    assert "OPENMAPMC_WAYPOINT_NOTIFICATIONS" in capsys.readouterr().err


def test_server_routes_waypoint_to_creator_and_preserves_name_tokens(tmp_path, monkeypatch):
    sent = []

    class Webhook:
        def __init__(self, *args, **kwargs):
            pass

        async def sendPlayerMessage(self, text, player):
            sent.append((text, player))

        async def sendServerMessage(self, text):
            pytest.fail("Waypoint must be sent as the creator")

        async def onClose(self):
            pass

    monkeypatch.setattr("server.server.DiscordWebhook", Webhook)
    config = tmp_path / "config.toml"
    config.write_text(f'WEBHOOK_URL = "{WEBHOOK}"\n', encoding="utf-8")

    async def exercise():
        server = Server()
        try:
            server.init(config)
            await server.on_line_added(line(DATA | {"name": "拠点 %server-count%"}))
            assert len(sent) == 1
            assert sent[0][1] == "Alice"
            assert "拠点 %server-count%" in sent[0][0]
            assert "minecraft:overworld" in sent[0][0]
            assert server.player_count == 0
        finally:
            await server.shutdown()

    asyncio.run(exercise())
