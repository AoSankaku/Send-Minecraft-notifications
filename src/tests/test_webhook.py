import asyncio
from unittest.mock import AsyncMock

import pytest
from discord import AllowedMentions, Webhook
from discord.webhook.async_ import AsyncWebhookAdapter

from message.webhook import DiscordWebhook


@pytest.mark.parametrize(
    "icon_url, icon_player, expected_avatar",
    [
        ("", "", "https://raw.githubusercontent.com/AoSankaku/Send-Minecraft-notifications/main/assets/info_icon_dot.png"),
        ("", "AdminPlayer", "https://example.com/avatars/AdminPlayer"),
        ("https://example.com/custom.png", "", "https://example.com/custom.png"),
        ("https://example.com/custom.png", "AdminPlayer", "https://example.com/custom.png"),
    ],
)
def test_server_icon_selection_is_independent_of_player_messages(
    monkeypatch, icon_url, icon_player, expected_avatar
):
    execute = AsyncMock(return_value=None)
    monkeypatch.setattr(AsyncWebhookAdapter, "execute_webhook", execute)

    async def send():
        webhook = DiscordWebhook(
            "https://discord.com/api/webhooks/123456789012345678/test-tokentest-tokentest-tokentest-tokentest-tokentest-token",
            "https://example.com/avatars/", "Server", icon_url,
            server_icon_player=icon_player,
        )
        try:
            await webhook.sendServerMessage("Server online")
            await webhook.sendPlayerMessage("Player chat", "ChatPlayer")
            await webhook.sendServerMessage("Server notification")
        finally:
            await webhook.onClose()

    asyncio.run(send())
    payloads = [call.kwargs["payload"] for call in execute.call_args_list]
    assert [payload["avatar_url"] for payload in payloads] == [
        expected_avatar, "https://example.com/avatars/ChatPlayer", expected_avatar,
    ]
    assert [payload["username"] for payload in payloads] == ["Server", "ChatPlayer", "Server"]
    assert all(payload["allowed_mentions"] == {"parse": []} for payload in payloads)


@pytest.mark.parametrize("method", ["sendMessage", "sendPlayerMessage", "sendServerMessage"])
def test_all_notifications_disable_mentions_in_api_payload(monkeypatch, method):
    execute = AsyncMock(return_value=None)
    monkeypatch.setattr(AsyncWebhookAdapter, "execute_webhook", execute)
    content = "``` @everyone @here <@123456789012345678> <@!123456789012345678> <@&123456789012345678> ```"

    async def send():
        webhook = DiscordWebhook(
            "https://discord.com/api/webhooks/123456789012345678/test-tokentest-tokentest-tokentest-tokentest-tokentest-token",
            "https://example.com/avatars/", "Server", "",
        )
        try:
            args = (content, "Player") if method == "sendPlayerMessage" else (content,)
            await getattr(webhook, method)(*args)
        finally:
            await webhook.onClose()

    asyncio.run(send())
    payload = execute.call_args.kwargs["payload"]
    assert payload["content"] == content
    assert payload["allowed_mentions"] == {"parse": []}


def test_retry_cannot_reenable_mentions(monkeypatch):
    send_mock = AsyncMock(side_effect=[OSError("offline"), None])
    monkeypatch.setattr(Webhook, "send", send_mock)
    async def send():
        webhook = DiscordWebhook(
            "https://discord.com/api/webhooks/123456789012345678/test-tokentest-tokentest-tokentest-tokentest-tokentest-token",
            "", "Server", "",
        )
        monkeypatch.setattr("message.webhook.asyncio.sleep", AsyncMock())
        try:
            await webhook._send_with_retry("``` @everyone", allowed_mentions=AllowedMentions.all())
            assert send_mock.await_count == 2
            for call in send_mock.await_args_list:
                assert call.kwargs["allowed_mentions"].to_dict() == {"parse": []}
        finally:
            await webhook.onClose()

    asyncio.run(send())
