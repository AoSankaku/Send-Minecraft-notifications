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
