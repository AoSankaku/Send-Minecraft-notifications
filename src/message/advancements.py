"""Offline translation of the display names present in server log records."""

from collections import defaultdict
from functools import lru_cache
import json
from pathlib import Path

from message.locales import normalize_locale
from utils.runtime import resource_path


def validate_dictionary(dictionary) -> dict[str, str]:
    if not isinstance(dictionary, dict) or len(dictionary) > 4096 or not all(
        isinstance(key, str) and 0 < len(key) <= 1024
        and isinstance(value, str) and 0 < len(value) <= 1024
        and not any(ord(char) < 32 or ord(char) == 127 for char in key + value)
        for key, value in dictionary.items()
    ):
        raise ValueError("Invalid ADVANCEMENT_DICTIONARY; use a table of nonempty title strings")
    return dict(dictionary)


def _read_catalog(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema") != 1:
            raise ValueError()
        versions = data.get("versions")
        if not isinstance(versions, dict) or not versions:
            raise ValueError()
        for version, languages in versions.items():
            if not isinstance(version, str) or not isinstance(languages, dict):
                raise ValueError()
            if not languages.get("en"):
                raise ValueError()
            for locale, names in languages.items():
                if not isinstance(locale, str) or not isinstance(names, dict) or not all(
                    isinstance(key, str) and isinstance(value, str) and value
                    for key, value in names.items()
                ):
                    raise ValueError()
        return versions
    except (OSError, UnicodeError, ValueError):
        raise ValueError(f"Invalid or missing Minecraft translation catalog: {path}") from None


@lru_cache(maxsize=1)
def _bundled_catalog() -> dict:
    return _read_catalog(resource_path("translations/minecraft.json"))


class AdvancementTranslator:
    def __init__(
        self, locale="ja", *, enabled=True, dictionary=None, minecraft_version="",
        catalog_path: Path | None = None, mod_advancements=None, mod_achievements=None,
    ):
        self.locale = normalize_locale(locale)
        self.enabled = enabled
        self.dictionary = validate_dictionary({} if dictionary is None else dictionary)
        versions = _read_catalog(Path(catalog_path)) if catalog_path is not None else _bundled_catalog()
        if minecraft_version and minecraft_version not in versions:
            raise ValueError("Invalid MINECRAFT_VERSION; leave empty or choose: " + ", ".join(versions))
        selected = [versions[minecraft_version]] if minecraft_version else versions.values()
        # Catalog snapshots are ordered oldest to newest. Reuse the newest
        # available wording for a key while retaining old English name aliases.
        # Regional locales absent from old versions can use a newer translation.
        translated = {}
        for languages in selected:
            translated.update(languages.get(self.locale, {}))
        candidates = {False: defaultdict(set), True: defaultdict(set)}
        for languages in selected:
            for key, english in languages["en"].items():
                legacy = key.startswith("achievement.")
                if not legacy and not (key.startswith("advancements.") and key.endswith(".title")):
                    continue
                # Missing keys remain candidates: an identical display name
                # may refer to a different, untranslated advancement.
                candidates[legacy][english].add(translated.get(key, english))
        for english, translations in (mod_advancements or {}).items():
            candidates[False][english].update(translations)
        for english, translations in (mod_achievements or {}).items():
            candidates[True][english].update(translations)
        self.names = {
            legacy: {english: next(iter(names)) for english, names in values.items() if len(names) == 1}
            for legacy, values in candidates.items()
        }

    def translate(self, name: str, *, legacy=False) -> str:
        if not self.enabled:
            return name
        return self.dictionary.get(name, self.names[legacy].get(name, name))
