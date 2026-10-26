import random
import logging
import time
import structlog
from structlog.stdlib import BoundLogger
from watchfiles import awatch
from os import path
import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit

from message.parser import LogParser, combine_chat_records
from message.chat_japanese import JapaneseChatFormatter
from message.webhook import DiscordWebhook
from message.advancements import AdvancementTranslator
from message.log_translations import load_log_translators
from message.model import MessageType
from message.constant import EventIds
from message.i18n import I18n
from utils.logutil import LogUtil
from handlers.secrets import BotEnv
from server.state import ServerState
from server.crash import CrashReporter, is_server_start_record
from server.script_state import ScriptState
from utils.runtime import default_config_path

class Server:
    def __init__(self, debug_mode: bool = False):
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(
                logging.INFO if not debug_mode else logging.DEBUG
            )
        )
        self.logger: BoundLogger = structlog.getLogger()
        self.state: ServerState = ServerState.STARTING
        self.script_state: ScriptState = ScriptState.RUNNING
        self.player_count: int = 0
        self.logutil: LogUtil = LogUtil()
        self.send_count: int = 0
        self.tips_messages: list[str] = []
        self.webhook: DiscordWebhook | None = None
        self.admin_webhook: DiscordWebhook | None = None
        self.crash_reporter: CrashReporter | None = None
        self.latest_log_path: Path | None = None
        self.parser: LogParser
        self.i18n: I18n
        self.advancement_translator: AdvancementTranslator | None = None
        self.death_translator = None
        self.chat_japanese = JapaneseChatFormatter()
        pass
    
    def init(self, config_path: Path | None = None):
        self.logger.info("Initializing now...")
        
        config_path = config_path or default_config_path()
        BotEnv.init(config_path)
        self.chat_japanese = JapaneseChatFormatter(
            enabled=BotEnv.JapanizeEnabled.getBool(), mode=BotEnv.JapanizeMode.get(),
            dictionary=json.loads(BotEnv.JapanizeDictionary.get()),
            server_format=BotEnv.JapanizeServerFormat.get(),
        )
        self.tips_messages = json.loads(BotEnv.TipsMessages.get())
        self.logger.info("Environment variables loaded.")
        
        locale = BotEnv.Language.get()
        self.i18n = I18n.for_config(config_path, locale)
        self.logger.info("Notification language loaded.", language=locale)
        self.advancement_translator, self.death_translator, mod_catalog = load_log_translators()
        if mod_catalog is not None:
            self.logger.info("MOD translation cache loaded.", reused=mod_catalog.cache_hits, parsed=mod_catalog.cache_misses)
            for warning in mod_catalog.warnings:
                self.logger.warning(warning)
        self.logger.info("Translator initialized.")
        
        self.webhook = DiscordWebhook(
            BotEnv.WebhookUrl.get(),
            BotEnv.PlayerIconApi.get(),
            BotEnv.SenderName.get(),
            BotEnv.SenderIcon.get(),
            server_icon_player=BotEnv.SenderIconPlayer.get(),
        )
        webhooks_by_url = {BotEnv.WebhookUrl.get(): self.webhook}
        admin_url = BotEnv.AdminWebhookUrl.get()
        if admin_url:
            self.admin_webhook = webhooks_by_url.get(admin_url)
            if self.admin_webhook is None:
                self.admin_webhook = DiscordWebhook(
                    admin_url,
                    BotEnv.PlayerIconApi.get(),
                    BotEnv.SenderName.get(),
                    BotEnv.SenderIcon.get(),
                    server_icon_player=BotEnv.SenderIconPlayer.get(),
                )
                webhooks_by_url[admin_url] = self.admin_webhook
        self.logger.info("Webhook initialized.")
        
        self.parser = LogParser(
            BotEnv.ServerStartMessage.get(),
            BotEnv.ServerStopMessage.get(),
            BotEnv.ServerRestartMessage.get(),
            BotEnv.RestartAnnouncementMessage.get(),
            json.loads(BotEnv.OtherIgnoreNames.get()),
            public_channels=json.loads(BotEnv.JapanizePublicChannels.get()),
            advancement_translator=self.advancement_translator,
            death_translator=self.death_translator,
            openmapmc_waypoints=BotEnv.OpenMapMcWaypoints.getBool(),
        )
        self.logger.info("LogParser initialized.")
        
        Path(BotEnv.TargetDir.get()).mkdir(parents=True, exist_ok=True)
        logfile_path = Path(BotEnv.TargetDir.get()) / BotEnv.TargetFile.get()
        self.latest_log_path = logfile_path
        self.logutil.load_to_prev(str(logfile_path))
        crash_reports_dir = BotEnv.CrashReportsDir.get().strip()
        if crash_reports_dir:
            configured_crash_dir = Path(crash_reports_dir)
            if not configured_crash_dir.is_absolute():
                configured_crash_dir = Path(config_path).absolute().parent / configured_crash_dir
        else:
            configured_crash_dir = Path(BotEnv.TargetDir.get()).parent / "crash-reports"
        webhook_secrets = []
        for configured_url in (BotEnv.WebhookUrl.get(), admin_url):
            if configured_url:
                webhook_secrets.append(configured_url)
                webhook_secrets.append(urlsplit(configured_url).path.rstrip("/").rsplit("/", 1)[-1])
        self.crash_reporter = CrashReporter(
            crash_reports_dir=configured_crash_dir,
            latest_log_path=logfile_path,
            enabled=BotEnv.CrashDetectionEnabled.getBool(),
            upload_enabled=BotEnv.CrashReportUploadEnabled.getBool(),
            server_pid=int(BotEnv.ServerPid.get()),
            alert_targets=json.loads(BotEnv.CrashAlertTargets.get()),
            report_targets=json.loads(BotEnv.CrashReportTargets.get()),
            crash_message=BotEnv.CrashMessage.get(),
            translate=lambda event: self.i18n.translate(EventIds(event)),
            send_message=self._send_crash_notification,
            secrets=tuple(webhook_secrets),
            home_paths=(str(Path.home()),),
        )
        self.logger.info("Logfile loaded.")
        
        self.logger.info("Initialization completed!")
        self.logger.info("Press Ctrl+C to shut down the script")
    
    async def shutdown(self):
        if self.script_state != ScriptState.CRASHED:
            self.logger.info("Gracefully shutting down...")
        if self.crash_reporter:
            await self.crash_reporter.close()
        webhooks = []
        for webhook in (self.webhook, self.admin_webhook):
            if webhook is not None and all(webhook is not existing for existing in webhooks):
                webhooks.append(webhook)
        if webhooks:
            await asyncio.gather(
                *(webhook.onClose() for webhook in webhooks),
                return_exceptions=True,
            )
        self.logger.info("See you!")

    async def _send_crash_notification(self, message: str, targets):
        destinations = {
            "main": self.webhook,
            "admin": self.admin_webhook,
        }
        selected = []
        seen = set()
        for target in targets:
            webhook = destinations.get(target)
            if webhook is None or id(webhook) in seen:
                continue
            seen.add(id(webhook))
            selected.append((target, webhook))

        async def send(target, webhook):
            try:
                await asyncio.wait_for(webhook.sendServerMessage(message), timeout=10)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Do not log webhook URLs, payloads, or remote error details.
                self.logger.warning("Crash notification delivery failed", destination=target)

        await asyncio.gather(*(send(target, webhook) for target, webhook in selected))

    async def poll_crashes(self, *, now: float | None = None) -> int:
        if self.crash_reporter is None:
            return 0
        count = await self.crash_reporter.poll(now=now)
        if self.crash_reporter.has_crashed:
            self.state = ServerState.CRASHED
        await self.crash_reporter.drain_alerts()
        return count

    async def crash(self):
        self.script_state = ScriptState.CRASHED
    
    async def listen_file_change(self):
        try:
            async for changes in awatch(
                BotEnv.TargetDir.get(), recursive=True,
                yield_on_timeout=True, rust_timeout=1000,
            ):
                now = time.monotonic()
                for change in changes:
                    filepath = change[1]
                    try:
                        matches_latest = (
                            self.latest_log_path is not None
                            and Path(filepath).resolve() == self.latest_log_path.resolve()
                        )
                    except OSError:
                        matches_latest = False
                    if matches_latest:
                        try:
                            new_lines = self.logutil.get_log_diff(filepath)
                        except OSError:
                            continue
                        for line in combine_chat_records(new_lines):
                            await self.on_line_added(line, now=now)
                await self.poll_crashes(now=now)
        except asyncio.exceptions.CancelledError:
            pass
    
    async def on_line_added(self, line: str, *, now: float | None = None):
        if self.crash_reporter is not None:
            if is_server_start_record(line):
                self.crash_reporter.on_server_start(now=now)
                if self.state == ServerState.CRASHED:
                    self.state = ServerState.STARTING
            if self.crash_reporter.observe_line(line, now=now):
                self.state = ServerState.CRASHED
            await self.crash_reporter.drain_alerts()
        result = self.parser.parse(line, self.i18n)
        if result == None:
            self.logger.debug("Ignore line", line=line)
            return

        if not self.on_event(result.event_id, now=now):
            return

        if result.player_count is not None:
            self.player_count = result.player_count
            self.round_player_count()

        if result.msg_type == MessageType.Unknown:
            self.logger.warn("Unknown message happened!", result=result)
            return
        
        if result.chat_text is not None:
            result.text = self.chat_japanese.format_message(result.chat_text, result.chat_format or "")
            if not result.text:
                return
        if (
            result.milestone_title is not None
            and result.milestone_template is not None
            and result.milestone_placeholder is not None
        ):
            result.text = self.replace_additional_data(result.milestone_template).replace(
                result.milestone_placeholder, result.milestone_title
            )
        elif not result.literal_text:
            result.text = self.replace_additional_data(result.text)
        
        self.logger.debug("Sending", message=result.text)
        match result.msg_type:
            case MessageType.Player:
                await self.webhook.sendPlayerMessage(result.text, result.playerId or "Invalid userid")
            case MessageType.Server | MessageType.System:
                await self.webhook.sendServerMessage(result.text)
        
        await self.on_after_send(result.event_id)
    
    def replace_additional_data(self, msg: str) -> str:
        return msg.replace("%server-count%", str(self.player_count))
    
    def round_player_count(self):
        if self.player_count < 0:
            self.player_count = 0
    
    def on_event(self, event_id: str, *, now: float | None = None) -> bool:
        # Returns False if the event should be suppressed
        if event_id == EventIds.ON_SERVER_STOP:
            if self.crash_reporter is not None:
                self.crash_reporter.on_clean_stop()
            if self.state == ServerState.CRASHED:
                self.logger.debug("Suppressed normal server stop after a crash")
                return False
            if self.state == ServerState.RESTARTING:
                self.logger.debug("Suppressed server stop message due to server restart")
                return False
            if self.state == ServerState.STOPPED:
                self.logger.debug("Suppressed duplicate server stop message")
                return False
            self.state = ServerState.STOPPED

        match event_id:
            case EventIds.ON_JOIN:
                self.round_player_count()
                self.player_count += 1
                self.send_count = 0
            case EventIds.ON_LEFT:
                self.player_count -= 1
                self.round_player_count()
                self.send_count = 0
            case EventIds.ON_SERVER_START:
                self.player_count = 0
                self.state = ServerState.STARTED
                if self.crash_reporter is not None:
                    self.crash_reporter.on_server_start(now=now)
            case EventIds.ON_SERVER_RESTART:
                self.state = ServerState.RESTARTING
        
        return True
    
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
            await self.webhook.sendServerMessage(BotEnv.TipsPrefix.get() + random.choice(self.tips_messages))
        self.send_count += 1
