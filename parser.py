import os
import re
import dataclasses
from typing import Callable
from model import MessageData, MessageType
from enum import StrEnum

forge_primary_prefix = r"^\[[0-9a-zA-Z]{9} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}] \[Server thread/INFO] \[net\.minecraft\.server\.dedicated\.DedicatedServer/]: "
forge_secondary_prefix = r"^\[[0-9a-zA-Z]{9} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}] \[Server thread/INFO] \[net\.minecraft\.server\.MinecraftServer/]: "
default_prefix = r"^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: "
prefix_wildcard_without_brackets = (
    f"{forge_primary_prefix}|{forge_secondary_prefix}|{default_prefix}"
)

@dataclasses.dataclass
class ParserRule:
    regex_str: str
    handler: Callable[[list[any]], MessageData | None]
    condition: Callable[[list[any]], bool] | None = None

class RegexParser:
    def __init__(self):
        self.prefix = f"({prefix_wildcard_without_brackets})"
        self.handlers: dict[str, ParserRule] = {}
    
    def addRule(
        self,
        id: str,
        regex_pattern: str,
        handler: Callable[[list[any]], MessageData | None]
    ):
        if id in self.handlers.keys():
            raise KeyError(f"This rule id was already registered. id:{id}")
        self.handlers[id] = ParserRule(regex_pattern, handler)
    
    def addPrefiedRule(
        self,
        id: str,
        regex_pattern: str,
        handler: Callable[[list[any]], MessageData | None],
        condition: Callable[[list[any]], bool] | None = None
    ):
        if id in self.handlers.keys():
            raise KeyError(f"This rule id was already registered. id:{id}")
        self.handlers[id] = ParserRule(self.prefix + regex_pattern, handler, condition)
    
    def parse(self, text: str) -> MessageData | None:
        for k in self.handlers:
            _rule = self.handlers[k]
            
            _matched = re.findall(_rule.regex_str, text)
            if len(_matched) == 0:
                continue
            
            if _rule.condition != None:
                if not _rule.condition(_matched):
                    continue
            
            _result = _rule.handler(_matched)
            if _result is None:
                continue
            _result.event_id = k
            return _result
        return None

class EventIds(StrEnum):
    ON_JOIN = "on_join"
    ON_JOIN_NON_WHITELISTED = "on_join_non_whitelisted"
    ON_LEFT = "on_left"
    
    ON_SERVER_START = "on_server_start"
    ON_SERVER_STOP = "on_server_stop"
    ON_SERVER_RESTART = "on_server_restart"
    
    ON_CONSOLE_CHAT = "on_console_chat"
    ON_SECURE_CHAT = "on_secure_chat"
    ON_SECURE_CHAT_OTHER = "on_secure_chat_other"
    ON_NON_SECURE_CHAT = "on_non_secure_chat"
    
    ON_DEATH = "on_death"
    ON_RECALC_PLAYER_COUNT = "on_recalc_player_count"
    ON_ADVANCEMENT_COMPLETE = "on_advancement_complete"
    ON_GOAL_COMPLETE = "on_goal_complete"
    ON_CHALLENGE_COMPLETE = "on_challenge_complete"
    ON_ACHIEVEMENTS_COMPLETE_OLD = "on_achievements_complete_old"
    
    # integrations
    ON_CHAT_FROM_LUNACHAT = "on_chat_from_lunachat"

class LogParser(RegexParser):
    def __init__(
        self,
        server_start_message: str,
        server_stop_message: str,
        server_restart_message: str,
        ignore_names: list[str]
    ):
        super().__init__()
        
        # player join & left
        # Todo: player count impl on sender & replace "#server_count" with server player count
        self.addPrefiedRule(
            "on_join",
            r"(.*) joined the game",
            lambda x: MessageData(MessageType.System, "#0c0", f":green_circle: {str(x[0][1])} が参加しました。一緒に遊んであげよう！（現在 #server_count 名）")
        )
        self.addPrefiedRule(
            "on_left",
            r"(.*) left the game",
            lambda x: MessageData(MessageType.System, "#c00", f":red_circle: {str(x[0][1])} が退出しました。（現在 #server_count 名）")
        )
        
        # server status
        self.addPrefiedRule(
            "on_server_start",
            r"Done ",
            lambda x: MessageData(MessageType.System, "#6A9955", server_start_message)
        )
        self.addPrefiedRule(
            "on_server_stop",
            r"Stopping( the)? server",
            lambda x: MessageData(MessageType.System, "#D16869", server_stop_message)
        )
        self.addPrefiedRule(
            "on_server_restart",
            r"(\[Not Secure] |)\[Server] (.*)",
            lambda x: MessageData(MessageType.System, "#50C1FF", server_restart_message)
        )
        
        # player chat handling
        self.addPrefiedRule(
            "on_secure_chat",
            r"^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Async Chat Thread - #(.*)/INFO]: <(.*?)>(.*)",
            lambda x : MessageData(MessageType.Player, "#888", f"`{str(x[0][2])}`", str(x[0][1]))
        )
        self.addPrefiedRule(
            "on_secure_chat_other",
            r"<(.*?)>(.*)",
            lambda x: MessageData(MessageType.Player, "#888", f"`{str(x[0][2])}`", str(x[0][1]))
        )
        self.addPrefiedRule(
            "on_non_secure_chat",
            r"^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Async Chat Thread - #(.*)/INFO]: \[(.*?)] <(.*)>(.*)",
            lambda x: MessageData(MessageType.Player, "#888", f"`{str(x[0][3])}`", str(x[0][2]))
        )
        
        # server chat handling
        self.addPrefiedRule(
            "on_console_chat",
            r"(\[Not Secure] )?\[(.*?)] (.*)",
            lambda x : MessageData(MessageType.Server, "#888", f"`{str(x[0][3])}`", "#server") if len(x) and str(x[0][2]) == "Server"
            # if not matched to condition -> it's player message.
            else (MessageData(MessageType.Player, "#888", f"`{str(x[0][3])}`", str(x[0][2])) if len(x) and not (str(x[0][2]).casefold() in ignore_names) else None), # Todo: suppport #server id
        )
        
        # chat which from lunachat
        self.addPrefiedRule(
            "on_chat_from_lunachat",
            r"^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Async Chat Thread - #(.*)/INFO]: (\[Not Secure] )?(.*): (.*)",
            lambda x: MessageData(MessageType.Player, "#888", f"`{str(x[0][3])}`", str(x[0][2]))
        )
        
        # on non whitelisted player joined
        self.addPrefiedRule(
            "on_join_non_whitelisted",
            r"Disconnecting (.*?name=)(.*?),(.*?You are not whitelisted on this server!)",
            lambda x: MessageData(MessageType.Server, "#f8f", f":yellow_circle: {str(x[0][2])} がサーバーに入ろうとしましたが、ホワイトリストに入っていません！")
        )
        
        # re-calculate player count when "/list" command fired.
        self.addPrefiedRule(
            "on_recalc_player_count",
            r"There are ([0-9]*) of a max of ([0-9]*) players online:",
            lambda x: MessageData(MessageType.Server, "#f8f", f":information_source: 現在サーバーにいるプレイヤーは {self.player_count} 人です。（上限 {str(x[0][2])} 名）")
        )
        
        # advancements
        self.addPrefiedRule(
            "on_advancement_complete",
            r"(.*) has made the advancement \[(.*)]",
            lambda x: MessageData(MessageType.Player, "#f8f", f":trophy: 進捗[{str(x[0][2])}]を達成しました！", str(x[0][1]))
        )
        
        # goals
        self.addPrefiedRule(
            "on_goal_complete",
            r"(.*) has reached the goal \[(.*)]",
            lambda x: MessageData(MessageType.Player, "#f8f", f":checkered_flag: 目標[{str(x[0][2])}]を達成しました！", str(x[0][1]))
        )
        
        # challenges
        self.addPrefiedRule(
            "on_challenge_complete",
            r"(.*) has completed the challenge \[(.*)]",
            lambda x: MessageData(MessageType.Player, "#f8f", f":trophy: 進捗[{str(x[0][2])}]を達成しました！", str(x[0][1])),
        )
        
        # achievements(until 17w13a)
        self.addPrefiedRule(
            "on_achievements_complete_old",
            r"(.*) has just earned the achievement \[(.*)]",
            lambda x: MessageData(MessageType.Player, "#f8f", f":military_metal: 挑戦[{str(x[0][2])}]を達成しました！", str(x[0][1]))
        )
        
        # death messages(experimental feature)
        self.addPrefiedRule(
            "on_death",
            r"(.*) (was|died|drown|withered|experienced|blew|hit|fell|went|walked|burned|tried|discovered|froze|starved|suffocated|left) (.*)",
            lambda x: MessageData(MessageType.Player, "#f8f", f":skull_crossbones: 死んでしまいました。助けに行ってあげよう！ (x:{str(x[0][1])}/y:{str(x[0][2])}/z:{str(x[0][3])})", str(x[0][1])) # Todo: check this one is working?
        )