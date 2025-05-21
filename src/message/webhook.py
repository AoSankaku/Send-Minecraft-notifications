from discord import Webhook
import aiohttp


class DiscordWebhook:
    def __init__(
        self,
        webhook_url: str,
        avatar_url_base: str,
        server_webhook_name: str,
        server_console_pic: str,
    ):
        self.webhook_url: str = webhook_url
        self.aiohttp_session = aiohttp.ClientSession()
        self.webhook: Webhook = Webhook.from_url(
            self.webhook_url, session=self.aiohttp_session
        )
        self.avatar_url_base: str = avatar_url_base
        self.server_webhook_name = server_webhook_name
        self.server_console_pic = server_console_pic

    async def onClose(self):
        await self.aiohttp_session.close()

    async def sendMessage(self, msg: str):
        await self.webhook.send(msg, tts=False)

    async def sendPlayerMessage(self, msg: str, userid: str):
        await self.webhook.send(
            msg, avatar_url=self.avatar_url_base + userid, username=userid, tts=False
        )

    async def sendServerMessage(self, msg: str):
        await self.webhook.send(
            msg,
            username=self.server_webhook_name,
            avatar_url=self.server_console_pic,
            tts=False,
        )
