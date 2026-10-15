import pytest

from message.japanize import LocalJapaneseConverter


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("konnichiha", "こんにちは"),
        ("arigatou", "ありがとう"),
        ("gakkou", "がっこう"),
        ("matcha", "まっちゃ"),
        ("tcha", "っちゃ"),
        ("kan'i", "かんい"),
        ("nn", "ん"),
        ("konnnichiha", "こんにちは"),
        ("shi si chi ti tsu tu fu hu ji zi", "し し ち ち つ つ ふ ふ じ じ"),
        ("wi we", "うぃ うぇ"),
        ("kyo sya zyu", "きょ しゃ じゅ"),
        ("xa lya xtsu ltu", "ぁ ゃ っ っ"),
        ("KO-NI-CHI-HA-", "こーにーちーはー"),
        ("ArIgAtOu! 123", "ありがとう! 123"),
    ],
)
def test_converts_romaji_to_hiragana(source: str, expected: str) -> None:
    assert LocalJapaneseConverter().convert(source) == expected


def test_converts_known_tokens_and_keeps_unknown_english_tokens() -> None:
    assert LocalJapaneseConverter().convert("Hello, arigatou there!") == "Hello, ありがとう there!"


def test_custom_dictionary_overrides_builtins_and_matches_case_insensitively() -> None:
    converter = LocalJapaneseConverter({"ARIGATOU": "感謝！", "good morning": "おはようございます"})

    assert converter.convert("ArIgAtOu") == "感謝！"
    assert converter.convert("GOOD MORNING") == "おはようございます"
    assert converter.convert("hello arigatou") == "hello 感謝！"


@pytest.mark.parametrize(
    "source",
    [
        "https://arigatou.example/konnichiha",
        "arigatou.example/konnichiha",
        "contact@arigatou.example",
        "@arigatou",
        "@everyone",
        "<@123456789012345678>",
        "<@!123456789012345678>",
        "<@&123456789012345678>",
        "<#123456789012345678>",
        "`arigatou`",
        "```arigatou\nmatcha```",
        "minecraft:arigatou_item",
    ],
)
def test_protected_spans_are_not_converted(source: str) -> None:
    assert LocalJapaneseConverter().convert(source) is None


def test_converts_text_around_protected_spans_without_touching_them() -> None:
    source = "arigatou https://konnichiha.example/path @matcha `gakkou` minecraft:matcha"
    assert LocalJapaneseConverter().convert(source) == (
        "ありがとう https://konnichiha.example/path @matcha `gakkou` minecraft:matcha"
    )


@pytest.mark.parametrize(
    "source",
    [
        "こんにちは arigatou",
        "ｺﾝﾆﾁﾊ arigatou",
        "日本語だけ",
        "/arigatou",
        "$arigatou",
        "hello there",
        "123 !!!",
        "",
    ],
)
def test_skips_messages_that_are_not_safe_or_possible_to_convert(source: str) -> None:
    assert LocalJapaneseConverter().convert(source) is None


def test_unknown_token_is_not_partially_transliterated() -> None:
    assert LocalJapaneseConverter().convert("hello") is None


def test_rejects_messages_over_the_input_limit() -> None:
    assert LocalJapaneseConverter().convert("arigatou " + "x" * 4089) is None


def test_returns_none_if_dictionary_result_does_not_change_input() -> None:
    assert LocalJapaneseConverter({"hello": "hello"}).convert("hello") is None


def test_returns_none_when_repeated_dictionary_tokens_expand_past_output_limit() -> None:
    converter = LocalJapaneseConverter({"a": "x" * 1024})
    assert converter.convert("a a a a a") is None


def test_returns_none_when_whole_phrase_dictionary_result_exceeds_output_limit() -> None:
    converter = LocalJapaneseConverter({"hello": "x" * 4097})
    assert converter.convert("hello") is None
