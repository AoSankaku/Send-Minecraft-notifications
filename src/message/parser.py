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
        ignore_names: list[str]
    ):
        super().__init__()

        # player issue command
        self.addPrefiedRule(
            EventIds.ON_ISSUE_COMMAND,
            r"\[(.*?): (.*?)]$",
            lambda msg, x: MessageData(MessageType.Server, "#888", msg.replace("%player-message%", str(x[0][2])))
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
        
        # player chat handling
        self.addPrefiedRule(
            EventIds.ON_SECURE_CHAT,
            r"^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Async Chat Thread - #(.*)/INFO]: <(.*?)>\s*(.*)",
            lambda msg, x: MessageData(MessageType.Player, "#888", msg.replace("%player-message%", str(x[0][2])), str(x[0][1]))
        )
        self.addPrefiedRule(
            EventIds.ON_SECURE_CHAT_OTHER,
            r"<(.*?)>\s*(.*)",
            lambda msg, x: MessageData(MessageType.Player, "#888", msg.replace("%player-message%", str(x[0][2])), str(x[0][1]))
        )
        self.addPrefiedRule(
            EventIds.ON_NON_SECURE_CHAT,
            r"^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Async Chat Thread - #(.*)/INFO]: \[(.*?)] <(.*)>\s*(.*)",
            lambda msg, x: MessageData(MessageType.Player, "#888", msg.replace("%player-message%", str(x[0][3])), str(x[0][2]))
        )
        
        # server chat handling
        self.addPrefiedRule(
            EventIds.ON_CONSOLE_CHAT,
            r"(\[Not Secure] )?\[(.*?)] (.*)",
            lambda msg, x: MessageData(MessageType.Server, "#888", msg.replace("%player-message%", str(x[0][3])), "#server") if len(x) and str(x[0][2]) == "Server"
            # if not matched to condition -> it's player message.
            else (MessageData(MessageType.Player, "#888", msg.replace("%player-message%", str(x[0][3])), str(x[0][2])) if len(x) and not (str(x[0][2]).casefold() in ignore_names) else None), # Todo: suppport #server id
        )
        
        # chat which from lunachat
        self.addPrefiedRule(
            EventIds.ON_CHAT_FROM_LUNACHAT,
            r"^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Async Chat Thread - #(.*)/INFO]: (\[Not Secure] )?(.*): (.*)",
            lambda msg, x: MessageData(MessageType.Player, "#888", msg.replace("%player-message%", str(x[0][3])), str(x[0][2]))
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