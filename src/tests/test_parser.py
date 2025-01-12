import pytest
from message.parser import LogParser
from message.constant import EventIds

def test_each_event_runs_exactly():
    parser = LogParser("", "", "", "Restarting in 60 seconds!", []) # We don't need check message here.
    
    testcases: list[tuple[str, EventIds]] = [
        ("[01Dec2024 16:07:10.209] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Ao_Sankaku joined the game", EventIds.ON_JOIN),
        ('[01Dec2024 16:05:53.040] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Ao_Sankaku left the game', EventIds.ON_LEFT),
        ('[03Nov2024 09:15:29.053] [Server thread/INFO] [net.minecraft.server.dedicated.DedicatedServer/]: Done (11.632s)! For help, type "help"', EventIds.ON_SERVER_START),
        ('[03Nov2024 18:35:18.200] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Stopping the server', EventIds.ON_SERVER_STOP)
    ]
    for log_line, event_id in testcases:
        assert parser.parse(log_line).event_id == event_id