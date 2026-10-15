"""Acceptance tests for selectable notification catalogs and advancement names."""

import json
import re
from pathlib import Path

import pytest

from handlers.secrets import BotEnv
from main import cli
from message.constant import EventIds
from message.i18n import I18n
from message.locales import SUPPORTED_LOCALES, normalize_locale
from message.parser import LogParser
from utils.runtime import resource_path, translation_path


LOCALES = {
    "ja": "ja_jp",
    "en": "en_us",
    "zh-CN": "zh_cn",
    "zh-TW": "zh_tw",
    "zh-HK": "zh_hk",
    "hi": "hi_in",
    "es": "es_es",
    "fr": "fr_fr",
    "de": "de_de",
    "pt-BR": "pt_br",
    "pt-PT": "pt_pt",
    "ru": "ru_ru",
    "ar": "ar_sa",
    "id": "id_id",
    "ko": "ko_kr",
    "vi": "vi_vn",
    "tr": "tr_tr",
    "it": "it_it",
    "pl": "pl_pl",
    "cs": "cs_cz",
    "ms": "ms_my",
    "ro": "ro_ro",
}
WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/" + "test-token-" * 6
PLACEHOLDER = re.compile(r"%[A-Za-z0-9_-]+%")


def _catalog(mc_locale: str) -> dict[str, str]:
    path = resource_path(f"translations/{mc_locale}.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_supported_locales_cover_the_second_language_scope():
    assert SUPPORTED_LOCALES == LOCALES
    for language, mc_locale in LOCALES.items():
        assert normalize_locale(language) == language
        assert normalize_locale(mc_locale.upper()) == language


def test_all_notification_catalogs_have_complete_keys_and_placeholders():
    expected_keys = {event.value for event in EventIds if event is not EventIds.NONE}
    catalogs = {locale: _catalog(mc_locale) for locale, mc_locale in LOCALES.items()}
    japanese = catalogs["ja"]

    assert set(japanese) == expected_keys
    for locale, catalog in catalogs.items():
        assert set(catalog) == expected_keys, locale
        for event_id in expected_keys:
            assert set(PLACEHOLDER.findall(catalog[event_id])) == set(
                PLACEHOLDER.findall(japanese[event_id])
            ), (locale, event_id)


@pytest.mark.parametrize("locale", ["es", "fr", "zh-CN", "pt-BR", "ar"])
def test_locale_factory_selects_a_non_japanese_notification_catalog(tmp_path, locale):
    translator = I18n.for_config(tmp_path / "config.toml", locale)
    assert translator.current_lang == LOCALES[locale]
    assert translator.translate(EventIds.ON_JOIN) == _catalog(LOCALES[locale])["on_join"]
    assert translator.translate(EventIds.ON_JOIN) != _catalog("ja_jp")["on_join"]


def test_locale_factory_uses_japanese_by_default_and_rejects_unknown_locale(tmp_path):
    assert I18n.for_config(tmp_path / "config.toml").current_lang == "ja_jp"
    with pytest.raises(ValueError, match="locale|language|言語"):
        I18n.for_config(tmp_path / "config.toml", "unsupported")
    with pytest.raises(ValueError):
        normalize_locale("unsupported")


def test_translation_path_accepts_canonical_locale_and_keeps_legacy_default(tmp_path):
    config = tmp_path / "send-minecraft-notifications.toml"
    custom_dir = tmp_path / "translations"
    custom_dir.mkdir()
    custom = custom_dir / "pt_br.json"
    custom.write_text("{}", encoding="utf-8")

    assert translation_path(config).name == "ja_jp.json"
    assert translation_path(config, "pt-BR") == custom
    assert translation_path(config, "pt_br") == custom


def test_custom_catalog_overlays_selected_locale_by_key(tmp_path):
    custom_dir = tmp_path / "translations"
    custom_dir.mkdir()
    (custom_dir / "fr_fr.json").write_text(
        json.dumps({"on_join": "customized %player-name%"}), encoding="utf-8"
    )

    translator = I18n.for_config(tmp_path / "config.toml", "fr")
    assert translator.translate(EventIds.ON_JOIN) == "customized %player-name%"
    assert translator.translate(EventIds.ON_LEFT) == _catalog("fr_fr")["on_left"]


@pytest.mark.parametrize("locale", ["fr", "es"])
def test_check_config_validates_selected_translation_without_running_server(
    tmp_path, monkeypatch, capsys, locale
):
    config = tmp_path / "config.toml"
    config.write_text(f'WEBHOOK_URL = "{WEBHOOK}"\nLANGUAGE = "{locale}"\n', encoding="utf-8")
    monkeypatch.setattr("main.main", lambda *_args, **_kwargs: pytest.fail("server must not start"))

    assert cli(["--config", str(config), "--check-config"]) == 0
    assert "No notifications were sent" in capsys.readouterr().out


def test_invalid_selected_custom_catalog_is_reported_by_check_config(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text(f'WEBHOOK_URL = "{WEBHOOK}"\nLANGUAGE = "de"\n', encoding="utf-8")
    custom_dir = tmp_path / "translations"
    custom_dir.mkdir()
    (custom_dir / "de_de.json").write_text("[]", encoding="utf-8")

    assert cli(["--config", str(config), "--check-config"]) == 1
    assert "Translation data" in capsys.readouterr().err


class RecordingAdvancementTranslator:
    def __init__(self):
        self.calls = []

    def translate(self, name: str, *, legacy: bool = False) -> str:
        self.calls.append((name, legacy))
        return "最初の村" if name == "First Village" else name


class EventTemplates:
    def translate(self, event_id):
        return {
            EventIds.ON_ADVANCEMENT_COMPLETE: "advancement %advancement-name%",
            EventIds.ON_GOAL_COMPLETE: "goal %goal-name%",
            EventIds.ON_CHALLENGE_COMPLETE: "challenge %challenge-name%",
            EventIds.ON_ACHIEVEMENTS_COMPLETE_OLD: "old %challenge-name%",
        }.get(event_id)


@pytest.mark.parametrize(
    ("line", "title", "legacy", "expected_text"),
    [
        (
            "user has made the advancement [First Village]",
            "First Village",
            False,
            "advancement 最初の村",
        ),
        (
            "user has reached the goal [First Village]",
            "First Village",
            False,
            "goal 最初の村",
        ),
        (
            "user has completed the challenge [First Village]",
            "First Village",
            False,
            "challenge 最初の村",
        ),
        (
            "user has just earned the achievement [First Village]",
            "First Village",
            True,
            "old 最初の村",
        ),
    ],
)
def test_parser_translates_titles_for_all_milestone_events(line, title, legacy, expected_text):
    advancement_translator = RecordingAdvancementTranslator()
    parser = LogParser(
        "", "", "", "", [], advancement_translator=advancement_translator
    )

    result = parser.parse(
        f"[16Jul2024 18:04:05.111] [Server thread/INFO] "
        f"[net.minecraft.server.MinecraftServer/]: {line}",
        EventTemplates(),
    )

    assert result is not None
    assert result.text == expected_text
    assert advancement_translator.calls == [(title, legacy)]


def test_config_exposes_locale_and_advancement_translation_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBHOOK_URL", WEBHOOK)
    BotEnv.init(tmp_path / "not-present.toml")
    assert BotEnv.Language.get() == "ja"
    assert BotEnv.AdvancementTranslationEnabled.getBool()
    assert BotEnv.AdvancementDictionary.get() == "{}"
    assert BotEnv.MinecraftVersion.get() == ""

    config = tmp_path / "config.toml"
    config.write_text(
        'LANGUAGE = "pt-BR"\n'
        'ADVANCEMENT_TRANSLATION_ENABLED = false\n'
        '[ADVANCEMENT_DICTIONARY]\n"First Village" = "A Primeira Aldeia"\n'
        'MINECRAFT_VERSION = "1.20.1"\n',
        encoding="utf-8",
    )
    BotEnv.init(config)
    assert BotEnv.Language.get() == "pt-BR"
    assert not BotEnv.AdvancementTranslationEnabled.getBool()
    assert json.loads(BotEnv.AdvancementDictionary.get()) == {"First Village": "A Primeira Aldeia"}
    assert BotEnv.MinecraftVersion.get() == "1.20.1"

