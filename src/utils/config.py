"""TOML configuration loading and safe migration from legacy dotenv files."""

from __future__ import annotations

import io
import json
import os
import tempfile
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import toml
from dotenv.parser import parse_stream
from dotenv.variables import Literal, Variable, parse_variables

from utils.miscutil import normalize_message_newlines


CONFIG_FILENAME = "send-minecraft-notifications.toml"
TEMPLATE_FILENAME = "send-minecraft-notifications.example.toml"

_BOOL_KEYS = {
    "KILL_AFTER_CLOSED", "EMBED_MODE", "JAPANIZE_ENABLED",
    "ADVANCEMENT_TRANSLATION_ENABLED",
    "OPENMAPMC_WAYPOINT_NOTIFICATIONS",
}
_ARRAY_KEYS = {"IGNORE_NAMES", "TIPS_MESSAGES", "JAPANIZE_PUBLIC_CHANNELS"}
_DICT_KEYS = {"JAPANIZE_DICTIONARY", "ADVANCEMENT_DICTIONARY"}
_MESSAGE_KEYS = {
    "SERVER_START_MESSAGE",
    "SERVER_STOP_MESSAGE",
    "SERVER_RESTART_MESSAGE",
    "TIPS_PREFIX",
    "JAPANIZE_SERVER_FORMAT",
}


def _fail(path: Path, setting: str | None = None) -> ValueError:
    if setting is not None:
        return ValueError(f"Invalid setting {setting} in {path}")
    return ValueError(f"Invalid configuration in {path}")


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            values = tomllib.loads(source.read())
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        raise _fail(path) from None
    if not isinstance(values, dict):  # Defensive: a TOML document is a table.
        raise _fail(path) from None
    return values


def _template_values(template_path: Path) -> tuple[dict[str, Any], set[str]]:
    template = _read_toml(template_path)
    known_keys = set(template)
    return _convert_native(template, template_path, known_keys), known_keys


def _parse_json_legacy(value: str, path: Path, setting: str) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        raise _fail(path, setting) from None


def _normalize_legacy_value(key: str, value: Any) -> Any:
    if key in _MESSAGE_KEYS and isinstance(value, str):
        return normalize_message_newlines(value)
    if key == "TIPS_MESSAGES" and isinstance(value, list):
        return [normalize_message_newlines(item) for item in value]
    return value


def _legacy_native_value(key: str, value: str, path: Path) -> Any:
    if key in _BOOL_KEYS:
        lowered = value.strip().casefold()
        if lowered not in {"true", "false"}:
            raise _fail(path, key) from None
        return lowered == "true"

    if key in _ARRAY_KEYS:
        if key == "IGNORE_NAMES":
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError):
                if value.lstrip().startswith("["):
                    raise _fail(path, key) from None
                # Older installations also used a comma-separated list.
                parsed = [part.strip() for part in value.split(",") if part.strip()]
            else:
                if isinstance(parsed, str):
                    parsed = [part.strip() for part in parsed.split(",") if part.strip()]
            if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
                raise _fail(path, key) from None
        else:
            parsed = _parse_json_legacy(value, path, key)
            if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
                raise _fail(path, key) from None
        return _normalize_legacy_value(key, parsed)

    if key in _DICT_KEYS:
        parsed = _parse_json_legacy(value, path, key)
        if not isinstance(parsed, dict) or not all(
            isinstance(item_key, str) and isinstance(item, str)
            for item_key, item in parsed.items()
        ):
            raise _fail(path, key) from None
        return parsed

    return _normalize_legacy_value(key, value)


def _validate_native_value(key: str, value: Any, path: Path) -> Any:
    if key in _BOOL_KEYS:
        if not isinstance(value, bool):
            raise _fail(path, key) from None
    elif key in _ARRAY_KEYS:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise _fail(path, key) from None
    elif key in _DICT_KEYS:
        if not isinstance(value, dict) or not all(
            isinstance(item_key, str) and isinstance(item, str)
            for item_key, item in value.items()
        ):
            raise _fail(path, key) from None
    elif not isinstance(value, str):
        raise _fail(path, key) from None
    return value


def _convert_native(values: Mapping[str, Any], path: Path, known_keys: set[str]) -> dict[str, str | None]:
    converted: dict[str, str | None] = {}
    for key, value in values.items():
        if key not in known_keys:
            continue
        _validate_native_value(key, value, path)
        if isinstance(value, bool):
            converted[key] = "true" if value else "false"
        elif isinstance(value, (list, dict)):
            converted[key] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        else:
            converted[key] = value
    return converted


def _convert_legacy(values: Mapping[str, str | None], path: Path, known_keys: set[str]) -> dict[str, str | None]:
    converted: dict[str, str | None] = {}
    for key, value in values.items():
        if key not in known_keys or value is None:
            continue
        if not isinstance(value, str):
            raise _fail(path, key) from None
        native = _legacy_native_value(key, value, path)
        if isinstance(native, bool):
            converted[key] = "true" if native else "false"
        elif isinstance(native, (list, dict)):
            converted[key] = json.dumps(native, ensure_ascii=False, separators=(",", ":"))
        else:
            converted[key] = native
    return converted


def _read_legacy(path: Path) -> dict[str, str | None]:
    try:
        content = path.read_text(encoding="utf-8-sig")
        # Reject malformed statements before parsing so a migration cannot
        # silently drop a setting. Do not surface parser diagnostics, which can
        # contain source text.
        bindings = list(parse_stream(io.StringIO(content)))
        if any(binding.error for binding in bindings):
            raise _fail(path)
        # Resolve only earlier values from this file. Process environment
        # variables are never consulted; environment overrides are layered
        # explicitly by load_config_values after the file has been parsed.
        file_values: dict[str, str | None] = {}
        resolved_values: dict[str, str | None] = {}
        for binding in bindings:
            if binding.key is None:
                continue
            value = binding.value
            if value is not None:
                value = _interpolate_legacy_value(value, file_values)
            file_values[binding.key] = value
            resolved_values[binding.key] = value
        return resolved_values
    except (OSError, UnicodeError, ValueError):
        raise _fail(path) from None


def _interpolate_legacy_value(value: str, earlier_values: Mapping[str, str | None]) -> str:
    parts: list[str] = []
    for atom in parse_variables(value):
        if isinstance(atom, Literal):
            parts.append(atom.value)
        elif isinstance(atom, Variable):
            resolved = earlier_values.get(atom.name)
            if atom.name in earlier_values and resolved is not None:
                parts.append(resolved)
            elif atom.default is not None:
                parts.append(atom.default)
            else:
                parts.append("${" + atom.name + "}")
    return "".join(parts)


def _load_file_values(path: Path, known_keys: set[str]) -> dict[str, str | None]:
    if path.is_symlink():
        raise _fail(path)
    if not path.is_file():
        if path.exists():
            raise _fail(path)
        return {}
    if path.suffix.casefold() == ".toml":
        return _convert_native(_read_toml(path), path, known_keys)
    return _convert_legacy(_read_legacy(path), path, known_keys)


def _convert_environment(environment: Mapping[str, str], path: Path, known_keys: set[str]) -> dict[str, str | None]:
    selected: dict[str, str | None] = {}
    for key in known_keys:
        if key in environment:
            selected[key] = environment[key]
    return _convert_legacy(selected, path, known_keys)


def load_config_values(
    path: Path,
    template_path: Path,
    environment: Mapping[str, str] | None = None,
) -> dict[str, str | None]:
    """Load defaults, a TOML or dotenv config, and known environment overrides.

    Returned values use the string forms consumed by BotEnv. An absent config
    file is valid and leaves template defaults in effect.
    """
    path = Path(path)
    template_path = Path(template_path)
    defaults, known_keys = _template_values(template_path)
    values = defaults
    values.update(_load_file_values(path, known_keys))

    if environment is None:
        environment = os.environ
    try:
        values.update(_convert_environment(environment, path, known_keys))
    except (TypeError, ValueError):
        # Value errors already identify only the setting and config path.
        raise
    return values


def _legacy_native_values(path: Path, template_path: Path) -> dict[str, Any]:
    # Validate the template with the same schema used by the runtime loader,
    # then retain its native types for TOML serialization.
    _, known_keys = _template_values(template_path)
    native_defaults = _read_toml(template_path)
    values = dict(native_defaults)

    if path.is_symlink():
        raise _fail(path)
    if not path.is_file():
        raise _fail(path)
    legacy = _read_legacy(path)
    for key, value in legacy.items():
        if value is None:
            continue
        if key in known_keys:
            values[key] = _legacy_native_value(key, value, path)
        else:
            # TOML has no null value. Keep unknown dotenv settings where their
            # value is representable, while leaving the original file intact.
            values[key] = value
    # Validate the fully merged document before serialization. Known values
    # from defaults and the legacy source must all have their declared types.
    _convert_native(values, path, known_keys)
    return values


def write_private_config(path: Path, text: str) -> None:
    """Atomically publish a complete UTF-8 config without replacing a file."""
    path = Path(path)
    if os.path.lexists(path):
        raise FileExistsError(path)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        output = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
    except BaseException:
        # fdopen failed before taking ownership of the raw descriptor.
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary_path.unlink(missing_ok=True)
        raise

    try:
        with output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        # Publish only after the full file has been flushed and closed. link()
        # is an atomic no-replace operation on POSIX; Windows rename also fails
        # if the destination already exists.
        if os.name == "nt":
            os.rename(temporary_path, path)
        else:
            os.link(temporary_path, path)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def migrate_legacy_config(source: Path, template_path: Path) -> tuple[Path, bool]:
    """Convert a legacy dotenv file beside itself, without modifying its bytes.

    Returns ``(canonical_path, created)``. Existing canonical paths take
    priority, including symlinks, and are never opened or overwritten here.
    """
    source = Path(source)
    template_path = Path(template_path)
    destination = source.parent / CONFIG_FILENAME

    # lexists catches dangling symlinks; don't read the source if a canonical
    # config already has priority.
    if os.path.lexists(destination):
        return destination, False

    native_values = _legacy_native_values(source, template_path)
    try:
        serialized = toml.dumps(native_values)
        roundtrip = tomllib.loads(serialized)
        _convert_native(roundtrip, destination, set(_read_toml(template_path)))
        if roundtrip != native_values:
            raise _fail(destination)
    except (TypeError, ValueError, toml.TomlDecodeError, tomllib.TOMLDecodeError):
        raise _fail(destination) from None

    try:
        write_private_config(destination, serialized)
    except FileExistsError:
        # Another process or the user created the canonical file concurrently.
        return destination, False
    return destination, True
