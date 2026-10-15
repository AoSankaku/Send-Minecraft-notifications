"""Read mod language resources without loading or executing Minecraft code."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile
import zlib

from message.locales import SUPPORTED_LOCALES, normalize_locale


_SCHEMA = 3
_MAX_ENTRY_BYTES = 8 * 1024 * 1024
_MAX_JAR_SELECTED_BYTES = 64 * 1024 * 1024
_MAX_ARCHIVE_MEMBERS = 100_000
_MAX_CACHE_BYTES = 128 * 1024 * 1024
_NAMESPACE = re.compile(r"^[a-z0-9_.-]+$", re.IGNORECASE)
_LANGUAGE_LOCALES = tuple(dict.fromkeys(SUPPORTED_LOCALES.values()))
_LOCALE_BY_FILE = {locale.casefold(): locale for locale in _LANGUAGE_LOCALES}
_LOCALE_BY_FILE.update({
    locale.replace("_", "-").casefold(): locale for locale in _LANGUAGE_LOCALES
})


@dataclass
class ModCatalog:
    advancements: dict[str, set[str]]
    deaths: list[tuple[str, str | None]]
    warnings: list[str]
    cache_hits: int
    cache_misses: int
    achievements: dict[str, set[str]] = field(default_factory=dict)


def _warning(source: str, detail: str, resource: str | None = None) -> str:
    suffix = f" ({resource})" if resource else ""
    return f"{source}: {detail}{suffix}"


def _is_link(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or (is_junction is not None and is_junction())


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _valid_cache(data: object) -> bool:
    if not isinstance(data, dict) or data.get("schema") != _SCHEMA:
        return False
    title_keys = data.get("title_keys")
    resources = data.get("resources")
    if not isinstance(resources, list) or not all(
        isinstance(resource, dict)
        and isinstance(resource.get("namespace"), str)
        and resource["namespace"] not in {".", ".."}
        and bool(_NAMESPACE.fullmatch(resource["namespace"]))
        and isinstance(resource.get("languages"), dict)
        and set(resource["languages"]) == set(_LANGUAGE_LOCALES)
        and all(
            isinstance(translations, dict) and all(
                isinstance(key, str) and isinstance(values, list)
                and all(isinstance(value, str) for value in values)
                for key, values in translations.items()
            )
            for translations in resource["languages"].values()
        )
        for resource in resources
    ):
        return False
    if not isinstance(title_keys, list) or not all(
        isinstance(key, str) and 0 < len(key) <= 2048 for key in title_keys
    ):
        return False
    return True


def _read_cache(path: Path) -> dict | None:
    if _is_link(path):
        raise ValueError(f"Translation cache file must not be a symlink: {path}")
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f"Translation cache path is not a file: {path}")
    try:
        if path.stat().st_size > _MAX_CACHE_BYTES:
            return None
        with path.open("rb") as source:
            raw = source.read(_MAX_CACHE_BYTES + 1)
        if len(raw) > _MAX_CACHE_BYTES:
            return None
        data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        return None
    return data if _valid_cache(data) else None


def _write_cache(path: Path, cache_dir: Path, data: dict) -> None:
    if _is_link(path):
        raise ValueError(f"Translation cache file must not be a symlink: {path}")
    serialized = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if len(serialized.encode("utf-8")) > _MAX_CACHE_BYTES:
        raise ValueError(f"Translation cache exceeds size limit: {path.name}")
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=cache_dir,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as output:
            temp_name = output.name
            output.write(serialized)
            output.flush()
            os.fsync(output.fileno())
        if _is_link(path):
            raise ValueError(f"Translation cache file must not be a symlink: {path}")
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def _language_resource(name: str) -> tuple[str, str, str] | None:
    # Backslashes, absolute paths, drive names, and traversal are never valid
    # resource paths. ZIP entries are read directly and never extracted.
    if "\\" in name or name.startswith("/") or ":" in name:
        return None
    parts = name.split("/")
    if len(parts) != 4 or parts[0].casefold() != "assets":
        return None
    namespace, folder, filename = parts[1], parts[2], parts[3]
    if namespace in {".", ".."} or not _NAMESPACE.fullmatch(namespace) or folder.casefold() != "lang":
        return None
    base, dot, extension = filename.rpartition(".")
    if not dot or extension.casefold() not in {"json", "lang"}:
        return None
    locale = _LOCALE_BY_FILE.get(base.casefold())
    return (namespace, locale, extension.casefold()) if locale else None


def _advancement_resource(name: str) -> bool:
    if "\\" in name or name.startswith("/") or ":" in name:
        return False
    parts = name.split("/")
    return (
        len(parts) >= 4
        and parts[0].casefold() == "data"
        and parts[1] not in {".", ".."}
        and bool(_NAMESPACE.fullmatch(parts[1]))
        and parts[2].casefold() in {"advancement", "advancements"}
        and all(part not in {"", ".", ".."} for part in parts)
        and parts[-1].casefold().endswith(".json")
    )


def _parse_language(raw: bytes, extension: str) -> dict[str, str]:
    source = raw.decode("utf-8-sig")
    if extension == "json":
        parsed = json.loads(source)
        if not isinstance(parsed, dict):
            raise ValueError("language JSON must be an object")
        return {key: value for key, value in parsed.items() if isinstance(key, str) and isinstance(value, str)}
    result = {}
    for line in source.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            result[key] = value.strip()
    return result


def _collect_translate_keys(component: object, found: set[str]) -> None:
    if isinstance(component, dict):
        key = component.get("translate")
        if isinstance(key, str) and key:
            found.add(key)
        for value in component.values():
            if isinstance(value, (dict, list)):
                _collect_translate_keys(value, found)
    elif isinstance(component, list):
        for value in component:
            _collect_translate_keys(value, found)


def _looks_like_title_key(key: str) -> bool:
    parts = key.casefold().split(".")
    if any(
        part in {"description", "descriptions", "desc", "get", "hint", "hints", "criteria", "toast"}
        or part.startswith(("description_", "desc_"))
        for part in parts
    ):
        return False
    if "achievement" in parts or "advancement" in parts:
        return True
    return "advancements" in parts and parts[-1] == "title"


def _extract_archive(path: Path, warnings: list[str]) -> dict | None:
    source = path.name
    resources: dict[str, dict[str, dict[str, list[str]]]] = {}
    title_keys: set[str] = set()
    bytes_read = 0
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > _MAX_ARCHIVE_MEMBERS:
                warnings.append(_warning(source, "archive member count exceeds limit"))
                return None
            selected = []
            total_bytes = 0
            seen_language_paths = set()
            for member in members:
                resource = _language_resource(member.filename)
                is_advancement = _advancement_resource(member.filename)
                if resource is None and not is_advancement:
                    continue
                if member.is_dir():
                    continue
                if member.file_size > _MAX_ENTRY_BYTES:
                    warnings.append(_warning(source, "resource exceeds size limit", member.filename))
                    continue
                total_bytes += member.file_size
                if total_bytes > _MAX_JAR_SELECTED_BYTES:
                    warnings.append(_warning(source, "selected resources exceed total size limit"))
                    return None
                if resource is not None:
                    marker = member.filename.casefold()
                    if marker in seen_language_paths:
                        warnings.append(_warning(source, "duplicate language resource skipped", member.filename))
                        continue
                    seen_language_paths.add(marker)
                selected.append((member, resource, is_advancement))
            for member, resource, is_advancement in selected:
                remaining = _MAX_JAR_SELECTED_BYTES - bytes_read
                read_limit = min(_MAX_ENTRY_BYTES + 1, remaining + 1)
                try:
                    with archive.open(member) as entry:
                        raw = entry.read(read_limit)
                except (OSError, RuntimeError, zipfile.BadZipFile, EOFError, zlib.error):
                    warnings.append(_warning(source, "resource could not be read", member.filename))
                    continue
                if len(raw) > _MAX_ENTRY_BYTES:
                    warnings.append(_warning(source, "resource exceeds size limit", member.filename))
                    continue
                if len(raw) > remaining:
                    warnings.append(_warning(source, "selected resources exceed total size limit"))
                    return None
                bytes_read += len(raw)
                if resource is not None:
                    namespace, locale, extension = resource
                    try:
                        parsed = _parse_language(raw, extension)
                        languages = resources.setdefault(namespace, {
                            language_locale: {} for language_locale in _LANGUAGE_LOCALES
                        })
                        for key, value in parsed.items():
                            candidates = languages[locale].setdefault(key, [])
                            if value not in candidates:
                                candidates.append(value)
                    except (UnicodeError, ValueError, json.JSONDecodeError, RecursionError):
                        warnings.append(_warning(source, "malformed language resource skipped", member.filename))
                elif is_advancement:
                    try:
                        definition = json.loads(raw.decode("utf-8-sig"))
                        display = definition.get("display") if isinstance(definition, dict) else None
                        if isinstance(display, dict) and "title" in display:
                            resource_title_keys = set()
                            _collect_translate_keys(display["title"], resource_title_keys)
                            title_keys.update(resource_title_keys)
                    except (UnicodeError, ValueError, json.JSONDecodeError, RecursionError):
                        warnings.append(_warning(source, "malformed advancement resource skipped", member.filename))
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, EOFError, zlib.error):
        warnings.append(_warning(source, "invalid or unreadable JAR"))
        return None
    all_keys = set().union(*(
        set(items)
        for namespace_languages in resources.values()
        for items in namespace_languages.values()
    )) if resources else set()
    title_keys.update(key for key in all_keys if _looks_like_title_key(key))
    return {
        "schema": _SCHEMA,
        "resources": [
            {"namespace": namespace, "languages": languages}
            for namespace, languages in sorted(resources.items())
        ],
        "title_keys": sorted(title_keys),
    }


def _cache_dir(path: Path) -> Path:
    if _is_link(path):
        raise ValueError(f"Translation cache directory must not be a symlink: {path}")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ValueError(f"Cannot create translation cache directory: {path}") from error
    if _is_link(path) or not path.is_dir():
        raise ValueError(f"Translation cache path is not a safe directory: {path}")
    return path


def _combine(
    records: list[dict], locale: str,
) -> tuple[dict[str, set[str]], list[tuple[str, str | None]], dict[str, set[str]]]:
    groups = [resource for record in records for resource in record["resources"]]
    title_keys: set[str] = set()
    for record in records:
        title_keys.update(record["title_keys"])
    english_locale = SUPPORTED_LOCALES["en"]
    selected_locale = SUPPORTED_LOCALES[locale]
    english_by_key: dict[str, set[str]] = {}
    for group in groups:
        for key, values in group["languages"][english_locale].items():
            english_by_key.setdefault(key, set()).update(values)
    translation_only_by_key: dict[str, set[str]] = {}
    for group in groups:
        english_keys = group["languages"][english_locale]
        for key, values in group["languages"][selected_locale].items():
            if key not in english_keys:
                translation_only_by_key.setdefault(key, set()).update(values)

    advancements: dict[str, set[str]] = {}
    achievements: dict[str, set[str]] = {}
    for key in title_keys:
        for group in groups:
            titles = group["languages"][english_locale].get(key, ())
            if not titles:
                continue
            translations = set(group["languages"][selected_locale].get(key, ()))
            if len(english_by_key.get(key, ())) == 1:
                translations.update(translation_only_by_key.get(key, ()))
            for title in titles:
                candidates = translations or {title}
                advancements.setdefault(title, set()).update(candidates)
                if "achievement" in key.casefold().split("."):
                    achievements.setdefault(title, set()).update(candidates)

    death_pairs: set[tuple[str, str | None]] = set()
    for group in groups:
        for key, templates in group["languages"][english_locale].items():
            if not key.startswith(("death.attack.", "death.fell.")):
                continue
            translations = set(group["languages"][selected_locale].get(key, ()))
            if len(english_by_key.get(key, ())) == 1:
                translations.update(translation_only_by_key.get(key, ()))
            for template in templates:
                if translations:
                    death_pairs.update((template, translated) for translated in translations)
                else:
                    death_pairs.add((template, None))
    return (
        advancements,
        sorted(death_pairs, key=lambda pair: (pair[0], pair[1] or "")),
        achievements,
    )


def load_mod_catalog(mods_dir: Path, cache_dir: Path, locale: str) -> ModCatalog:
    """Load selected locale strings and title metadata from direct child JARs."""
    selected_locale = normalize_locale(locale)
    mods_dir = Path(mods_dir)
    if not mods_dir.is_dir():
        raise ValueError(f"MODS_DIR must point to an existing directory: {mods_dir}")
    cache_dir = _cache_dir(Path(cache_dir))
    warnings: list[str] = []
    records = []
    cache_hits = cache_misses = 0
    try:
        entries = sorted(mods_dir.iterdir(), key=lambda path: path.name.casefold())
    except OSError as error:
        raise ValueError(f"MODS_DIR cannot be read: {mods_dir}") from error
    for jar in entries:
        if jar.suffix.casefold() != ".jar":
            continue
        if jar.is_symlink():
            warnings.append(_warning(jar.name, "symbolic-link JAR skipped"))
            continue
        try:
            if not jar.is_file():
                continue
            digest = _digest(jar)
        except OSError:
            warnings.append(_warning(jar.name, "JAR could not be read"))
            continue
        cache_path = cache_dir / f"{digest}.json"
        cached = _read_cache(cache_path)
        if cached is not None:
            records.append(cached)
            cache_hits += 1
            continue
        if cache_path.exists():
            warnings.append(_warning(jar.name, "invalid translation cache; rebuilding"))
        cache_misses += 1
        extracted = _extract_archive(jar, warnings)
        if extracted is None:
            continue
        try:
            confirmed_digest = _digest(jar)
        except OSError:
            warnings.append(_warning(jar.name, "JAR changed or became unreadable during extraction; skipped"))
            continue
        if confirmed_digest != digest:
            warnings.append(_warning(jar.name, "JAR changed during extraction; skipped"))
            continue
        try:
            _write_cache(cache_path, cache_dir, extracted)
        except (OSError, ValueError) as error:
            if isinstance(error, ValueError):
                raise
            warnings.append(_warning(jar.name, "translation cache could not be written"))
        records.append(extracted)
    advancements, deaths, achievements = _combine(records, selected_locale)
    return ModCatalog(advancements, deaths, warnings, cache_hits, cache_misses, achievements)
