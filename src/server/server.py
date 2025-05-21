import random
import logging
import structlog
from structlog.stdlib import BoundLogger
from watchfiles import awatch
from os import path

from message.parser import LogParser
from message.webhook import DiscordWebhook
from message.model import MessageType
from message.constant import EventIds
from message.i18n import I18n
from utils.logutil import LogUtil
from handlers.secrets import BotEnv
from server.state import ServerState

class Server:
    def __init__(self, debug_mode: bool = False):
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(
                logging.INFO if not debug_mode else logging.DEBUG
            )
        )
        self.logger: BoundLogger = structlog.getLogger()
        self.state: ServerState = ServerState.STARTING
        self.player_count: int = 0
        self.logutil: LogUtil = LogUtil()
        self.send_count: int = 0
        self.tips_messages: list[str] = []
        self.webhook: DiscordWebhook
        self.parser: LogParser
        self.i18n: I18n
        pass
    
    def init(self):
        self.logger.info("Initializing now...")
        
        BotEnv.init()
        for _m in BotEnv.TipsMessages.get()[1:-1].split(","):
            self.tips_messages.append(_m[1:-1])
        self.logger.info("Environment variables loaded.")
        
        self.i18n = I18n()
        self.logger.info("Loading ja_jp lang...")
        self.i18n.load_translation("ja_jp", "translations/ja_jp.json")
        self.logger.info("Translator initialized.")
        
        self.webhook = DiscordWebhook(
            BotEnv.WebhookUrl.get(),
            BotEnv.PlayerIconApi.get(),
            BotEnv.DefaultServerConsolePic.get()
        )
        self.logger.info("Webhook initialized.")
        
        self.parser = LogParser(
            BotEnv.ServerStartMessage.get(),
            BotEnv.ServerStopMessage.get(),
            BotEnv.ServerRestartMessage.get(),
            BotEnv.RestartAnnouncementMessage.get(),
            BotEnv.OtherIgnoreNames.get()
        )
        self.logger.info("LogParser initialized.")
        
        logfile_path = path.join(BotEnv.TargetDir.get(), BotEnv.TargetFile.get())
        self.logutil.load_to_prev(logfile_path)
        self.logger.info("Logfile loaded.")
        
        self.logger.info("Initialization completed!")
    
    async def shutdown(self):
        self.logger.info("Shutting down now...")
        
        self.logger.info("See you!")
    
    async def listen_file_change(self):
        try:
            async for changes in awatch(BotEnv.TargetDir.get(), recursive=True):
                for change in changes:
                    filepath = change[1]
                    filename = path.basename(filepath)
                    if filename == BotEnv.TargetFile.get():
                        for line in self.logutil.get_log_diff(filepath):
                            await self.on_line_added(line)
        except KeyboardInterrupt:
            self.logger.info("Ctrl-C detected!")
    
    async def on_line_added(self, line: str):
        result = self.parser.parse(line, self.i18n)
        if result == None:
            self.logger.debug("Ignore line", line=line)
            return

        if result.msg_type == MessageType.Unknown:
            self.logger.warn("Unknown message happened!", result=result)
            return
        
        self.on_event(result.event_id)
        result.text = self.replace_additional_data(result.text)
        
        self.logger.debug("Sending", message=result.text)
        match result.msg_type:
            case MessageType.Player:
                await self.webhook.sendPlayerMessage(result.text, result.playerId)
            case MessageType.Server | MessageType.System:
                await self.webhook.sendServerMessage(result.text)
        
        await self.on_after_send(result.event_id)
    
    def replace_additional_data(self, msg: str) -> str:
        return msg.replace("%server-count%", str(self.player_count))
    
    def round_player_count(self):
        if self.player_count < 0:
            self.player_count = 0
    
    def on_event(self, event_id: str):
        match event_id:
            case EventIds.ON_JOIN:
                self.round_player_count()
                self.player_count += 1
            case EventIds.ON_LEFT:
                self.player_count -= 1
                self.round_player_count()
            case EventIds.ON_SERVER_START:
                self.player_count = 0
    
    async def on_after_send(self, event_id: str):
        if self.send_count >= 16:
            self.send_count = 0
            msg = self.i18n.translate(EventIds.PLAYER_COUNT_NOTIFY)
            if msg == None:
                self.logger.warn(f"Failed to send player count notify because of translation missing (key:{EventIds.PLAYER_COUNT_NOTIFY})")
            else:
                msg = self.replace_additional_data(msg)
                await self.webhook.sendServerMessage(msg)
        if self.send_count%8 == 0 and self.send_count > 0:
            await self.webhook.sendServerMessage(random.choice(self.tips_messages))
        self.send_count += 1