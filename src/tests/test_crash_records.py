"""Server failure records across loader generations, without network or a JVM."""

import pytest

from server.crash import is_server_crash_record, is_server_start_record


@pytest.mark.parametrize("record", [
    pytest.param(
        "[05Nov2026 07:17:13.836] [main/ERROR] [net.minecraft.server.Main/FATAL]: "
        "Failed to start the minecraft server", id="reported-forge-1.20.1",
    ),
    pytest.param("[12:34:56] [main/FATAL]: Failed to start the minecraft server", id="fabric-1.16"),
    pytest.param("[12:34:56] [main/ERROR]: Failed to start the server", id="short-start-failure"),
    pytest.param("[12:34:56] [Server thread/ERROR]: Failed to start Minecraft server", id="server-thread-start-failure"),
    pytest.param("[12:34:56] [main/ERROR] [minecraft/Main]: Failed to start minecraft server", id="short-logger"),
    pytest.param("[12:34:56] [Server thread/ERROR] [minecraft/MinecraftServer]: Encountered an unexpected exception", id="forge-1.12"),
    pytest.param("[12:34:56] [Server thread/ERROR]: Encountered an unexpected exception", id="fabric-runtime"),
    pytest.param("[06Nov2026 12:34:56.789] [main/ERROR] [net.minecraft.server.Main/FATAL]: Failed to start the server", id="modern-neoforge"),
    pytest.param("\x1b[31m[12:34:56] [main/ERROR]: Failed to start the minecraft server\x1b[0m\n", id="ansi-colors"),
    pytest.param("[12:34:56] [main/ERROR]: §cFailed to start the minecraft server§r", id="minecraft-colors"),
    pytest.param(
        "[0511月2026 07:17:13.826] [main/FATAL] [net.minecraftforge.server.loading.ServerModLoader/]: "
        "Crash report saved to ./crash-reports/crash-2026-11-05_07.17.13-fml.txt",
        id="reported-forge-server-mod-loader",
    ),
    pytest.param(
        "[12:34:56] [main/FATAL] [net.neoforged.neoforge.server.loading.ServerModLoader/]: "
        "Failed to save crash report", id="neoforge-report-write-failure",
    ),
    pytest.param(
        "[12:34:56] [main/FATAL] [neoforge/ServerModLoader]: "
        "Crash report saved to ./crash-reports/crash-example-fml.txt", id="neoforge-console-report",
    ),
])
def test_server_failure_records(record):
    assert is_server_crash_record(record)


@pytest.mark.parametrize("record", [
    "[12:34:56] [main/ERROR]: Failed to start the metrics exporter",
    "[12:34:56] [main/INFO]: Failed to start the server",
    "[12:34:56] [Render thread/FATAL]: Failed to start the minecraft server",
    "[12:34:56] [Server thread/ERROR] [examplemod/]: <Alice> Failed to start the minecraft server",
    "[12:34:56] [main/ERROR]: [Server] Failed to start the minecraft server",
    "[12:34:56] [main/ERROR]: Example: Failed to start the minecraft server",
    "[12:34:56] [Server thread/ERROR]: Advice: Encountered an unexpected exception",
    "[12:34:56] [main/FATAL] [net.minecraftforge.client.loading.ClientModLoader/]: Crash report saved to ./crash-reports/crash-example-fml.txt",
    "[12:34:56] [main/FATAL] [examplemod/]: Crash report saved to ./crash-reports/crash-example-fml.txt",
    "[12:34:56] [Render thread/FATAL] [net.neoforged.neoforge.server.loading.ServerModLoader/]: Failed to save crash report",
    'net.neoforged.fml.startup.FatalStartupException: Couldn\'t find Minecraft server thread. Startup likely failed.',
    'java.lang.RuntimeException: Failed to start the minecraft server',
    "[12:34:56] [main/ERROR] [FabricLoader/]: Incompatible mods found!",
])
def test_non_server_failures_and_quoted_markers_are_ignored(record):
    assert not is_server_crash_record(record)


@pytest.mark.parametrize("record", [
    "[12:34:56] [main/INFO]: Loading Minecraft 1.16.5 with Fabric Loader 0.14.25",
    "[12:34:56] [main/INFO] [FabricLoader/GameProvider]: Loading Minecraft 1.21.1 with Fabric Loader 0.16.0",
    "[0511月2026 07:16:32.761] [main/INFO] [cpw.mods.modlauncher.Launcher/MODLAUNCHER]: ModLauncher running: args [--launchTarget, forgeserver, --fml.forgeVersion, 47.4.10]",
    "[12:34:56] [main/INFO] [cpw.mods.modlauncher.Launcher/MODLAUNCHER]: ModLauncher running: args [--launchTarget, neoforgeserver, --fml.neoForgeVersion, 21.1.0]",
    "[12:34:56] [main/INFO] [cpw.mods.modlauncher.Launcher/MODLAUNCHER]: ModLauncher running: args [--launchTarget, fmlserver, --fml.mcVersion, 1.16.5]",
    "[12:34:56] [main/INFO] [LaunchWrapper]: Loading tweak class name net.minecraftforge.fml.common.launcher.FMLServerTweaker",
    "[12:34:56] [main/INFO] [LaunchWrapper]: Loading tweak class name cpw.mods.fml.common.launcher.FMLServerTweaker",
    "\x1b[32m[12:34:56] [Server thread/INFO]: Starting minecraft server version 1.21.1\x1b[0m",
])
def test_loader_boot_records_reset_failed_start_attempts(record):
    assert is_server_start_record(record)


@pytest.mark.parametrize("record", [
    "[12:34:56] [main/INFO] [cpw.mods.modlauncher.Launcher/MODLAUNCHER]: ModLauncher running: args [--launchTarget, forgeclient]",
    "[12:34:56] [main/INFO] [LaunchWrapper]: Loading tweak class name net.minecraftforge.fml.common.launcher.FMLTweaker",
    "[12:34:56] [Server thread/INFO]: <Alice> Loading Minecraft 1.21.1 with Fabric Loader 0.16.0",
    "[12:34:56] [main/INFO] [examplemod/]: ModLauncher running: args [--launchTarget, forgeserver]",
    "[12:34:56] [main/INFO] [examplemod/]: Loading Minecraft 1.21.1 with Fabric Loader 0.16.0",
    "[12:34:56] [main/ERROR]: Loading Minecraft 1.21.1 with Fabric Loader 0.16.0",
])
def test_chat_client_and_untrusted_boot_messages_do_not_reset_incidents(record):
    assert not is_server_start_record(record)
