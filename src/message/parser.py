import re
import dataclasses
from typing import Callable
from message.model import MessageData, MessageType
from message.constant import EventIds
from message.i18n import I18n

forge_primary_prefix = r"^\[.*] \[Server thread/INFO] \[net\.minecraft\.server\.dedicated\.DedicatedServer/]: "
forge_secondary_prefix = r"^\[.*] \[Server thread/INFO] \[net\.minecraft\.server\.MinecraftServer/]: "
default_prefix = r"^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: "
prefix_wildcard_without_brackets = (
    f"{forge_primary_prefix}|{forge_secondary_prefix}|{default_prefix}"
)

_COLORS = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|§[0-9a-fk-orx]", re.IGNORECASE)
_LOG_HEADER = re.compile(
    r"^(?:\[[^\]\r\n]+\] \[(?P<thread>[^\]\r\n]+)/INFO\]"
    r"(?: \[(?P<logger>[^\]\r\n]+)\])?:[ \t]*"
    r"|\[\d{2}:\d{2}:\d{2} INFO\]:[ \t]*"
    r"|\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \[INFO\][ \t]+)"
    r"(?P<body>[\s\S]*)$"
)
_PLAYER = r"[.A-Za-z0-9_]{1,32}"
_ANGLE_CHAT = re.compile(rf"^<(?P<player>{_PLAYER})>[ \t]*(?P<text>[\s\S]*)$")
_COLON_CHAT = re.compile(rf"^(?P<player>{_PLAYER}):[ \t]+(?P<text>[\s\S]*)$")
_CHANNEL_CHAT = re.compile(rf"^\[(?P<channel>[^\]\r\n]+)\][ \t]*(?:<(?P<angle>{_PLAYER})>|(?P<colon>{_PLAYER}):)[ \t]*(?P<text>[\s\S]*)$")
_PRIVATE_CHAT = re.compile(r"^(?:\[[^\]\r\n]*(?:->|→|»)[^\]\r\n]*\]|<[^>\r\n]*(?:->|→|»)[^>\r\n]*>)")


def _chat_body(line: str):
    match = _LOG_HEADER.fullmatch(_COLORS.sub("", line).rstrip("\r\n"))
    if match is None:
        return None
    body = match["body"]
    not_secure = False
    # Both orders occur in modded/unsigned logging layouts.
    for _ in range(2):
        if body.startswith("[Not Secure] "):
            body = body[len("[Not Secure] "):]
            not_secure = True
        elif body.startswith("[CHAT] "):
            body = body[len("[CHAT] "):]
    return match, body, not_secure


def combine_chat_records(lines: list[str]) -> list[str]:
    """Join Tsuki's headerless continuation inside a public chat record only."""
    records = []
    for line in lines:
        previous = _chat_body(records[-1]) if records else None
        if (
            previous and "\n" not in previous[1]
            and _ANGLE_CHAT.fullmatch(previous[1])
            and _COLORS.sub("", line).startswith("→ ")
        ):
            records[-1] = records[-1].rstrip("\r\n") + "\n" + line
        else:
            records.append(line)
    return records

@dataclasses.dataclass
class ParserRule:
    regex_str: str
    handler: Callable[[str, list[any]], MessageData | None]
    condition: Callable[[list[any]], bool] | None = None

class RegexParser:
    def __init__(self):
        self.prefix = f"({prefix_wildcard_without_brackets})"
        self.handlers: dict[str, ParserRule] = {}
    
    def addRule(
        self,
        id: str,
        regex_pattern: str,
        handler: Callable[[str, list[any]], MessageData | None]
    ):
        if id in self.handlers.keys():
            raise KeyError(f"This rule id was already registered. id:{id}")
        self.handlers[id] = ParserRule(regex_pattern, handler)
    
    def addPrefiedRule(
        self,
        id: str,
        regex_pattern: str,
        handler: Callable[[str, list[any]], MessageData | None],
        condition: Callable[[list[any]], bool] | None = None
    ):
        if id in self.handlers.keys():
            raise KeyError(f"This rule id was already registered. id:{id}")
        self.handlers[id] = ParserRule(self.prefix + regex_pattern, handler, condition)
    
    def parse(self, text: str, translator: I18n = None) -> MessageData | None:
        for k in self.handlers:
            _rule = self.handlers[k]
            
            _matched = re.findall(_rule.regex_str, text)
            if len(_matched) == 0:
                continue
            
            if _rule.condition != None:
                if not _rule.condition(_matched):
                    continue
            
            _translated = ">> No Translation <<"
            if translator != None:
                _translated = translator.translate(k) or "!! translation failure !!"

            _result = _rule.handler(_translated, _matched)
            if _result is None:
                continue
            _result.event_id = k
            return _result
        return None

class LogParser(RegexParser):
    def __init__(
        self,
        server_start_message: str,
        server_stop_message: str,
        server_restart_message: str,
        restart_announcement_message: str,
        ignore_names: list[str],
        *,
        public_channels=(),
    ):
        super().__init__()
        self.public_channels = {channel.casefold() for channel in public_channels}
        ignore_names = {name.casefold() for name in ignore_names}

        # player issue command
        self.addPrefiedRule(
            EventIds.ON_ISSUE_COMMAND,
            r"\[(.*?): (.*?)]$",
            lambda msg, x: MessageData(MessageType.Player, "#888", msg.replace("%player-message%", str(x[0][2])), str(x[0][1]))
        )
        
        # player join & left
        # Todo: player count impl on sender & replace "#server_count" with server player count
        self.addPrefiedRule(
            EventIds.ON_JOIN,
            r"(.*) joined the game",
            lambda msg, x: MessageData(MessageType.System, "#0c0", msg.replace("%player-name%", str(x[0][1])))
        )
        self.addPrefiedRule(
            EventIds.ON_LEFT,
            r"(.*) left the game",
            lambda msg, x: MessageData(MessageType.System, "#c00", msg.replace("%player-name%", str(x[0][1])))
        )
        self.addPrefiedRule(
            EventIds.ON_KICK,
            r"Kicked (.*?): (.*)",
            lambda msg, x: MessageData(MessageType.System, "#c00", msg.replace("%player-name%", str(x[0][1])).replace("%player-message%", str(x[0][2])))
        )
        
        # server status
        self.addPrefiedRule(
            EventIds.ON_SERVER_START,
            r"Done ",
            lambda msg, x: MessageData(MessageType.System, "#6A9955", server_start_message)
        )
        self.addPrefiedRule(
            EventIds.ON_SERVER_STOP,
            r"Stopping( the)? server",
            lambda msg, x: MessageData(MessageType.System, "#D16869", server_stop_message)
        )
        self.addPrefiedRule(
            EventIds.ON_SERVER_RESTART,
            r"(\[Not Secure] |)\[Server] (.*)",
            lambda msg, x: MessageData(MessageType.System, "#50C1FF", server_restart_message) if x[0][2] == restart_announcement_message else None
        )
        
        # server chat handling
        self.addPrefiedRule(
            EventIds.ON_CONSOLE_CHAT,
            r"(\[Not Secure] )?\[(.*?)] (.*)",
            lambda msg, x: MessageData(MessageType.Server, "#888", msg.replace("%player-message%", str(x[0][3])), "#server") if len(x) and str(x[0][2]) == "Server"
            # if not matched to condition -> it's player message.
            else (MessageData(MessageType.Player, "#888", msg.replace("%player-message%", str(x[0][3])), str(x[0][2])) if len(x) and not (str(x[0][2]).casefold() in ignore_names) else None), # Todo: suppport #server id
        )
        
        # on non whitelisted player joined
        self.addPrefiedRule(
            EventIds.ON_JOIN_NON_WHITELISTED,
            r"Disconnecting (.*?name=)(.*?),(.*?You are not whitelisted on this server!)",
            lambda msg, x: MessageData(MessageType.Server, "#f8f", msg.replace("%player-name%", str(x[0][2])))
        )
        
        # re-calculate player count when "/list" command fired.
        self.addPrefiedRule(
            EventIds.ON_RECALC_PLAYER_COUNT,
            r"There are ([0-9]*) of a max of ([0-9]*) players online:(.*)",
            lambda msg, x: MessageData(MessageType.Server, "#f8f", msg.replace("%server-max-player%", str(x[0][2])), player_count=int(x[0][1]))
        )
        
        # advancements
        self.addPrefiedRule(
            EventIds.ON_ADVANCEMENT_COMPLETE,
            r"(.*) has made the advancement \[(.*)]",
            lambda msg, x: MessageData(MessageType.Player, "#f8f", msg.replace("%advancement-name%", str(x[0][2])), str(x[0][1]))
        )
        
        # goals
        self.addPrefiedRule(
            EventIds.ON_GOAL_COMPLETE,
            r"(.*) has reached the goal \[(.*)]",
            lambda msg, x: MessageData(MessageType.Player, "#f8f", msg.replace("%goal-name%", str(x[0][2])), str(x[0][1]))
        )
        
        # challenges
        self.addPrefiedRule(
            EventIds.ON_CHALLENGE_COMPLETE,
            r"(.*) has completed the challenge \[(.*)]",
            lambda msg, x: MessageData(MessageType.Player, "#f8f", msg.replace("%challenge-name%", str(x[0][2])), str(x[0][1])),
        )
        
        # achievements(until 17w13a)
        self.addPrefiedRule(
            EventIds.ON_ACHIEVEMENTS_COMPLETE_OLD,
            r"(.*) has just earned the achievement \[(.*)]",
            lambda msg, x: MessageData(MessageType.Player, "#f8f", msg.replace("%challenge-name%", str(x[0][2])), str(x[0][1]))
        )
        
        # death messages(experimental feature)
        self.addPrefiedRule(
            EventIds.ON_DEATH,
            r"(.*) (was|died|drown|withered|experienced|blew|hit|fell|went|walked|burned|tried|discovered|froze|starved|suffocated|left) (.*)",
            lambda msg, x: MessageData(MessageType.Player, "#f8f", msg.replace("%death-x%", str(x[0][1])).replace("%death-y%", str(x[0][2])).replace("%death-z%", str(x[0][3])), str(x[0][1]))
        )

    def parse(self, text: str, translator: I18n = None) -> MessageData | None:
        decoded = _chat_body(text)
        if decoded is None:
            return super().parse(text, translator)
        header, body, not_secure = decoded
        # An anonymous conversion can belong to a private message. Never infer
        # its sender from the previous public message or forward it on its own.
        if _PRIVATE_CHAT.match(body) or body.startswith(("[JP]", "→ ")):
            return None
        if body.startswith("[Server] "):
            return super().parse(text, translator)
        channel = _CHANNEL_CHAT.fullmatch(body)
        if channel:
            if channel["channel"].casefold() not in self.public_channels:
                return None
            player, content = channel["angle"] or channel["colon"], channel["text"]
            event = EventIds.ON_CHAT_FROM_LUNACHAT
        else:
            # Unknown bracketed formats can be private/channel traffic. Keep
            # console /say and established command feedback, never reinterpret
            # an unapproved channel as a player's display name in the fallback.
            if body.startswith("[") and not (
                body.startswith("[Server] ")
                or re.fullmatch(rf"\[{_PLAYER}: [^\r\n]*\]", body)
            ):
                return None
            match = _ANGLE_CHAT.fullmatch(body)
            if not_secure:
                event = EventIds.ON_NON_SECURE_CHAT
            elif "chat" in (header["thread"] or "").casefold():
                event = EventIds.ON_SECURE_CHAT
            else:
                event = EventIds.ON_SECURE_CHAT_OTHER
            if match is None and (
                "chat" in (header["thread"] or "").casefold()
                or "lunachat" in (header["logger"] or "").casefold()
            ):
                match = _COLON_CHAT.fullmatch(body)
                event = EventIds.ON_CHAT_FROM_LUNACHAT
            if match is None:
                return super().parse(text, translator)
            player, content = match["player"], match["text"]
        template = translator.translate(event) if translator else ">> No Translation <<"
        template = template if template is not None else "%player-message%"
        return MessageData(
            MessageType.Player, "#888", template.replace("%player-message%", content), player,
            event_id=event, chat_text=content, chat_format=template,
        )
