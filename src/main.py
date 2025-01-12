import os
import re
import dataclasses
from enum import StrEnum

forge_primary_prefix = r"^\[[0-9a-zA-Z]{9} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}] \[Server thread/INFO] \[net\.minecraft\.server\.dedicated\.DedicatedServer/]: "
forge_secondary_prefix = r"^\[[0-9a-zA-Z]{9} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}] \[Server thread/INFO] \[net\.minecraft\.server\.MinecraftServer/]: "
default_prefix = r"^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: "
prefix_wildcard_without_brackets = (
    f"{forge_primary_prefix}|{forge_secondary_prefix}|{default_prefix}"
)

class MessageType(StrEnum):
    System = "system"
    Server = "server"
    Player = "player"
    Unknown = "unknown"

@dataclasses.dataclass
class MessageData:
    msg_type: MessageType
    color: str
    text: str

def parse_line(text: str):
    match = re.findall(
            f"({prefix_wildcard_without_brackets})" + r"(.*) joined the game", text
        )
    if len(match) and not (str(match[0][1]).startswith("[")):
        # player_count += 1
        chat_count = 0
        return {
            "embed": {
                "color": "#0c0",
                "name": str(match[0][1]),
                "title": f"サーバーに参加しました。一緒に遊んであげよう！\n（現在 {0} 名）",
            },
            "noembed": {
                "type": "normal",
                "name": str(match[0][1]),
                "message": f":green_circle: {str(match[0][1])} が参加しました。一緒に遊んであげよう！（現在 {0} 名）",
            },
        }
    return text

def main():
    print(parse_line("[01Dec2024 16:07:10.209] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Ao_Sankaku joined the game"))
    # print(re.match(prefix_wildcard_without_brackets, "[21Sep2024 02:07:19.990] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Stopping server"))
    
    return
    raw_data = None
    with open("test.log") as f:
        raw_data = f.read()
    
    if raw_data is None:
        print("Failed to open test.log")
        exit(1)
    
    arr = raw_data.split("\n")
    cnt = 0
    for s in arr:
        print(parse_line(s))
        
        # count
        cnt += 1
        if cnt == 100:
            break
    
    print("")

if __name__ == "__main__":
    main()