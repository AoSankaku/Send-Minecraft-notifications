import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from enum import StrEnum
from typing import Self

from utils.config import TEMPLATE_FILENAME, load_config_values
from utils.runtime import default_config_path, resource_path
from message.chat_japanese import validate_server_format
from message.locales import normalize_locale
from message.advancements import validate_dictionary


def _is_bool_str(s: str) -> bool:
    _lower = s.lower()
    return _lower == "true" or _lower == "false"


_env_data: dict[str, str] = {}


def _loadEnvWithValidate(name: Self, values: dict[str, str | None]):
    # Get value from os enriron
    _v = values.get(name)

    if _v is None:
        _default = _get_default(name)
        if _default is None:
            # If default value was not presented.
            raise ValueError(f"Missing setting: {name.value}")
        else:
            print(f"[Warn] Fallback to default value. name:{name}")
            _v = _default

    # Validation
    _v = _validate_env(name, _v)
    if _v is None:
        raise ValueError(f"Invalid setting: {name.value}")

    # Store env value
    _env_data[name.value] = _v


def _validate_env(name: Self, value: str) -> str | None:
    match name:
        case BotEnv.WebhookUrl:
            try:
                url = urlsplit(value)
            except ValueError:
                return None
            if (
                url.scheme != "https"
                or url.netloc not in (
                    "discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com",
                    "ptb.discordapp.com", "canary.discordapp.com",
                )
                or not re.fullmatch(r"/api/webhooks/[0-9]{17,20}/[A-Za-z0-9._-]{60,}", url.path)
            ):
                return None
        case BotEnv.KillAfterClosed | BotEnv.JapanizeEnabled | BotEnv.AdvancementTranslationEnabled | BotEnv.OpenMapMcWaypoints:
            if not _is_bool_str(value):
                return None
        case BotEnv.EmbedMode:
            if not _is_bool_str(value):
                return None
        case BotEnv.JapanizeMode:
            return value.casefold() if value.casefold() in {"auto", "local", "server"} else None
        case BotEnv.Language:
            try:
                return normalize_locale(value)
            except ValueError:
                return None
        case BotEnv.AdvancementDictionary:
            try:
                validate_dictionary(json.loads(value))
            except (TypeError, ValueError):
                return None
        case BotEnv.TranslationCacheDir:
            if not value.strip():
                return None
        case BotEnv.JapanizeDictionary:
            try:
                dictionary = json.loads(value)
            except (TypeError, ValueError):
                return None
            if not isinstance(dictionary, dict) or len(dictionary) > 256 or not all(
                isinstance(key, str) and re.fullmatch(r"[A-Za-z][A-Za-z' -]{0,127}", key)
                and isinstance(replacement, str) and 0 < len(replacement) <= 1024
                for key, replacement in dictionary.items()
            ):
                return None
        case BotEnv.JapanizePublicChannels:
            try:
                channels = json.loads(value)
            except (TypeError, ValueError):
                return None
            if not isinstance(channels, list) or len(channels) > 64 or not all(
                isinstance(channel, str) and re.fullmatch(r"[^\[\]\r\n]{1,64}", channel)
                and not any(marker in channel for marker in ("->", "→", "»"))
                for channel in channels
            ):
                return None
        case BotEnv.JapanizeServerFormat:
            try:
                return validate_server_format(value)
            except ValueError:
                return None
        case BotEnv.TipsMessages:
            try:
                tips = json.loads(value)
            except (ValueError, TypeError):
                return None
            if not isinstance(tips, list) or not tips or not all(isinstance(tip, str) for tip in tips):
                return None
    # finish
    return value


def _get_default(name: Self) -> str | None:
    match name:
        case BotEnv.TipsPrefix:
            return ""
    return None


class BotEnv(StrEnum):
    WebhookUrl = "WEBHOOK_URL"
    TargetDir = "TARGET_DIR"
    TargetFile = "TARGET_FILE"
    PluginDir = "PLUGIN_DIR"
    OtherIgnoreNames = "IGNORE_NAMES"
    KillAfterClosed = "KILL_AFTER_CLOSED"
    
    # Webhook
    SenderName = "SENDER_NAME"
    SenderIcon = "SENDER_ICON"
    SenderIconPlayer = "SENDER_ICON_PLAYER"

    # Server Message
    ServerStartMessage = "SERVER_START_MESSAGE"
    ServerStopMessage = "SERVER_STOP_MESSAGE"
    ServerRestartMessage = "SERVER_RESTART_MESSAGE"
    RestartAnnouncementMessage = "RESTART_ANNOUNCEMENT_MESSAGE"

    # Tips Message
    TipsPrefix = "TIPS_PREFIX"
    TipsMessages = "TIPS_MESSAGES"

    # Mode
    EmbedMode = "EMBED_MODE"
    
    # Api Endpoint
    PlayerIconApi = "PLAYER_ICON_API"

    # Optional offline public-chat conversion.
    JapanizeEnabled = "JAPANIZE_ENABLED"
    JapanizeMode = "JAPANIZE_MODE"
    JapanizeDictionary = "JAPANIZE_DICTIONARY"
    JapanizeServerFormat = "JAPANIZE_SERVER_FORMAT"
    JapanizePublicChannels = "JAPANIZE_PUBLIC_CHANNELS"

    # Notification locale and advancement title translations.
    Language = "LANGUAGE"
    AdvancementTranslationEnabled = "ADVANCEMENT_TRANSLATION_ENABLED"
    AdvancementDictionary = "ADVANCEMENT_DICTIONARY"
    MinecraftVersion = "MINECRAFT_VERSION"
    ModsDir = "MODS_DIR"
    TranslationCacheDir = "TRANSLATION_CACHE_DIR"
    OpenMapMcWaypoints = "OPENMAPMC_WAYPOINT_NOTIFICATIONS"

    @staticmethod
    def init(env_path: str | Path | None = None):
        config_path = Path(env_path).absolute() if env_path is not None else default_config_path()
        values = load_config_values(config_path, resource_path(TEMPLATE_FILENAME))
        _env_data.clear()
        for _e in BotEnv:
            _loadEnvWithValidate(_e, values)
        for name in (BotEnv.TargetDir, BotEnv.PluginDir, BotEnv.ModsDir, BotEnv.TranslationCacheDir):
            value = name.get()
            if value:
                configured = config_path.parent / value
                # Preserve the final component so the MOD cache loader can
                # reject symlink directories before opening/writing them.
                _env_data[name.value] = str(configured.absolute() if name in (
                    BotEnv.ModsDir, BotEnv.TranslationCacheDir,
                ) else configured.resolve())

    def getBool(self) -> bool:
        _s = _env_data[self.value]
        return True if _s.lower() == "true" else False

    def get(self) -> str:
        return _env_data[self.value]
