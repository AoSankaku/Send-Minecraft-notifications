import json
import os
from pathlib import Path
import zipfile

import pytest

from message.locales import SUPPORTED_LOCALES
from message.mod_catalog import load_mod_catalog


def _jar(path: Path, resources: dict[str, str | bytes]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, contents in resources.items():
            archive.writestr(name, contents)
    return path


def _base_resources(*, locale="ja_jp", title="工場を拡大せよ！", with_death=True):
    resources = {
        "assets/create/lang/en_us.json": json.dumps({
            "create.advancement.cog_in_the_machine": "Cog in the Machine",
            "create.advancement.cog_in_the_machine.description": "Not a title",
            "death.attack.crushing_wheels": "%1$s was processed by Crushing Wheels",
            "death.fell.accident.generic": "%1$s fell from a great height",
        }),
        f"assets/create/lang/{locale}.json": json.dumps({
            "create.advancement.cog_in_the_machine": title,
            "death.attack.crushing_wheels": "%1$sは粉砕ホイールに加工された",
        }),
        "data/create/advancements/cog_in_the_machine.json": json.dumps({
            "display": {"title": {"translate": "create.advancement.cog_in_the_machine"}},
        }),
        "data/create/advancements/no_title.json": json.dumps({
            "display": {"description": {"translate": "create.advancement.cog_in_the_machine.description"}},
        }),
    }
    if not with_death:
        resources.pop(f"assets/create/lang/{locale}.json")
    return resources


def test_missing_mods_directory_is_actionable(tmp_path):
    with pytest.raises(ValueError, match="MODS_DIR"):
        load_mod_catalog(tmp_path / "missing-mods", tmp_path / "cache", "ja")


def test_empty_mods_directory_is_valid_and_creates_cache_directory(tmp_path):
    mods = tmp_path / "mods"
    mods.mkdir()
    cache = tmp_path / "cache"

    catalog = load_mod_catalog(mods, cache, "ja")

    assert catalog.advancements == {}
    assert catalog.deaths == []
    assert catalog.warnings == []
    assert catalog.cache_hits == catalog.cache_misses == 0
    assert cache.is_dir()


def test_create_like_advancement_and_death_resources_are_extracted(tmp_path):
    mods = tmp_path / "mods"
    _jar(mods / "Create.jar", _base_resources())

    catalog = load_mod_catalog(mods, tmp_path / "cache", "ja")

    assert catalog.advancements == {"Cog in the Machine": {"工場を拡大せよ！"}}
    assert ("%1$s was processed by Crushing Wheels", "%1$sは粉砕ホイールに加工された") in catalog.deaths
    assert ("%1$s fell from a great height", None) in catalog.deaths
    assert all("Not a title" not in title for title in catalog.advancements)
    assert catalog.cache_misses == 1


def test_all_supported_locales_are_extracted_into_locale_independent_cache(tmp_path, monkeypatch):
    mods = tmp_path / "mods"
    resources = _base_resources()
    for code, minecraft_locale in SUPPORTED_LOCALES.items():
        if code == "ja":
            continue
        resources[f"assets/create/lang/{minecraft_locale}.json"] = json.dumps({
            "create.advancement.cog_in_the_machine": f"{code} title",
            "death.attack.crushing_wheels": f"{code} death",
        })
    _jar(mods / "create.jar", resources)
    cache = tmp_path / "cache"
    first = load_mod_catalog(mods, cache, "ja")
    assert first.advancements["Cog in the Machine"] == {"工場を拡大せよ！"}

    original_zip_file = zipfile.ZipFile

    def no_archive_reopen(*args, **kwargs):
        pytest.fail("A locale change should reuse extracted resources from cache")

    monkeypatch.setattr(zipfile, "ZipFile", no_archive_reopen)
    second = load_mod_catalog(mods, cache, "fr")

    assert second.advancements["Cog in the Machine"] == {"fr title"}
    assert second.cache_hits == 1
    assert second.cache_misses == 0
    monkeypatch.setattr(zipfile, "ZipFile", original_zip_file)


def test_missing_target_translation_keeps_english_candidate(tmp_path):
    mods = tmp_path / "mods"
    _jar(mods / "create.jar", _base_resources(with_death=False))

    catalog = load_mod_catalog(mods, tmp_path / "cache", "ja")

    assert catalog.advancements["Cog in the Machine"] == {"Cog in the Machine"}
    assert catalog.deaths == [
        ("%1$s was processed by Crushing Wheels", None),
        ("%1$s fell from a great height", None),
    ]


def test_legacy_lang_resources_are_case_insensitive_and_interpolations_survive(tmp_path):
    mods = tmp_path / "mods"
    _jar(mods / "old-mod.JAR", {
        "assets/oldmod/lang/en_US.LANG": "oldmod.advancement.first=First Steps\n"
        "death.attack.oldmod=%1$s was zapped\n",
        "assets/oldmod/lang/ja_JP.lang": "oldmod.advancement.first=最初の一歩\n"
        "death.attack.oldmod=%1$sは感電した\n",
        "data/oldmod/advancement/first.json": json.dumps({
            "display": {"title": {"translate": "oldmod.advancement.first"}},
        }),
    })

    catalog = load_mod_catalog(mods, tmp_path / "cache", "ja")

    assert catalog.advancements == {"First Steps": {"最初の一歩"}}
    assert ("%1$s was zapped", "%1$sは感電した") in catalog.deaths


def test_fallback_title_key_patterns_exclude_description_keys(tmp_path):
    mods = tmp_path / "mods"
    _jar(mods / "mod.jar", {
        "assets/mod/lang/en_us.json": json.dumps({
            "mod.advancement.hidden": "Fallback title",
            "mod.advancement.hidden.description": "Fallback description",
            "mod.advancements.another.title": "Another title",
            "mod.achievement.old": "Old achievement",
            "mod.achievement.old.description": "Old description",
            "mod.item.machine": "Machine",
        }),
        "assets/mod/lang/ja_jp.json": json.dumps({
            "mod.advancement.hidden": "隠された目標",
            "mod.advancement.hidden.description": "説明",
            "mod.advancements.another.title": "別の目標",
            "mod.achievement.old": "旧実績",
            "mod.achievement.old.description": "旧説明",
            "mod.item.machine": "機械",
        }),
    })

    catalog = load_mod_catalog(mods, tmp_path / "cache", "ja")

    assert catalog.advancements == {
        "Fallback title": {"隠された目標"},
        "Another title": {"別の目標"},
        "Old achievement": {"旧実績"},
    }


def test_duplicate_titles_and_death_templates_preserve_ambiguity(tmp_path):
    mods = tmp_path / "mods"
    _jar(mods / "one.jar", {
        "assets/one/lang/en_us.json": json.dumps({
            "one.advancement.same": "Same Name",
            "death.attack.one": "%1$s met a machine",
        }),
        "assets/one/lang/ja_jp.json": json.dumps({
            "one.advancement.same": "同じ名前",
            "death.attack.one": "%1$sは機械に遭遇した",
        }),
    })
    _jar(mods / "two.jar", {
        "assets/two/lang/en_us.json": json.dumps({
            "two.advancement.same": "Same Name",
            "death.attack.two": "%1$s met a machine",
        }),
        "assets/two/lang/ja_jp.json": json.dumps({
            "two.advancement.same": "別の名前",
            "death.attack.two": "%1$sは機械に倒された",
        }),
    })

    catalog = load_mod_catalog(mods, tmp_path / "cache", "ja")

    assert catalog.advancements["Same Name"] == {"同じ名前", "別の名前"}
    assert catalog.deaths.count(("%1$s met a machine", "%1$sは機械に遭遇した")) == 1
    assert catalog.deaths.count(("%1$s met a machine", "%1$sは機械に倒された")) == 1


def test_cache_hit_does_not_open_archive_and_content_hash_invalidates_same_size_same_mtime(tmp_path, monkeypatch):
    mods = tmp_path / "mods"
    jar = _jar(mods / "mod.jar", _base_resources())
    cache = tmp_path / "cache"
    first = load_mod_catalog(mods, cache, "ja")
    original_stat = jar.stat()

    def no_archive_reopen(*args, **kwargs):
        pytest.fail("Valid cache hit should not reopen the jar")

    monkeypatch.setattr(zipfile, "ZipFile", no_archive_reopen)
    cached = load_mod_catalog(mods, cache, "ja")
    assert cached.cache_hits == 1
    assert cached.advancements == first.advancements

def test_content_change_rebuilds_cache_even_if_size_and_mtime_are_preserved(tmp_path):
    mods = tmp_path / "mods"
    jar = _jar(mods / "mod.jar", _base_resources(title="A title"))
    cache = tmp_path / "cache"
    load_mod_catalog(mods, cache, "ja")
    stat = jar.stat()
    data = _base_resources(title="B title")
    rewritten = _jar(jar, data)
    assert rewritten.stat().st_size == stat.st_size
    os.utime(jar, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    catalog = load_mod_catalog(mods, cache, "ja")

    assert catalog.cache_misses == 1
    assert catalog.advancements == {"Cog in the Machine": {"B title"}}


def test_removed_jar_stops_contributing_without_deleting_inactive_cache(tmp_path):
    mods = tmp_path / "mods"
    jar = _jar(mods / "mod.jar", _base_resources())
    cache = tmp_path / "cache"
    load_mod_catalog(mods, cache, "ja")
    cache_files = list(cache.glob("*.json"))
    assert len(cache_files) == 1

    jar.unlink()
    catalog = load_mod_catalog(mods, cache, "ja")

    assert catalog.advancements == {}
    assert catalog.deaths == []
    assert cache_files[0].exists()


@pytest.mark.parametrize("bad_cache", ["{broken", json.dumps({"schema": 999}), json.dumps({"schema": 1, "resources": []})])
def test_corrupt_or_stale_cache_is_rebuilt(tmp_path, bad_cache):
    mods = tmp_path / "mods"
    jar = _jar(mods / "mod.jar", _base_resources())
    cache = tmp_path / "cache"
    cache.mkdir()
    import hashlib

    cache_name = hashlib.sha256(jar.read_bytes()).hexdigest() + ".json"
    (cache / cache_name).write_text(bad_cache, encoding="utf-8")

    catalog = load_mod_catalog(mods, cache, "ja")

    assert catalog.cache_misses == 1
    assert catalog.advancements == {"Cog in the Machine": {"工場を拡大せよ！"}}


def test_non_jar_files_nested_jars_and_jar_symlinks_are_ignored(tmp_path):
    mods = tmp_path / "mods"
    mods.mkdir()
    _jar(mods / "nested" / "nested.jar", _base_resources(title="Nested"))
    (mods / "not-a-mod.jar.txt").write_text("ignored", encoding="utf-8")
    actual = _jar(tmp_path / "real.jar", _base_resources(title="Symlink"))
    try:
        (mods / "linked.jar").symlink_to(actual)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable in this environment")

    catalog = load_mod_catalog(mods, tmp_path / "cache", "ja")

    assert catalog.advancements == {}
    assert any("linked.jar" in warning for warning in catalog.warnings)


def test_broken_jar_is_warned_and_valid_sibling_is_still_loaded(tmp_path):
    mods = tmp_path / "mods"
    mods.mkdir()
    (mods / "broken.jar").write_bytes(b"not a zip archive")
    _jar(mods / "valid.jar", _base_resources())

    catalog = load_mod_catalog(mods, tmp_path / "cache", "ja")

    assert catalog.advancements == {"Cog in the Machine": {"工場を拡大せよ！"}}
    assert any("broken.jar" in warning for warning in catalog.warnings)


def test_unrelated_zip_resources_are_never_extracted_and_malformed_language_warns(tmp_path):
    mods = tmp_path / "mods"
    _jar(mods / "mod.jar", {
        "assets/mod/lang/en_us.json": "{malformed",
        "assets/mod/lang/ja_jp.json": json.dumps({"death.attack.bad": "翻訳"}),
        "../../outside.txt": "must not be extracted",
        "META-INF/secret.json": json.dumps({"not": "a language resource"}),
    })
    catalog = load_mod_catalog(mods, tmp_path / "cache", "ja")

    assert catalog.advancements == {}
    assert catalog.deaths == []
    assert any("assets/mod/lang/en_us.json" in warning for warning in catalog.warnings)
    assert not (tmp_path / "outside.txt").exists()


def test_entry_and_archive_limits_skip_oversized_resources_without_extracting_them(tmp_path):
    mods = tmp_path / "mods"
    _jar(mods / "large.jar", {
        "assets/mod/lang/en_us.json": " " * (8 * 1024 * 1024 + 1),
        "assets/mod/lang/ja_jp.json": "{}",
    })

    catalog = load_mod_catalog(mods, tmp_path / "cache", "ja")

    assert catalog.advancements == {}
    assert catalog.deaths == []
    assert any("limit" in warning.lower() for warning in catalog.warnings)


def test_cache_directory_and_cache_file_symlinks_are_rejected(tmp_path):
    mods = tmp_path / "mods"
    _jar(mods / "mod.jar", _base_resources())
    outside = tmp_path / "outside"
    outside.mkdir()
    cache_link = tmp_path / "cache-link"
    try:
        cache_link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable in this environment")

    with pytest.raises(ValueError, match="cache|CACHE"):
        load_mod_catalog(mods, cache_link, "ja")


def test_invalid_locale_is_rejected(tmp_path):
    mods = tmp_path / "mods"
    mods.mkdir()

    with pytest.raises(ValueError, match="LANGUAGE"):
        load_mod_catalog(mods, tmp_path / "cache", "xx")
