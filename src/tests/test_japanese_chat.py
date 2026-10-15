import asyncio
from unittest.mock import AsyncMock

import pytest

from message.chat_japanese import JapaneseChatFormatter, validate_server_format
from message.constant import EventIds
from message.i18n import I18n
from message.parser import LogParser, combine_chat_records
from server.server import Server


PREFIXES = [
    "[12:34:56] [Server thread/INFO]: ",
    "[12:34:56] [Async Chat Thread - #2/INFO]: ",
    "[12:34:56] [AsyncChat-3/INFO]: ",
    "[12:34:56] [Server thread/INFO] [minecraft/DedicatedServer]: ",
    "[15Oct2026 12:34:56.123] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: ",
    "[12:34:56 INFO]: ",
    "2013-10-15 12:34:56 [INFO] ",
]


def parser(public_channels=()):
    return LogParser("", "", "", "Restarting in 60 seconds!", [], public_channels=public_channels)


def translator():
    result = I18n()
    result.lang_data = {"ja_jp": {event.value: "`%player-message%`" for event in EventIds}}
    result.loaded_lang = ["ja_jp"]
    return result


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("marker", ["", "[Not Secure] ", "[CHAT] "])
def test_chat_metadata_across_server_log_layouts(prefix, marker):
    result = parser().parse(prefix + marker + "<Alice> konnichiha", translator())
    assert result is not None
    assert result.playerId == "Alice"
    assert result.chat_text == "konnichiha"
    assert result.chat_format == "`%player-message%`"
    assert result.text == "`konnichiha`"


def test_default_off_keeps_existing_output():
    formatter = JapaneseChatFormatter()
    assert formatter.format_message("konnichiha", "`%player-message%`") == "`konnichiha`"
    assert formatter.format_message("konnichiha (こんにちは)") == "konnichiha (こんにちは)"


def test_async_and_unsigned_chat_keep_their_configured_translation_keys():
    translations = translator()
    translations.lang_data["ja_jp"][EventIds.ON_SECURE_CHAT] = "async: %player-message%"
    translations.lang_data["ja_jp"][EventIds.ON_NON_SECURE_CHAT] = "unsigned: %player-message%"
    line = "[12:34:56] [Async Chat Thread - #2/INFO]: "
    assert parser().parse(line + "<Alice> hello", translations).text == "async: hello"
    assert parser().parse(line + "[Not Secure] <Alice> hello", translations).text == "unsigned: hello"


def test_auto_falls_back_to_offline_and_reuses_exact_server_results():
    formatter = JapaneseChatFormatter(enabled=True)
    assert formatter.format_message("konnichiha", "`%player-message%`") == "`konnichiha`\n↳ `こんにちは`"
    assert formatter.format_message("hou seki (宝石)") == "hou seki\n↳ 宝石"
    assert formatter.format_message("konnichiha\n→ 今日は") == "konnichiha\n↳ 今日は"
    assert formatter.format_message("こんにちは") == "こんにちは"


def test_local_mode_overrides_existing_server_conversion():
    formatter = JapaneseChatFormatter(enabled=True, mode="local")
    assert formatter.format_message("konnichiha (今日は)") == "konnichiha\n↳ こんにちは"
    assert formatter.format_message("konnichiha\n→ 今日は") == "konnichiha\n↳ こんにちは"


def test_server_mode_does_not_run_local_conversion():
    formatter = JapaneseChatFormatter(enabled=True, mode="server")
    assert formatter.format_message("konnichiha") == "konnichiha"
    assert formatter.format_message("konnichiha (こんにちは)") == "konnichiha\n↳ こんにちは"


def test_custom_server_format_is_literal_and_requires_both_fields():
    formatter = JapaneseChatFormatter(enabled=True, server_format="{original} => [{japanese}]")
    assert formatter.format_message("maikura => [マイクラ]") == "maikura\n↳ マイクラ"
    for value in ("{original}", "{original}{japanese}", "{original} {original} {japanese}", "{original} {other} {japanese}"):
        with pytest.raises(ValueError):
            validate_server_format(value)


def test_dictionary_is_used_only_for_local_conversion():
    formatter = JapaneseChatFormatter(enabled=True, dictionary={"maikura": "マイクラ"})
    assert formatter.format_message("maikura") == "maikura\n↳ マイクラ"
    assert formatter.format_message("maikura (Minecraft日本語)") == "maikura\n↳ Minecraft日本語"


def test_disabled_chat_template_does_not_gain_a_conversion_line():
    formatter = JapaneseChatFormatter(enabled=True)
    assert formatter.format_message("konnichiha", "") == ""
    assert formatter.format_message("konnichiha", "hidden") == "hidden"


def test_parenthesized_english_is_not_a_server_japanese_result():
    formatter = JapaneseChatFormatter(enabled=True, mode="server")
    assert formatter.format_message("hello (world)") == "hello (world)"


def test_lunachat_public_line_keeps_original_and_server_result():
    result = parser().parse("[12:34:56] [Async Chat Thread - #1/INFO]: Alice: konnichiha §6(こんにちは)", translator())
    assert result.playerId == "Alice"
    assert result.event_id == EventIds.ON_CHAT_FROM_LUNACHAT
    assert result.chat_text == "konnichiha (こんにちは)"
    assert JapaneseChatFormatter(enabled=True).format_message(result.chat_text, result.chat_format) == "`konnichiha`\n↳ `こんにちは`"


@pytest.mark.parametrize("body", [
    "[Alice -> Bob] konnichiha (秘密の挨拶)",
    "<Alice -> Bob> konnichiha (秘密の挨拶)",
    "[JP] 秘密の挨拶",
    "→ 秘密の挨拶",
    "[private]Alice: konnichiha (秘密の挨拶)",
    "[private] Alice: konnichiha (秘密の挨拶)",
    "[Team] <Alice> konnichiha (秘密の挨拶)",
    "[private] [Alice] konnichiha (秘密の挨拶)",
    "[private] Nick-Name: secret",
])
def test_unattributed_private_and_unapproved_channel_lines_are_not_forwarded(body):
    assert parser().parse(PREFIXES[0] + body, translator()) is None


def test_named_channel_requires_explicit_public_allowlist():
    line = PREFIXES[0] + "[global]Alice: konnichiha (こんにちは)"
    assert parser().parse(line, translator()) is None
    result = parser(["global"]).parse(line, translator())
    assert result.playerId == "Alice" and result.chat_text == "konnichiha (こんにちは)"


def test_colon_shaped_server_diagnostics_do_not_become_player_chat():
    assert parser().parse(PREFIXES[0] + "WEBHOOK_URL: private-token", translator()) is None


@pytest.mark.parametrize("message", ["<Alice> Hello", "Alice: Hello"])
def test_console_say_is_preserved_as_server_traffic(message):
    result = parser().parse(PREFIXES[0] + "[Server] " + message, translator())
    assert result.event_id == EventIds.ON_CONSOLE_CHAT
    assert result.playerId == "#server"
    assert result.chat_text is None
    assert result.text == f"`{message}`"


def test_tsuki_same_record_continuation_is_preserved_but_unrelated_system_line_is_not_attached():
    lines = [PREFIXES[0] + "<Alice> konnichiha\n", "→ こんにちは\n", PREFIXES[0] + "→ unrelated\n"]
    records = combine_chat_records(lines)
    assert records == [lines[0] + lines[1], lines[2]]
    result = parser().parse(records[0], translator())
    assert result.chat_text == "konnichiha\n→ こんにちは"
    assert parser().parse(records[1], translator()) is None
    assert combine_chat_records([PREFIXES[0] + "[Alice -> Bob] secret\n", "→ 秘密\n"]) == [
        PREFIXES[0] + "[Alice -> Bob] secret\n", "→ 秘密\n",
    ]


def test_server_integration_converts_only_actual_public_chat_without_network():
    async def run():
        server = Server()
        server.parser = parser()
        server.i18n = translator()
        server.chat_japanese = JapaneseChatFormatter(enabled=True)
        server.webhook = type("FakeWebhook", (), {"sendPlayerMessage": AsyncMock(), "sendServerMessage": AsyncMock()})()
        server.on_after_send = AsyncMock()
        await server.on_line_added(PREFIXES[0] + "<Alice> konnichiha")
        server.webhook.sendPlayerMessage.assert_awaited_once_with("`konnichiha`\n↳ `こんにちは`", "Alice")
        await server.on_line_added(PREFIXES[0] + "[JP] secret")
        assert server.webhook.sendPlayerMessage.await_count == 1
    asyncio.run(run())
