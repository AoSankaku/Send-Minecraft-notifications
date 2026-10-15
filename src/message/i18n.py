import json
from pathlib import Path

from message.constant import EventIds
from message.locales import SUPPORTED_LOCALES, normalize_locale
from utils.runtime import resource_path

class I18n:
    def __init__(self):
        self.current_lang = "ja_jp"
        self.lang_priority = []
        self.loaded_lang = []
        self.lang_data: dict[str, dict[str, str]] = {}

    def load_translation(self, language_code: str, filepath: str) -> bool:
        translation_path = Path(filepath)
        if not translation_path.exists():
            return False
        self.lang_data[language_code] = self._read_catalog(translation_path)
        if language_code not in self.loaded_lang:
            self.loaded_lang.append(language_code)
        return True

    @staticmethod
    def _read_catalog(filepath: Path) -> dict[str, str]:
        try:
            with filepath.open(encoding="utf-8") as source:
                data = json.load(source)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid translation file: {filepath}") from error
        if not isinstance(data, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in data.items()
        ):
            raise ValueError("Translation data must be an object containing string values.")
        return data

    @classmethod
    def for_config(cls, config_path: str | Path, locale: str = "ja") -> "I18n":
        """Load English defaults, the selected bundled catalog, and local overrides."""
        language = normalize_locale(locale)
        mc_locale = SUPPORTED_LOCALES[language]
        english_locale = SUPPORTED_LOCALES["en"]
        english_path = resource_path(f"translations/{english_locale}.json")
        selected_path = resource_path(f"translations/{mc_locale}.json")
        merged = cls._read_catalog(english_path)
        if mc_locale != english_locale and selected_path.exists():
            merged.update(cls._read_catalog(selected_path))

        custom_path = Path(config_path).parent / "translations" / f"{mc_locale}.json"
        if custom_path.is_file():
            merged.update(cls._read_catalog(custom_path))

        translator = cls()
        translator.current_lang = mc_locale
        translator.lang_data[mc_locale] = merged
        translator.loaded_lang.append(mc_locale)
        return translator

    def translate(self, event_id: EventIds) -> str | None:
        if self.current_lang not in self.loaded_lang:
            return None
        return self.lang_data[self.current_lang].get(event_id.value, "")
