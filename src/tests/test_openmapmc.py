import asyncio
import json

import pytest

from main import cli
from message.parser import LogParser
from server.server import Server


EVENT = "on_shared_waypoint_created"
OPERATIONS = ("created", "updated", "deleted")
EVENTS = tuple(f"on_shared_waypoint_{operation}" for operation in OPERATIONS)
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
        return "%waypoint-name% | %waypoint-dimension% | %waypoint-x%, %waypoint-y%, %waypoint-z%" if event in EVENTS else "%player-message%"


def event_data(operation):
    data = DATA | {"event": f"shared_waypoint_{operation}"}
    if operation != "created":
        data |= {"actor_uuid": "9530c75b-f8a1-4cfa-b13b-4209b1edc6b0", "actor_name": "Bob"}
    return data


def line(data=None, header="[12:34:56] [Server thread/INFO] [OpenMapDelta/]: "):
    return header + MARKER + json.dumps(DATA if data is None else data, ensure_ascii=False)


@pytest.mark.parametrize("header", [
    "[12:34:56] [Server thread/INFO]: ",
    "[15Oct2026 12:34:56.123] [Server thread/INFO] [OpenMapDelta/]: ",
    "[12:34:56] [Server thread/INFO] [OpenMapDelta]: ",
    "[12:34:56 INFO]: ",
    "2026-10-15 12:34:56 [INFO] ",
])
@pytest.mark.parametrize("operation", OPERATIONS)
def test_shared_event_extracts_actor_name_location_and_dimension(header, operation):
    result = LogParser("", "", "", "", []).parse(line(event_data(operation), header=header), Templates())
    assert result is not None
    assert result.event_id == f"on_shared_waypoint_{operation}"
    assert result.playerId == ("Alice" if operation == "created" else "Bob")
    assert result.text == "拠点 | minecraft:overworld | 123, 64, -456"
    assert result.literal_text


@pytest.mark.parametrize("change", [
    {"event": "shared_waypoint_unknown"}, {"event": []}, {"event": {}},
    {"schema_version": 2}, {"schema_version": True},
    {"waypoint_id": "invalid"}, {"creator_uuid": "invalid"},
    {"creator_name": "invalid name"}, {"name": ""}, {"name": " "},
    {"name": "a\nb"}, {"name": "a" * 257}, {"name": "\ud800"},
    {"dimension": "invalid dimension"}, {"dimension": ""},
    {"x": True}, {"x": "123"}, {"x": float("nan")}, {"z": float("inf")},
    {"x": 30000001}, {"y": -2049}, {"y": 4097},
])
def test_invalid_or_unknown_events_are_not_reinterpreted_as_other_notifications(change):
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
@pytest.mark.parametrize("operation", OPERATIONS)
def test_untrusted_event_logger_or_chat_thread_is_not_forwarded(header, operation):
    assert LogParser("", "", "", "", []).parse(line(event_data(operation), header=header), Templates()) is None


@pytest.mark.parametrize("operation", OPERATIONS)
def test_chat_and_say_cannot_impersonate_waypoint_events(operation):
    parser = LogParser("", "", "", "", [])
    for prefix in ("<Alice> ", "[Server] ", "[CHAT] ", "[Not Secure] "):
        result = parser.parse(line(event_data(operation), header="[12:34:56] [Server thread/INFO]: " + prefix), Templates())
        assert result is None or result.event_id not in EVENTS


def test_names_are_inserted_literally_without_recursive_placeholder_expansion():
    name = '「拠点」 §a %waypoint-x% %server-count% @everyone `x`'
    result = LogParser("", "", "", "", []).parse(line(DATA | {"name": name}), Templates())
    assert result is not None
    assert result.text.startswith(name + " | ")


@pytest.mark.parametrize("operation", OPERATIONS)
def test_notifications_can_be_disabled(operation):
    parser = LogParser("", "", "", "", [], openmapmc_waypoints=False)
    assert parser.parse(line(event_data(operation)), Templates()) is None


@pytest.mark.parametrize("operation", ("updated", "deleted"))
def test_mutations_use_actual_actor_instead_of_waypoint_owner(operation):
    result = LogParser("", "", "", "", []).parse(line(event_data(operation)), Templates())
    assert result is not None
    assert result.event_id == f"on_shared_waypoint_{operation}"
    assert result.playerId == "Bob"
    assert result.text == "拠点 | minecraft:overworld | 123, 64, -456"
    assert result.literal_text


@pytest.mark.parametrize("operation", ("updated", "deleted"))
@pytest.mark.parametrize("change", [
    {"actor_uuid": None}, {"actor_uuid": "invalid"},
    {"actor_name": None}, {"actor_name": "invalid name"}, {"actor_name": ""},
    {"creator_uuid": "invalid"}, {"creator_name": "invalid name"},
    {"name": "a\nb"}, {"x": True},
])
def test_mutations_validate_actor_owner_and_waypoint(operation, change):
    assert LogParser("", "", "", "", []).parse(line(event_data(operation) | change), Templates()) is None


@pytest.mark.parametrize("operation", ("updated", "deleted"))
def test_mutations_without_actor_do_not_fall_back_to_owner(operation):
    data = DATA | {"event": f"shared_waypoint_{operation}"}
    assert LogParser("", "", "", "", []).parse(line(data), Templates()) is None


@pytest.mark.parametrize("operation", OPERATIONS)
def test_each_operation_selects_its_own_translation(operation):
    class OperationTemplates:
        def translate(self, event):
            return event + " %waypoint-name%"

    result = LogParser("", "", "", "", []).parse(line(event_data(operation)), OperationTemplates())
    assert result is not None
    assert result.text == f"on_shared_waypoint_{operation} 拠点"


@pytest.mark.parametrize("operation, word", [("created", "Created"), ("updated", "Updated"), ("deleted", "Deleted")])
def test_default_translation_describes_operation(operation, word):
    result = LogParser("", "", "", "", []).parse(line(event_data(operation)))
    assert result is not None
    assert word in result.text
    assert "拠点" in result.text


@pytest.mark.parametrize("operation", OPERATIONS)
def test_empty_custom_translation_disables_that_event(operation):
    class EmptyTemplate:
        def translate(self, event):
            return ""

    assert LogParser("", "", "", "", []).parse(line(event_data(operation)), EmptyTemplate()) is None


def test_duplicate_json_keys_are_rejected_even_for_otherwise_valid_event():
    body = json.dumps(DATA)[:-1] + ',"name":"second"}'
    text = "[12:34:56] [Server thread/INFO]: " + MARKER + body
    assert LogParser("", "", "", "", []).parse(text, Templates()) is None


def test_config_validates_waypoint_notification_switch(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text(f'WEBHOOK_URL = "{WEBHOOK}"\nOPENMAPMC_WAYPOINT_NOTIFICATIONS = "yes"\n', encoding="utf-8")
    assert cli(["--config", str(config), "--check-config"]) == 1
    assert "OPENMAPMC_WAYPOINT_NOTIFICATIONS" in capsys.readouterr().err


@pytest.mark.parametrize("operation", OPERATIONS)
def test_server_routes_waypoint_to_actor_and_preserves_name_tokens(operation, tmp_path, monkeypatch):
    sent = []

    class Webhook:
        def __init__(self, *args, **kwargs):
            pass

        async def sendPlayerMessage(self, text, player):
            sent.append((text, player))

        async def sendServerMessage(self, text):
            pytest.fail("Waypoint must be sent as the operation actor")

        async def onClose(self):
            pass

    monkeypatch.setattr("server.server.DiscordWebhook", Webhook)
    config = tmp_path / "config.toml"
    config.write_text(f'WEBHOOK_URL = "{WEBHOOK}"\n', encoding="utf-8")

    async def exercise():
        server = Server()
        try:
            server.init(config)
            await server.on_line_added(line(event_data(operation) | {"name": "拠点 %server-count%"}))
            assert len(sent) == 1
            assert sent[0][1] == ("Alice" if operation == "created" else "Bob")
            assert "拠点 %server-count%" in sent[0][0]
            assert "minecraft:overworld" in sent[0][0]
            assert server.player_count == 0
        finally:
            await server.shutdown()

    asyncio.run(exercise())
