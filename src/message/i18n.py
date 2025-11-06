import json
from os import path

from message.model import MessageData
from message.constant import EventIds

class I18n:
    def __init__(self):
        self.current_lang = "ja_jp"
        self.lang_priority = []
        self.loaded_lang = []
        self.lang_data: dict[str, dict[str, str]] = {}

    def load_translation(self, language_code: str, filepath: str) -> bool:
        if(path.exists(filepath)):
            data = None
            with open(filepath) as f:
                data = json.loads(f.read())
            if data == None:
                return False
            self.lang_data[language_code] = data
            self.loaded_lang.append(language_code)
            return True
        return False

    def translate(self, event_id: EventIds) -> str | None:
        if self.current_lang not in self.loaded_lang:
            return None
        return self.lang_data[self.current_lang].get(event_id.value, "")
