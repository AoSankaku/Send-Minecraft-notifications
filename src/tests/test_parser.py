import pytest
from message.parser import LogParser
from message.constant import EventIds

parser = LogParser(
    "", "", "", "Restarting in 60 seconds!", []
)  # We don't need check message here.


@pytest.mark.parametrize(
    "case",
    [
        (
            EventIds.ON_JOIN,
            "[01Dec2024 16:07:10.209] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user joined the game",
        ),
        (
            EventIds.ON_LEFT,
            "[01Dec2024 16:05:53.040] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user left the game",
        ),
        (
            EventIds.ON_SERVER_START,
            '[03Nov2024 09:15:29.053] [Server thread/INFO] [net.minecraft.server.dedicated.DedicatedServer/]: Done (11.632s)! For help, type "help"',
        ),
        (
            EventIds.ON_SERVER_STOP,
            "[03Nov2024 18:35:18.200] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Stopping the server",
        ),
        (
            EventIds.ON_CONSOLE_CHAT,
            "[19Aug2024 23:33:04.804] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: [Server] from server!",
        ),
        (
            EventIds.ON_SECURE_CHAT_OTHER,
            "[16Jul2024 00:00:24.849] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: <user> test message!",
        ),
        (
            EventIds.ON_DEATH,
            "[23Jul2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user burned to death",
        ),
        (
            EventIds.ON_ADVANCEMENT_COMPLETE,
            "[16Jul2024 18:04:05.111] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user has made the advancement [First Village]",
        ),
        (
            EventIds.ON_GOAL_COMPLETE,
            "[21Jul2024 05:23:23.431] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user has reached the goal [The Factory Must Grow!]",
        ),
        (
            EventIds.ON_CHALLENGE_COMPLETE,
            "[16Jul2024 03:06:05.789] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user has completed the challenge [Free Willy]",
        ),
    ],
)
def test_each_event_runs_exactly_forge(case: tuple[EventIds, str]):
    result = parser.parse(case[1])
    assert result
    assert result.event_id == case[0]


@pytest.mark.parametrize(
    "case",
    [
        "[23Jul2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user was burned to death",
        "[23Jul2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user was died to death",
        "[23Jul2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user was drown to death",
        "[23Jul2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user was withered to death",
        "[23Jul2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user was experienced to death",
        "[23Jul2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user was blew to death",
        "[23Jul2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user was hit to death",
        "[23Jul2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user was fell to death",
        "[23Jul2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user was went to death",
        "[23Jul2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user was walked to death",
        "[23Jul2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user was burned to death",
        "[23Jul2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user tried to death",
        "[23Jul2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user was discovered to death",
        "[23Jul2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user was froze to death",
        "[23Jul2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user was starved to death",
        "[23Jul2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user was suffocated to death",
        "[23Jul2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user was left to death",
        "[237月2024 01:24:14.180] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: user was left to death",
    ],
)
def test_each_kill_types(case: str):
    result = parser.parse(case)
    assert result
    assert result.event_id == EventIds.ON_DEATH
