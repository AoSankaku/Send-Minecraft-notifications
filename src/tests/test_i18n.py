from pathlib import Path

import pytest
from message.i18n import I18n
from message.constant import EventIds
from message.locales import SUPPORTED_LOCALES
from utils.runtime import translation_path

class TestI18n:
    @pytest.fixture
    def init_translator(self):
        self.translator = I18n()
        self.translator.load_translation("ja_jp", "translations/ja_jp.json")

    def test__can_translate_ja_jp(self, init_translator):
        assert self.translator.translate(EventIds.ON_JOIN) != None

    @pytest.mark.parametrize("data", ['[]', 'null', '{"on_join": 123}'])
    def test_invalid_translation_shapes_rejected(self, tmp_path, data):
        translation = tmp_path / "ja_jp.json"
        translation.write_text(data, encoding="utf-8")
        with pytest.raises(ValueError, match="Translation data"):
            I18n().load_translation("ja_jp", str(translation))


def test_legacy_translation_loading_and_default_path_stay_japanese():
    translator = I18n()
    assert translator.load_translation("ja_jp", "translations/ja_jp.json")
    assert translator.current_lang == "ja_jp"
    assert translator.translate(EventIds.ON_JOIN)
    assert translation_path(Path("config.toml")).name == "ja_jp.json"


def test_locale_factory_loads_selected_bundled_catalog(tmp_path):
    translator = I18n.for_config(tmp_path / "config.toml", "es")
    japanese = I18n()
    japanese.load_translation("ja_jp", "translations/ja_jp.json")

    assert translator.current_lang == SUPPORTED_LOCALES["es"]
    assert translator.translate(EventIds.ON_JOIN)
    assert translator.translate(EventIds.ON_JOIN) != japanese.translate(EventIds.ON_JOIN)


def test_locale_factory_overlays_custom_keys_and_falls_back_to_english(
    tmp_path, monkeypatch
):
    import message.i18n as i18n_module

    config_path = tmp_path / "send-minecraft-notifications.toml"
    custom_dir = tmp_path / "translations"
    custom_dir.mkdir()
    (custom_dir / "fr_fr.json").write_text(
        '{"on_join": "custom %player-name%"}', encoding="utf-8"
    )

    resources = tmp_path / "resources"
    bundled = resources / "translations"
    bundled.mkdir(parents=True)
    (bundled / "en_us.json").write_text(
        '{"on_join": "English %player-name%", "on_left": "English left"}',
        encoding="utf-8",
    )
    (bundled / "fr_fr.json").write_text(
        '{"on_join": "French %player-name%"}', encoding="utf-8"
    )
    monkeypatch.setattr(
        i18n_module,
        "resource_path",
        lambda relative: resources / relative,
        raising=False,
    )

    translator = I18n.for_config(config_path, "fr")

    assert translator.translate(EventIds.ON_JOIN) == "custom %player-name%"
    assert translator.translate(EventIds.ON_LEFT) == "English left"


def test_locale_factory_rejects_unknown_locale_and_invalid_custom_catalog(tmp_path):
    with pytest.raises(ValueError, match="locale|LANGUAGE|言語"):
        I18n.for_config(tmp_path / "config.toml", "xx")

    custom_dir = tmp_path / "translations"
    custom_dir.mkdir()
    (custom_dir / "de_de.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="Translation data"):
        I18n.for_config(tmp_path / "config.toml", "de")
