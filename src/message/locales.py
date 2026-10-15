"""Supported user locale codes and their Minecraft language resource names."""

SUPPORTED_LOCALES = {
    "ja": "ja_jp", "en": "en_us", "zh-CN": "zh_cn", "zh-TW": "zh_tw",
    "zh-HK": "zh_hk", "hi": "hi_in", "es": "es_es", "fr": "fr_fr",
    "de": "de_de", "pt-BR": "pt_br", "pt-PT": "pt_pt", "ru": "ru_ru",
    "ar": "ar_sa", "id": "id_id", "ko": "ko_kr", "vi": "vi_vn",
    "tr": "tr_tr", "it": "it_it", "pl": "pl_pl", "cs": "cs_cz",
    "ms": "ms_my", "ro": "ro_ro",
}

_ALIASES = {
    alias.replace("_", "-").casefold(): code
    for code, minecraft in SUPPORTED_LOCALES.items()
    for alias in (code, minecraft)
}


def normalize_locale(value: str) -> str:
    if isinstance(value, str):
        result = _ALIASES.get(value.replace("_", "-").casefold())
        if result is not None:
            return result
    raise ValueError("Invalid LANGUAGE; choose: " + ", ".join(SUPPORTED_LOCALES))
