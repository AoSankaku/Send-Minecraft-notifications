import dataclasses
from enum import StrEnum
from message.constant import EventIds


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
    playerId: str | None = None
    event_id: EventIds = EventIds.NONE
    player_count: int | None = None