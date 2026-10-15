import json

import pytest

from update_minecraft_translations import read_language, title_entries, download


def test_json_language_and_legacy_language_are_read_without_executing_content():
    assert read_language(json.dumps({"advancements.a.title": "石器時代"}).encode(), ".json") == {
        "advancements.a.title": "石器時代",
    }
    assert read_language("# comment\nachievement.a=所持品の確認\nother=with=equals\n".encode(), ".lang") == {
        "achievement.a": "所持品の確認", "other": "with=equals",
    }


def test_only_progress_titles_and_old_achievement_names_are_retained():
    assert title_entries({
        "advancements.story.mine_stone.title": "Stone Age",
        "advancements.story.mine_stone.description": "Mine stone",
        "achievement.openInventory": "Taking Inventory",
        "achievement.openInventory.desc": "Press E",
        "achievement.get": "Achievement get!",
        "achievement.taken": "Achievement taken!",
        "chat.type.advancement.task": "%s made %s",
    }) == {
        "advancements.story.mine_stone.title": "Stone Age",
        "achievement.openInventory": "Taking Inventory",
    }


@pytest.mark.parametrize("data", [b"[]", b"null", b'{"title":1}', b"invalid"])
def test_malformed_language_data_is_rejected(data):
    with pytest.raises(ValueError):
        read_language(data, ".json")


def test_cached_download_still_checks_digest(tmp_path):
    import hashlib

    data = b"verified data"
    checksum = hashlib.sha1(data).hexdigest()
    (tmp_path / checksum).write_bytes(data)
    assert download("https://resources.download.minecraft.net/ab/" + checksum, checksum, tmp_path) == data
    (tmp_path / checksum).write_bytes(b"tampered")
    # Must not trust corrupted cached content or make a network request.
    with pytest.raises(ValueError, match="checksum"):
        download("https://resources.download.minecraft.net/ab/" + checksum, checksum, tmp_path)


@pytest.mark.parametrize("url", ["http://resources.download.minecraft.net/file", "https://example.com/file", "file:///etc/passwd"])
def test_download_only_accepts_official_https_sources(tmp_path, url):
    with pytest.raises(ValueError, match="official HTTPS"):
        download(url, "a" * 40, tmp_path)
