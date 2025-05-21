from enum import Enum, auto

class ServerState(Enum):
    STARTING = auto()
    STARTED = auto()
    STOPPED = auto()
    RESTARTING = auto()