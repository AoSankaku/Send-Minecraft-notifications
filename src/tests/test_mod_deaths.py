import pytest

from message.mod_deaths import DeathTranslator


CRUSH = ("%1$s was processed by Crushing Wheels", "%1$sは破砕ホイールによって加工された")


def test_create_death_translation_preserves_victim_name():
    result = DeathTranslator([CRUSH]).translate("Alice was processed by Crushing Wheels")
    assert result is not None
    assert result.player == "Alice"
    assert result.text == "Aliceは破砕ホイールによって加工された"


def test_indexed_arguments_can_reorder_and_leave_player_and_item_names_literal():
    translator = DeathTranslator([(
        "%1$s was slain by %2$s using %3$s",
        "%2$sは%3$sを使って%1$sを倒した",
    )])
    result = translator.translate("Alice was slain by Bob using [Custom %server-count% Sword]")
    assert result.text == "Bobは[Custom %server-count% Sword]を使ってAliceを倒した"


def test_unindexed_arguments_and_literal_percent():
    translator = DeathTranslator([("%s was 100%% crushed by %s", "%2$sが%1$sを100%%破砕した")])
    assert translator.translate("Alice was 100% crushed by Bob").text == "BobがAliceを100%破砕した"


def test_repeated_arguments_must_match_and_are_not_retranslated():
    translator = DeathTranslator([("%1$s hurt %1$s", "%1$sが自滅した")])
    assert translator.translate("Alice hurt Alice").text == "Aliceが自滅した"
    assert translator.translate("Alice hurt Bob") is None


def test_missing_translation_keeps_recognized_death_original():
    result = DeathTranslator([(CRUSH[0], None)]).translate("Alice was processed by Crushing Wheels")
    assert result.player == "Alice"
    assert result.text == "Alice was processed by Crushing Wheels"


def test_conflicting_matches_keep_original_instead_of_guessing():
    source = "Alice was processed by Crushing Wheels"
    translator = DeathTranslator([CRUSH, (CRUSH[0], "%1$sは別の原因で死亡した")])
    result = translator.translate(source)
    assert result.text == source
    assert DeathTranslator([CRUSH, (CRUSH[0], None)]).translate(source).text == source


def test_distinct_templates_matching_same_line_are_also_ambiguous():
    source = "Alice was crushed by Bob"
    translator = DeathTranslator([
        ("%1$s was crushed by %2$s", "%1$sを%2$sが破砕した"),
        ("%1$s was crushed by Bob", "%1$sは機械に破砕された"),
    ])
    assert translator.translate(source).text == source


@pytest.mark.parametrize("text", [
    "<Alice> Alice was processed by Crushing Wheels",
    "[Server] Alice was processed by Crushing Wheels",
    "[Alice: Alice was processed by Crushing Wheels]",
    "Alice was processed by Crushing Wheels extra",
    "Invalid Player was processed by Crushing Wheels",
    "Alice was processed by Crushing Wheels\nOther log",
])
def test_non_death_or_non_player_record_is_not_matched(text):
    assert DeathTranslator([CRUSH]).translate(text) is None


@pytest.mark.parametrize("english,target", [
    ("%1$s%2$s", "%1$s死亡"),
    ("%1$d died", "%1$s死亡"),
    ("%1$s was crushed", "%2$s死亡"),
    ("plain diagnostic", "翻訳"),
])
def test_unsupported_or_inconsistent_templates_are_not_guessed(english, target):
    translator = DeathTranslator([(english, target)])
    assert translator.translate("Alice was crushed") is None or translator.translate("Alice was crushed").text == "Alice was crushed"


def test_ambiguous_argument_boundaries_preserve_original():
    source = "Alice was slain by Bob using Foo using Bar"
    translator = DeathTranslator([("%1$s was slain by %2$s using %3$s", "%1$s %2$s %3$s")])
    assert translator.translate(source).text == source


def test_long_untrusted_input_and_excessive_placeholders_do_not_match():
    translator = DeathTranslator([("%1$s a %2$s a %3$s", "%1$s %2$s %3$s")])
    assert translator.translate("Alice " + "a " * 20000) is None


def test_translation_cannot_silently_discard_killer_or_item_arguments():
    source = "Alice was slain by Bob using [Named Sword]"
    translator = DeathTranslator([("%1$s was slain by %2$s using %3$s", "%1$sは死亡した")])
    assert translator.translate(source).text == source
