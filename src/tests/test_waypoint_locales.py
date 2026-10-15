"""Acceptance tests for shared waypoint notification translations."""

import json
import re
from pathlib import Path

import pytest


LOCALE_FILES = (
    "ar_sa",
    "cs_cz",
    "de_de",
    "en_us",
    "es_es",
    "fr_fr",
    "hi_in",
    "id_id",
    "it_it",
    "ja_jp",
    "ko_kr",
    "ms_my",
    "pl_pl",
    "pt_br",
    "pt_pt",
    "ro_ro",
    "ru_ru",
    "tr_tr",
    "vi_vn",
    "zh_cn",
    "zh_hk",
    "zh_tw",
)
EVENT_KEY = "on_shared_waypoint_created"
REQUIRED_PLACEHOLDERS = {
    "%waypoint-name%",
    "%waypoint-dimension%",
    "%waypoint-x%",
    "%waypoint-y%",
    "%waypoint-z%",
}
PLACEHOLDER_PATTERN = re.compile(r"%[A-Za-z0-9_-]+%")


@pytest.mark.parametrize("locale_file", LOCALE_FILES)
def test_shared_waypoint_created_catalog_has_required_placeholders(locale_file):
    catalog_path = Path(__file__).resolve().parents[2] / "translations" / f"{locale_file}.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    assert EVENT_KEY in catalog, locale_file
    assert set(PLACEHOLDER_PATTERN.findall(catalog[EVENT_KEY])) == REQUIRED_PLACEHOLDERS, locale_file
