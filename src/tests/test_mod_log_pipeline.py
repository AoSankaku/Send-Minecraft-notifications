import asyncio
import json
import zipfile

import pytest

from main import cli
from server.server import Server
from handlers.secrets import BotEnv


WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/" + "test-token-" * 6


def write_create_jar(path):
    with zipfile.ZipFile(path, "w") as archive:
        for locale, mapping in {
            "en_us": {"create.advancement.test": "A Custom Factory", "death.attack.create.crush": "%1$s was processed by Crushing Wheels"},
            "ja_jp": {"create.advancement.test": "自作工場", "death.attack.create.crush": "%1$sは破砕ホイールによって加工された"},
            "de_de": {"create.advancement.test": "Eine eigene Fabrik", "death.attack.create.crush": "%1$s wurde von Zerkleinerungsrädern verarbeitet"},
        }.items():
            archive.writestr(f"assets/create/lang/{locale}.json", json.dumps(mapping))
        archive.writestr("data/create/advancement/test.json", json.dumps({"display": {"title": {"translate": "create.advancement.test"}}}))


class RecordingWebhook:
    def __init__(self, *args, **kwargs):
        self.players = []

    async def sendPlayerMessage(self, message, player):
        self.players.append((message, player))

    async def sendServerMessage(self, message):
        pass

    async def onClose(self):
        pass


@pytest.mark.parametrize("locale,title,death", [
    ("ja", "自作工場", "Aliceは破砕ホイールによって加工された"),
    ("de", "Eine eigene Fabrik", "Alice wurde von Zerkleinerungsrädern verarbeitet"),
    ("hi", "A Custom Factory", "Alice was processed by Crushing Wheels"),
])
def test_mod_logs_translate_and_cache_without_executing_mods(tmp_path, monkeypatch, locale, title, death):
    mods = tmp_path / "mods"
    mods.mkdir()
    write_create_jar(mods / "create.jar")
    config = tmp_path / "config.toml"
    config.write_text(f'WEBHOOK_URL = "{WEBHOOK}"\nLANGUAGE = "{locale}"\nMODS_DIR = "./mods"\n', encoding="utf-8")
    monkeypatch.setattr("server.server.DiscordWebhook", RecordingWebhook)

    async def exercise():
        server = Server()
        try:
            server.init(config)
            await server.on_line_added("[12:34:56] [Server thread/INFO] [minecraft/MinecraftServer]: Alice has made the advancement [A Custom Factory]")
            await server.on_line_added("[12:34:57] [Server thread/INFO] [minecraft/MinecraftServer]: Alice was processed by Crushing Wheels")
            await server.on_line_added("[12:34:58] [Server thread/INFO]: <Alice> Alice was processed by Crushing Wheels")
            assert title in server.webhook.players[0][0]
            assert server.webhook.players[0][1] == "Alice"
            assert death in server.webhook.players[1][0]
            assert server.webhook.players[1][1] == "Alice"
            assert server.webhook.players[2][0] == "`Alice was processed by Crushing Wheels`"
            assert server.player_count == 0
        finally:
            await server.shutdown()

    asyncio.run(exercise())
    cache = tmp_path / "translation-cache"
    assert cache.is_dir()
    files = list(cache.glob("*.json"))
    assert files
    assert all(WEBHOOK not in file.read_text(encoding="utf-8") for file in files)


def test_config_check_builds_cache_with_config_relative_paths(tmp_path, capsys):
    mods = tmp_path / "mods"
    mods.mkdir()
    write_create_jar(mods / "create.jar")
    config = tmp_path / "config.toml"
    config.write_text(
        f'WEBHOOK_URL = "{WEBHOOK}"\nMODS_DIR = "./mods"\nTRANSLATION_CACHE_DIR = "./my-cache"\n',
        encoding="utf-8",
    )
    assert cli(["--config", str(config), "--check-config"]) == 0
    assert list((tmp_path / "my-cache").glob("*.json"))
    assert BotEnv.ModsDir.get() == str(mods.resolve())
    assert BotEnv.TranslationCacheDir.get() == str((tmp_path / "my-cache").resolve())
    assert "No notifications were sent" in capsys.readouterr().out


def test_invalid_mods_directory_is_actionable_config_error(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text(f'WEBHOOK_URL = "{WEBHOOK}"\nMODS_DIR = "./missing-mods"\n', encoding="utf-8")
    assert cli(["--config", str(config), "--check-config"]) == 1
    assert "MODS_DIR" in capsys.readouterr().err


def test_empty_cache_directory_is_rejected_without_writing_to_working_directory(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text(f'WEBHOOK_URL = "{WEBHOOK}"\nTRANSLATION_CACHE_DIR = ""\n', encoding="utf-8")
    assert cli(["--config", str(config), "--check-config"]) == 1
    assert "TRANSLATION_CACHE_DIR" in capsys.readouterr().err


def test_old_settings_do_not_scan_or_create_mod_cache(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(f'WEBHOOK_URL = "{WEBHOOK}"\n', encoding="utf-8")
    assert cli(["--config", str(config), "--check-config"]) == 0
    assert not (tmp_path / "translation-cache").exists()


def test_mod_legacy_achievement_from_lang_file_translates_in_real_pipeline(tmp_path, monkeypatch):
    mods = tmp_path / "mods"
    mods.mkdir()
    with zipfile.ZipFile(mods / "old-mod.jar", "w") as archive:
        archive.writestr("assets/oldmod/lang/en_US.lang", "achievement.oldmod.test=Old Mod Achievement\n")
        archive.writestr("assets/oldmod/lang/ja_JP.lang", "achievement.oldmod.test=旧MOD実績\n")
    config = tmp_path / "config.toml"
    config.write_text(f'WEBHOOK_URL = "{WEBHOOK}"\nMODS_DIR = "./mods"\n', encoding="utf-8")
    monkeypatch.setattr("server.server.DiscordWebhook", RecordingWebhook)

    async def exercise():
        server = Server()
        try:
            server.init(config)
            await server.on_line_added("[12:34:56] [Server thread/INFO]: Alice has just earned the achievement [Old Mod Achievement]")
            assert "旧MOD実績" in server.webhook.players[0][0]
        finally:
            await server.shutdown()

    asyncio.run(exercise())
