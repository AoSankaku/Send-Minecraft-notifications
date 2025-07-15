from discord import Webhook, HTTPException, NotFound, Forbidden
import aiohttp
from urllib.parse import urljoin
import asyncio
import structlog


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
        self.logger: structlog.stdlib.BoundLogger = structlog.get_logger()

    async def _send_with_retry(self, *args, **kwargs):
        max_retries = 5
        retry_delay = 10  # seconds
        msg = args[0]

        for attempt in range(max_retries):
            try:
                await self.webhook.send(*args, **kwargs)
                return  # Success
            except HTTPException as e:
                self.logger.warn(
                    "Discord API request failed, retrying...",
                    status=e.status,
                    code=e.code,
                    text=e.text,
                    msg=msg,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                )
                raise
            except TypeError or ValueError as e:
                self.logger.warn(
                    "Error happened about embed processing...",
                    text=str(e),
                    msg=msg,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                )
                raise
            except Exception:
                self.logger.error("An unexpected error occurred during webhook send", exc_info=True)
                
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                self.logger.error("All retries failed. Crashing the script.")
                await self.onClose()
                raise RuntimeError(
                    f"Discord API request failed after {max_retries} retries."
                )

    async def onClose(self):
        await self.aiohttp_session.close()

    async def sendMessage(self, msg: str):
        await self._send_with_retry(msg, tts=False)

    async def sendPlayerMessage(self, msg: str, userid: str):
        await self._send_with_retry(
            msg,
            avatar_url=urljoin(self.avatar_url_base, userid),
            username=userid,
            tts=False,
        )

    async def sendServerMessage(self, msg: str):
        await self._send_with_retry(
            msg,
            username=self.server_webhook_name,
            avatar_url=self.server_console_pic,
            tts=False,
        )
