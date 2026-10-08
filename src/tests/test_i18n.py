import pytest
from message.i18n import I18n
from message.constant import EventIds

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
