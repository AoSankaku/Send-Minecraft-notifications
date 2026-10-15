"""Create startup translators from validated configuration, without a network."""

import json
from pathlib import Path

from handlers.secrets import BotEnv
from message.advancements import AdvancementTranslator
from message.mod_catalog import load_mod_catalog
from message.mod_deaths import DeathTranslator


def load_log_translators():
    mods_path = BotEnv.ModsDir.get()
    catalog = load_mod_catalog(
        Path(mods_path), Path(BotEnv.TranslationCacheDir.get()), BotEnv.Language.get(),
    ) if mods_path else None
    advancements = AdvancementTranslator(
        locale=BotEnv.Language.get(),
        enabled=BotEnv.AdvancementTranslationEnabled.getBool(),
        dictionary=json.loads(BotEnv.AdvancementDictionary.get()),
        minecraft_version=BotEnv.MinecraftVersion.get(),
        mod_advancements=catalog.advancements if catalog else None,
        mod_achievements=catalog.achievements if catalog else None,
    )
    deaths = DeathTranslator(catalog.deaths) if catalog else None
    return advancements, deaths, catalog
