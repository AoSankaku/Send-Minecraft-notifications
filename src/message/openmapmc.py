"""Versioned, server-originated OpenMapMC event log records."""

import json
import math
import re
from uuid import UUID

from message.constant import EventIds
from message.model import MessageData, MessageType


EVENT_PREFIX = "OPENMAPMC_EVENT "
MAX_RECORD_LENGTH = 8192
_PLAYER = re.compile(r"[.A-Za-z0-9_]{1,32}")
_DIMENSION = re.compile(r"[a-z0-9_.-]+:[a-z0-9/._-]+")
_PLACEHOLDER = re.compile(r"%waypoint-(?:name|dimension|x|y|z)%")
DEFAULT_TEMPLATE = ":round_pushpin: Created shared waypoint [%waypoint-name%] in %waypoint-dimension% (%waypoint-x%, %waypoint-y%, %waypoint-z%)."


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate event field")
        result[key] = value
    return result


def _uuid(value):
    return isinstance(value, str) and len(value) == 36 and str(UUID(value)) == value.lower()


def _coordinate(value, minimum, maximum):
    return type(value) in (int, float) and math.isfinite(value) and minimum <= value <= maximum


def _number(value):
    return str(int(value)) if value == int(value) else str(value)


def parse_waypoint_created(body: str, template: str = DEFAULT_TEMPLATE) -> MessageData | None:
    if not body.startswith(EVENT_PREFIX) or len(body) > MAX_RECORD_LENGTH:
        return None
    try:
        data = json.loads(body[len(EVENT_PREFIX):], object_pairs_hook=_unique_object)
        if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
            return None
        if data.get("event") != "shared_waypoint_created":
            return None
        if not _uuid(data.get("waypoint_id")) or not _uuid(data.get("creator_uuid")):
            return None
        creator, name, dimension = data.get("creator_name"), data.get("name"), data.get("dimension")
        if not isinstance(creator, str) or _PLAYER.fullmatch(creator) is None:
            return None
        if not isinstance(name, str) or not name.strip() or len(name) > 256 or len(name.encode("utf-8")) > 1024:
            return None
        if any(ord(char) < 32 or ord(char) == 127 for char in name):
            return None
        if not isinstance(dimension, str) or len(dimension) > 128 or _DIMENSION.fullmatch(dimension) is None:
            return None
        if not all(_coordinate(data.get(key), *bounds) for key, bounds in (
            ("x", (-30_000_000, 30_000_000)), ("y", (-2048, 4096)), ("z", (-30_000_000, 30_000_000)),
        )):
            return None
    except (ValueError, UnicodeError, OverflowError, RecursionError):
        return None
    fields = {
        "%waypoint-name%": name, "%waypoint-dimension%": dimension,
        **{f"%waypoint-{key}%": _number(data[key]) for key in ("x", "y", "z")},
    }
    # A single pass keeps placeholder-like text in user labels literal.
    text = _PLACEHOLDER.sub(lambda match: fields[match[0]], template)
    if not text.strip():
        return None
    return MessageData(
        MessageType.Player, "#50C8FF", text, creator,
        event_id=EventIds.ON_SHARED_WAYPOINT_CREATED, literal_text=True,
    )
