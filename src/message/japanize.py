"""Small, deterministic, offline romaji-to-hiragana conversion for chat."""

from __future__ import annotations

import re
from collections.abc import Mapping


_VOWELS = "aiueo"
_SYLLABLES: dict[str, str] = {
    vowel: kana for vowel, kana in zip(_VOWELS, "あいうえお", strict=True)
}


def _add_series(romaji: str, kana: str) -> None:
    for vowel, character in zip(_VOWELS, kana, strict=True):
        _SYLLABLES[romaji + vowel] = character


for _romaji, _kana in (
    ("k", "かきくけこ"),
    ("s", "さしすせそ"),
    ("t", "たちつてと"),
    ("n", "なにぬねの"),
    ("h", "はひふへほ"),
    ("m", "まみむめも"),
    ("r", "らりるれろ"),
    ("w", "わいうえを"),
    ("g", "がぎぐげご"),
    ("z", "ざじずぜぞ"),
    ("d", "だぢづでど"),
    ("b", "ばびぶべぼ"),
    ("p", "ぱぴぷぺぽ"),
    ("c", "かきくけこ"),
):
    _add_series(_romaji, _kana)

_SYLLABLES.update({"ya": "や", "yu": "ゆ", "yo": "よ"})
_SYLLABLES.update(
    {"fa": "ふぁ", "fi": "ふぃ", "fu": "ふ", "fe": "ふぇ", "fo": "ふぉ"}
)
_SYLLABLES.update({"wi": "うぃ", "we": "うぇ"})

_SYLLABLES.update(
    {
        # Hepburn, Kunrei-shiki, and common IME spellings.
        "shi": "し",
        "si": "し",
        "sha": "しゃ",
        "shu": "しゅ",
        "sho": "しょ",
        "sya": "しゃ",
        "syu": "しゅ",
        "syo": "しょ",
        "chi": "ち",
        "ti": "ち",
        "tsu": "つ",
        "tu": "つ",
        "cha": "ちゃ",
        "chu": "ちゅ",
        "cho": "ちょ",
        "tya": "ちゃ",
        "tyu": "ちゅ",
        "tyo": "ちょ",
        "fu": "ふ",
        "hu": "ふ",
        "ji": "じ",
        "zi": "じ",
        "ja": "じゃ",
        "ju": "じゅ",
        "jo": "じょ",
        "zya": "じゃ",
        "zyu": "じゅ",
        "zyo": "じょ",
        "jya": "じゃ",
        "jyu": "じゅ",
        "jyo": "じょ",
        "dya": "ぢゃ",
        "dyu": "ぢゅ",
        "dyo": "ぢょ",
        "tsa": "つぁ",
        "tsi": "つぃ",
        "tse": "つぇ",
        "tso": "つぉ",
        "kwa": "くぁ",
        "kwi": "くぃ",
        "kwe": "くぇ",
        "kwo": "くぉ",
        "gwa": "ぐぁ",
        "gwi": "ぐぃ",
        "gwe": "ぐぇ",
        "gwo": "ぐぉ",
    }
)

for _consonant, _kana in (
    ("ky", "き"),
    ("sh", "し"),
    ("ch", "ち"),
    ("ny", "に"),
    ("hy", "ひ"),
    ("my", "み"),
    ("ry", "り"),
    ("gy", "ぎ"),
    ("by", "び"),
    ("py", "ぴ"),
    ("dy", "ぢ"),
):
    for _vowel, _small in zip("auo", "ゃゅょ", strict=True):
        _SYLLABLES[_consonant + _vowel] = _kana + _small

for _prefix, _kana in (("x", "ぁぃぅぇぉ"), ("l", "ぁぃぅぇぉ")):
    for _vowel, _small in zip(_VOWELS, _kana, strict=True):
        _SYLLABLES[_prefix + _vowel] = _small
    for _tail, _small in (
        ("ya", "ゃ"),
        ("yu", "ゅ"),
        ("yo", "ょ"),
        ("wa", "ゎ"),
        ("ka", "ゕ"),
        ("ke", "ゖ"),
        ("tsu", "っ"),
        ("tu", "っ"),
    ):
        _SYLLABLES[_prefix + _tail] = _small

# Preserve code, links, email addresses, Discord mentions, and namespaced
# Minecraft identifiers exactly as typed.
_PROTECTED_SPAN = re.compile(
    r"```[\s\S]*?(?:```|$)"
    r"|`[^`\n]*`"
    r"|(?:https?://|www\.)[^\s<>`]+"
    r"|[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    r"|(?<![@\w])(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?:/[^\s<>`]*)?"
    r"|<[@#][!&]?\d+>"
    r"|(?<![A-Za-z0-9_])@[A-Za-z0-9_.-]+"
    r"|(?<![A-Za-z0-9_])[A-Za-z0-9_.-]+:[A-Za-z0-9_./-]+",
    re.IGNORECASE,
)
_ROMAJI_TOKEN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)*(?:-[A-Za-z]+)*-?")
_HIRAGANA_OR_JAPANESE = re.compile(
    r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff\uff66-\uff9f]"
)
_MAX_INPUT_LENGTH = 4096
_CONSONANTS = frozenset("bcdfghjklmpqrstvwxyz")


def _convert_token(token: str) -> str | None:
    source = token.casefold()
    result: list[str] = []
    index = 0

    while index < len(source):
        character = source[index]

        if character == "-":
            if not result:
                return None
            result.append("ー")
            index += 1
            continue

        if character == "n":
            following = source[index + 1 : index + 2]
            after_following = source[index + 2 : index + 3]
            if following == "'":
                result.append("ん")
                index += 2
                continue
            if following == "n":
                # Leave the second n available to begin a syllable when it is
                # followed by a vowel/y (konnichiha, nna, nnya).
                result.append("ん")
                index += 1 if after_following in {*_VOWELS, "y"} else 2
                continue
            if not following:
                result.append("ん")
                index += 1
                continue
            if following in _CONSONANTS and following != "y":
                result.append("ん")
                index += 1
                continue

        if source.startswith("tch", index) and "ch" + source[index + 3 : index + 4] in _SYLLABLES:
            result.append("っ")
            index += 1
            continue

        if (
            character in _CONSONANTS
            and character != "n"
            and source[index : index + 2] == character * 2
            and character in "kstchmrgzdbpf"
        ):
            result.append("っ")
            index += 1
            continue

        match = None
        for end in range(min(len(source), index + 4), index, -1):
            candidate = source[index:end]
            if candidate in _SYLLABLES:
                match = (candidate, _SYLLABLES[candidate])
                break
        if match is None:
            return None
        syllable, kana = match
        result.append(kana)
        index += len(syllable)

    return "".join(result)


class LocalJapaneseConverter:
    """Convert recognizable romaji tokens locally, without network access."""

    def __init__(self, dictionary: Mapping[str, str] | None = None) -> None:
        self._dictionary = {
            source.casefold(): target for source, target in (dictionary or {}).items()
        }

    def convert(self, text: str) -> str | None:
        if (
            not text
            or len(text) > _MAX_INPUT_LENGTH
            or text.startswith(("/", "$"))
            or _HIRAGANA_OR_JAPANESE.search(text)
        ):
            return None

        if not _PROTECTED_SPAN.search(text):
            phrase = self._dictionary.get(text.casefold())
            if phrase is not None:
                return phrase if phrase != text and len(phrase) <= _MAX_INPUT_LENGTH else None

        changed = False
        output: list[str] = []
        cursor = 0
        output_length = 0

        def convert_unprotected(segment: str, remaining: int) -> str | None:
            nonlocal changed
            parts: list[str] = []
            token_cursor = 0
            segment_length = 0

            def append_part(part: str) -> bool:
                nonlocal segment_length
                if segment_length + len(part) > remaining:
                    return False
                parts.append(part)
                segment_length += len(part)
                return True

            for token_match in _ROMAJI_TOKEN.finditer(segment):
                if not append_part(segment[token_cursor : token_match.start()]):
                    return None
                token = token_match.group()
                converted = self._dictionary.get(token.casefold())
                if converted is None:
                    converted = _convert_token(token)
                if converted is None:
                    converted = token
                else:
                    changed |= converted != token
                if not append_part(converted):
                    return None
                token_cursor = token_match.end()
            if not append_part(segment[token_cursor:]):
                return None
            return "".join(parts)

        for protected in _PROTECTED_SPAN.finditer(text):
            converted_segment = convert_unprotected(
                text[cursor : protected.start()], _MAX_INPUT_LENGTH - output_length
            )
            if converted_segment is None:
                return None
            output.append(converted_segment)
            output_length += len(converted_segment)
            protected_text = protected.group()
            if output_length + len(protected_text) > _MAX_INPUT_LENGTH:
                return None
            output.append(protected_text)
            output_length += len(protected_text)
            cursor = protected.end()
        converted_segment = convert_unprotected(
            text[cursor:], _MAX_INPUT_LENGTH - output_length
        )
        if converted_segment is None:
            return None
        output.append(converted_segment)

        converted_text = "".join(output)
        return converted_text if changed and converted_text != text else None
