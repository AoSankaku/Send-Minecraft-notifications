"""Render original/Japanese public chat using logged results or local conversion."""
import re

from message.japanize import LocalJapaneseConverter


JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uff66-\uff9f]")


def validate_server_format(template: str) -> str:
    if not template:
        return template
    if len(template) > 512 or any(template.count(token) != 1 for token in ("{original}", "{japanese}")):
        raise ValueError("Invalid setting: JAPANIZE_SERVER_FORMAT")
    remaining = template.replace("{original}", "").replace("{japanese}", "")
    if "{" in remaining or "}" in remaining or not remaining:
        raise ValueError("Invalid setting: JAPANIZE_SERVER_FORMAT")
    if "{original}{japanese}" in template or "{japanese}{original}" in template:
        raise ValueError("Invalid setting: JAPANIZE_SERVER_FORMAT")
    return template


class JapaneseChatFormatter:
    def __init__(self, *, enabled=False, mode="auto", dictionary=None, server_format=""):
        if mode not in {"auto", "local", "server"}:
            raise ValueError("Invalid setting: JAPANIZE_MODE")
        self.enabled = enabled
        self.mode = mode
        self.converter = LocalJapaneseConverter(dictionary)
        formats = ([validate_server_format(server_format)] if server_format else []) + [
            "{original} ({japanese})", "{original}\n→ {japanese}",
        ]
        self.server_patterns = [
            re.compile(re.escape(template)
                       .replace(re.escape("{original}"), r"(?P<original>[^\r\n]+?)")
                       .replace(re.escape("{japanese}"), r"(?P<japanese>[^\r\n]+)"))
            for template in formats
        ]

    def format_message(self, text: str, template: str = "%player-message%") -> str:
        def render(message):
            return template.replace("%player-message%", message)

        if not self.enabled or len(text) > 4096 or "%player-message%" not in template:
            return render(text)
        original = text
        japanese = None
        for pattern in self.server_patterns:
            match = pattern.fullmatch(text)
            if match and JAPANESE.search(match["japanese"]):
                original, japanese = match["original"], match["japanese"]
                break
        if self.mode == "local" or (japanese is None and self.mode == "auto"):
            japanese = self.converter.convert(original)
        if japanese is None or japanese == original:
            return render(original)
        return f"{render(original)}\n↳ {render(japanese)}"
