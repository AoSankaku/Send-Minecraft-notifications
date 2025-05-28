import os
from os import path

from dotenv import dotenv_values
from enum import StrEnum
from typing import Self


def _is_bool_str(s: str) -> bool:
    _lower = s.lower()
    return _lower == "true" or _lower == "false"


_env_data: dict[str, str] = {}


def _loadEnvWithValidate(name: Self, values: dict[str, str | None]):
    # Get value from os enriron
    _v = values[name]

    if _v is None:
        _default = _get_default(name)
        if _default is None:
            # If default value was not presented.
            print(f"Failed to load env. name:{name}")
            exit(1)
        else:
            print(f"[Warn] Fallback to default value. name:{name}")
            _v = _default

    # Validation
    _v = _validate_env(name, _v)
    if _v is None:
        print(f"Failed to validate env. name:{name}")
        exit(1)

    # Store env value
    _env_data[name.value] = _v


def _validate_env(name: Self, value: str) -> str | None:
    match name:
        case BotEnv.KillAfterClosed:
            if not _is_bool_str(value):
                return None
        case BotEnv.EmbedMode:
            if not _is_bool_str(value):
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

    @staticmethod
    def init():
        if(path.exists(".env")):
            values = dotenv_values(".env")
        else:
            values = os.environ
        for _e in BotEnv:
            _loadEnvWithValidate(_e, values)

    def getBool(self) -> bool:
        _s = _env_data[self.value]
        return True if _s.lower() == "true" else False

    def get(self) -> str:
        return _env_data[self.value]
