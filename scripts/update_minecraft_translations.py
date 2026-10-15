"""Rebuild the bundled title catalog from checksum-verified Mojang resources.

This is a maintainer command, never called by the notification application.
It reads JSON/.lang data from JARs as ZIPs; it does not execute or decompile Java.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from message.locales import SUPPORTED_LOCALES

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
DEFAULT_VERSIONS = ("1.11.2", "1.12.2", "1.16.5", "1.20.1", "1.21.11", "26.3")
OFFICIAL_HOSTS = {
    "piston-meta.mojang.com", "piston-data.mojang.com",
    "launchermeta.mojang.com", "launcher.mojang.com", "resources.download.minecraft.net",
}


def _validate_url(url: str):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc not in OFFICIAL_HOSTS:
        raise ValueError("Downloads require an official HTTPS Minecraft resource URL")


def download(url: str, sha1: str | None, cache: Path) -> bytes:
    _validate_url(url)
    if sha1 is not None and not re.fullmatch(r"[a-f0-9]{40}", sha1):
        raise ValueError("Invalid resource checksum")
    cached = cache / sha1 if sha1 else None
    if cached is not None and cached.is_file():
        data = cached.read_bytes()
    else:
        with urlopen(url, timeout=60) as response:
            _validate_url(response.url)
            data = response.read(100 * 1024 * 1024 + 1)
        if len(data) > 100 * 1024 * 1024:
            raise ValueError("Minecraft resource exceeds size limit")
    if sha1 is not None and hashlib.sha1(data).hexdigest() != sha1:
        raise ValueError(f"Minecraft resource checksum mismatch: {url}")
    if cached is not None and not cached.exists():
        cache.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(dir=cache)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(data)
            os.replace(name, cached)
        finally:
            Path(name).unlink(missing_ok=True)
    return data


def read_language(data: bytes, suffix: str) -> dict[str, str]:
    text = data.decode("utf-8-sig")
    if suffix == ".json":
        result = json.loads(text)
    elif suffix == ".lang":
        result = dict(line.split("=", 1) for line in text.splitlines() if "=" in line and not line.startswith("#"))
    else:
        raise ValueError("Unsupported Minecraft language format")
    if not isinstance(result, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in result.items()):
        raise ValueError("Invalid Minecraft language mapping")
    return result


def title_entries(language: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in sorted(language.items()) if value and (
        (key.startswith("advancements.") and key.endswith(".title"))
        or (key.startswith("achievement.") and not key.endswith(".desc") and key not in {
            "achievement.get", "achievement.taken", "achievement.requires", "achievement.unknown",
        })
    )}


def _version_catalog(entry: dict, cache: Path) -> tuple[dict, list[dict]]:
    version = json.loads(download(entry["url"], entry["sha1"], cache))
    index_meta = version["assetIndex"]
    index = json.loads(download(index_meta["url"], index_meta["sha1"], cache))["objects"]
    client = version["downloads"]["client"]
    with zipfile.ZipFile(io.BytesIO(download(client["url"], client["sha1"], cache))) as archive:
        english_name = next(name for name in archive.namelist() if name.lower() in {
            "assets/minecraft/lang/en_us.json", "assets/minecraft/lang/en_us.lang",
        })
        english = title_entries(read_language(archive.read(english_name), Path(english_name).suffix))
    if not english:
        raise ValueError(f"No progress titles in {entry['id']}")
    sources = [{"version": entry["id"], "kind": kind, "url": item["url"], "sha1": item["sha1"]}
               for kind, item in (("metadata", entry), ("asset_index", index_meta), ("client", client))]

    def language(code_and_resource):
        code, resource = code_and_resource
        if code == "en":
            return code, english, None
        name = next((f"minecraft/lang/{resource}{suffix}" for suffix in (".json", ".lang")
                     if f"minecraft/lang/{resource}{suffix}" in index), None)
        if name is None:
            return code, {}, None  # Some locales did not exist in older releases.
        checksum = index[name]["hash"]
        url = f"https://resources.download.minecraft.net/{checksum[:2]}/{checksum}"
        mapping = title_entries(read_language(download(url, checksum, cache), Path(name).suffix))
        titles = {key: value for key, value in mapping.items() if key in english}
        return code, titles, {"version": entry["id"], "locale": code, "url": url, "sha1": checksum}

    with ThreadPoolExecutor(max_workers=8) as executor:
        languages = list(executor.map(language, SUPPORTED_LOCALES.items()))
    sources.extend(source for _, _, source in languages if source is not None)
    return {code: mapping for code, mapping, _ in languages}, sources


def build_catalog(versions: list[str], cache: Path) -> dict:
    manifest = json.loads(download(MANIFEST_URL, None, cache))
    entries = {entry["id"]: entry for entry in manifest["versions"]}
    result = {"schema": 1, "versions": {}, "sources": []}
    for version in versions:
        if version not in entries:
            raise ValueError(f"Unknown Minecraft version: {version}")
        mapping, sources = _version_catalog(entries[version], cache)
        result["versions"][version] = mapping
        result["sources"].extend(sources)
        print(f"{version}: {len(mapping['en'])} titles, {sum(bool(names) for names in mapping.values())} locales", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--versions", nargs="+", default=DEFAULT_VERSIONS)
    parser.add_argument("--cache", type=Path, default=ROOT / ".uv-cache" / "minecraft")
    parser.add_argument("--output", type=Path, default=ROOT / "translations" / "minecraft.json")
    args = parser.parse_args()
    catalog = build_catalog(args.versions, args.cache)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
