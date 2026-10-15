import json
from pathlib import Path

import pytest

from message.advancements import AdvancementTranslator
from message.locales import SUPPORTED_LOCALES, normalize_locale


LOCALES = {
    "ja", "en", "zh-CN", "zh-TW", "zh-HK", "hi", "es", "fr", "de",
    "pt-BR", "pt-PT", "ru", "ar", "id", "ko", "vi", "tr", "it", "pl",
    "cs", "ms", "ro",
}


@pytest.mark.parametrize("locale", sorted(LOCALES))
def test_bundled_advancement_titles_available_offline_in_every_locale(locale, monkeypatch):
    import socket

    def no_network(*args, **kwargs):
        pytest.fail("Translation must work offline")

    monkeypatch.setattr(socket, "create_connection", no_network)
    translator = AdvancementTranslator(locale)
    translated = translator.translate("Stone Age")
    assert translated
    assert translated == "Stone Age" if locale == "en" else translated != "Stone Age"
    assert translator.translate("An Unrecognized Mod Advancement") == "An Unrecognized Mod Advancement"


def test_scope_contains_exactly_first_and_second_language_ranges():
    assert set(SUPPORTED_LOCALES) == LOCALES


@pytest.mark.parametrize("value,expected", [
    ("ja", "ja"), ("ja_jp", "ja"), ("en-US", "en"),
    ("zh_cn", "zh-CN"), ("ZH-hK", "zh-HK"), ("pt_pt", "pt-PT"),
    ("hi_in", "hi"), ("es_es", "es"), ("ar_sa", "ar"),
])
def test_language_code_aliases(value, expected):
    assert normalize_locale(value) == expected


@pytest.mark.parametrize("value", ["", "xx", "../ja", "zh", "pt", "../../config"])
def test_unsupported_or_ambiguous_language_is_rejected(value):
    with pytest.raises(ValueError, match="LANGUAGE"):
        normalize_locale(value)


def test_japanese_official_progress_and_old_achievement_names():
    translator = AdvancementTranslator("ja")
    assert translator.translate("Stone Age") == "石器時代"
    assert translator.translate("Taking Inventory", legacy=True) == "所持品の確認"
    assert translator.translate("Taking Inventory") == "Taking Inventory"
    assert translator.translate("Stone Age", legacy=True) == "Stone Age"


def test_exact_custom_dictionary_wins_and_can_translate_mod_titles():
    translator = AdvancementTranslator("ja", dictionary={
        "Stone Age": "好きな訳", "The Factory Must Grow!": "工場を拡大せよ！",
    })
    assert translator.translate("Stone Age") == "好きな訳"
    assert translator.translate("The Factory Must Grow!") == "工場を拡大せよ！"
    assert translator.translate("stone age") == "stone age"


def test_disabled_preserves_names_even_with_custom_dictionary():
    translator = AdvancementTranslator("ja", enabled=False, dictionary={"Stone Age": "独自訳"})
    assert translator.translate("Stone Age") == "Stone Age"


def test_custom_dictionary_is_copied():
    dictionary = {"Custom": "独自訳"}
    translator = AdvancementTranslator("ja", dictionary=dictionary)
    dictionary["Custom"] = "changed"
    assert translator.translate("Custom") == "独自訳"


@pytest.mark.parametrize("dictionary", [[], {"": "title"}, {"title": ""}, {"a": 3}, {3: "a"}, {"a\nb": "title"}])
def test_invalid_dictionary_is_rejected(dictionary):
    with pytest.raises(ValueError, match="ADVANCEMENT_DICTIONARY"):
        AdvancementTranslator("ja", dictionary=dictionary)


def synthetic_catalog(tmp_path):
    path = tmp_path / "minecraft.json"
    path.write_text(json.dumps({"schema": 1, "versions": {
        "old": {
            "en": {"advancements.a.title": "Same", "advancements.b.title": "Unique", "achievement.old": "Legacy"},
            "ja": {"advancements.a.title": "古い訳", "advancements.b.title": "共通", "achievement.old": "実績"},
        },
        "new": {
            "en": {"advancements.a.title": "Same", "advancements.b.title": "Unique", "advancements.c.title": "Same", "advancements.d.title": "Missing"},
            "ja": {"advancements.a.title": "新しい訳", "advancements.b.title": "共通", "advancements.c.title": "別の訳"},
        },
    }}), encoding="utf-8")
    return path


def test_ambiguous_names_are_preserved_instead_of_guessed(tmp_path):
    translator = AdvancementTranslator("ja", catalog_path=synthetic_catalog(tmp_path))
    assert translator.translate("Same") == "Same"
    assert translator.translate("Unique") == "共通"
    assert translator.translate("Missing") == "Missing"
    assert translator.translate("Legacy", legacy=True) == "実績"


def test_version_selection_limits_candidates_without_resolving_same_version_collision(tmp_path):
    path = synthetic_catalog(tmp_path)
    assert AdvancementTranslator("ja", minecraft_version="old", catalog_path=path).translate("Same") == "古い訳"
    assert AdvancementTranslator("ja", minecraft_version="new", catalog_path=path).translate("Same") == "Same"


def test_custom_dictionary_can_resolve_an_ambiguous_name(tmp_path):
    translator = AdvancementTranslator("ja", catalog_path=synthetic_catalog(tmp_path), dictionary={"Same": "管理者指定"})
    assert translator.translate("Same") == "管理者指定"


def test_unknown_catalog_version_has_actionable_error():
    with pytest.raises(ValueError, match="MINECRAFT_VERSION"):
        AdvancementTranslator("ja", minecraft_version="unavailable-version")


@pytest.mark.parametrize("data", [[], {"schema": 999, "versions": {}}, {"schema": 1, "versions": {"v": {"en": []}}}])
def test_invalid_catalog_has_clear_error(tmp_path, data):
    path = tmp_path / "minecraft.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Minecraft translation"):
        AdvancementTranslator("ja", catalog_path=path)


def test_bundled_catalog_has_all_locales_and_reproducible_source_metadata():
    path = Path(__file__).resolve().parents[2] / "translations" / "minecraft.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    assert catalog["schema"] == 1
    assert {"1.11.2", "1.12.2", "1.20.1"} <= set(catalog["versions"])
    for version, languages in catalog["versions"].items():
        assert set(languages) == LOCALES, version
        assert languages["en"]
        for language, names in languages.items():
            assert names, (version, language)
            assert set(names) <= set(languages["en"])
            assert all(isinstance(value, str) and value for value in names.values())
    assert catalog["sources"]
    assert all(source["url"].startswith("https://") and len(source["sha1"]) == 40 for source in catalog["sources"])
