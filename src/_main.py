import time
import pathlib
import asyncio
import structlog
from structlog.stdlib import BoundLogger
from watchfiles import awatch
from os import path

from message.parser import LogParser
from message.webhook import DiscordWebhook
from message.model import MessageType
from message.i18n import I18n
from utils.logutil import LogUtil
from handlers.secrets import BotEnv

logger: BoundLogger = structlog.getLogger()

default_server_console_pic = "https://aosankaku.github.io/Send-Minecraft-notifications/img/server.drawio.png"


async def main():
    logger.info("Send Minecraft Notifications v1.0.0")
    
    logger.info("Initializing now...")
    
    BotEnv.init()
    
    logger.info("Loading translations...")
    i18n = I18n()
    i18n.load_translation("ja_jp", "translations/ja_jp.json")
    logger.info("Translations loaded!")
    
    webhook = DiscordWebhook(
        BotEnv.WebhookUrl.get(),
        BotEnv.PlayerIconApi.get(),
        default_server_console_pic
    )
    
    parser = LogParser(
        BotEnv.ServerStartMessage.get(),
        BotEnv.ServerStopMessage.get(),
        BotEnv.ServerRestartMessage.get(),
        BotEnv.RestartAnnouncementMessage.get(),
        BotEnv.OtherIgnoreNames.get()
    )
    
    async def on_line_added(line: str):
        result = parser.parse(line, i18n)
        if result == None:
            logger.debug("Ignore line", line=line)
            return
        logger.info("Sending", message=result.text)
        match result.msg_type:
            case MessageType.Player:
                await webhook.sendPlayerMessage(result.text, result.playerId)
            case MessageType.Server | MessageType.System:
                await webhook.sendServerMessage(result.text)
            case MessageType.Unknown:
                logger.warn("Unknown message happened!", result=result)
    
    logutil = LogUtil()
    logutil.load_to_prev(path.join(BotEnv.TargetDir.get(), BotEnv.TargetFile.get()))
    
    logger.info("Initialization completed!")
    
    logger.info("Listening file changes...")
    try:
        async for changes in awatch(BotEnv.TargetDir.get(), recursive=True):
            for change in changes:
                filepath = change[1]
                filename = path.basename(filepath)
                if filename == BotEnv.TargetFile.get():
                    for line in logutil.get_log_diff(filepath):
                        await on_line_added(line)
    except KeyboardInterrupt:
        logger.info("Ctrl-C detected!")
    logger.info("Shutting down now...")
    
    logger.info("See you!")

if __name__ == "__main__":
    asyncio.run(main())