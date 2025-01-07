import os
import re
import dataclasses
from typing import Callable
from model import MessageData, MessageType

forge_primary_prefix = r"^\[[0-9a-zA-Z]{9} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}] \[Server thread/INFO] \[net\.minecraft\.server\.dedicated\.DedicatedServer/]: "
forge_secondary_prefix = r"^\[[0-9a-zA-Z]{9} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}] \[Server thread/INFO] \[net\.minecraft\.server\.MinecraftServer/]: "
default_prefix = r"^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: "
prefix_wildcard_without_brackets = (
    f"{forge_primary_prefix}|{forge_secondary_prefix}|{default_prefix}"
)

@dataclasses.dataclass
class ParserRule:
    regex_str: str
    handler: Callable[[list[any]], MessageData]

class RegexParser:
    def __init__(self):
        self.prefix = f"({prefix_wildcard_without_brackets})"
        self.handlers: dict[str, ParserRule] = {}
    
    def addRule(
        self,
        id: str,
        regex_pattern: str,
        handler: Callable[[list[any]], MessageData]
    ):
        if id in self.handlers.keys():
            raise KeyError(f"This rule id was already registered. id:{id}")
        self.handlers[id] = ParserRule(regex_pattern, handler)
    
    def addPrefiedRule(
        self,
        id: str,
        regex_pattern: str,
        handler: Callable[[list[any]], MessageData]
    ):
        if id in self.handlers.keys():
            raise KeyError(f"This rule id was already registered. id:{id}")
        self.handlers[id] = ParserRule(self.prefix + regex_pattern, handler)
    
    def parse(self, text: str) -> MessageData | None:
        for k in self.handlers:
            _rule = self.handlers[k]
            
            _matched = re.findall(_rule.regex_str, text)
            if len(_matched) == 0:
                continue
            
            return _rule.handler(_matched)
        return None

class LogParser(RegexParser):
    def __init__(self):
        super().__init__()
        
        # system messages
        self.addPrefiedRule(
            "on_join",
            r"(.*) joined the game",
            lambda x: MessageData(MessageType.System, "#0c0", f":green_circle: {str(x[0][1])} が参加しました。一緒に遊んであげよう！（現在 {0} 名）")
        )
        # self.addPrefiedRule(
        #     "on_left",
        # )