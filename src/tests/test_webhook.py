import asyncio
from unittest.mock import AsyncMock

import pytest
from discord import AllowedMentions, Webhook
from discord.webhook.async_ import AsyncWebhookAdapter

from message.webhook import DiscordWebhook


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
