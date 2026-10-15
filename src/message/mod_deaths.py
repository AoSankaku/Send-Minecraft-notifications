"""Conservative reverse matching of Minecraft death translation templates."""

from dataclasses import dataclass
import re


_ARGUMENT = re.compile(r"%(?:([1-3])\$)?s")
_PLAYER = re.compile(r"[.A-Za-z0-9_]{1,32}")
MAX_MESSAGE_LENGTH = 4096
MAX_MATCH_STEPS = 128


def _parts(template: str, *, source=False):
    if not isinstance(template, str) or len(template) > MAX_MESSAGE_LENGTH:
        return None
    result = []
    position = 0
    sequential = 0

    def literal(value):
        if value:
            if result and isinstance(result[-1], str):
                result[-1] += value
            else:
                result.append(value)

    while position < len(template):
        marker = template.find("%", position)
        if marker == -1:
            literal(template[position:])
            break
        literal(template[position:marker])
        if template.startswith("%%", marker):
            literal("%")
            position = marker + 2
            continue
        match = _ARGUMENT.match(template, marker)
        if match is None:
            return None
        if match[1] is None:
            sequential += 1
        argument = int(match[1]) if match[1] else sequential
        if argument > 3 or (source and result and isinstance(result[-1], int)):
            return None
        result.append(argument)
        position = match.end()
    arguments = [part for part in result if isinstance(part, int)]
    if not arguments or len(arguments) > 6:
        return None
    if source and (1 not in arguments or sum(len(part) for part in result if isinstance(part, str)) < 3):
        return None
    return result


def _match(parts, text):
    """Bounded literal searches; mod text is never compiled as executable regex."""
    matches = []
    steps = 0

    def walk(index, position, arguments):
        nonlocal steps
        steps += 1
        if steps > MAX_MATCH_STEPS or len(matches) > 1:
            return
        if index == len(parts):
            if position == len(text):
                matches.append(arguments)
            return
        part = parts[index]
        if isinstance(part, str):
            if text.startswith(part, position):
                walk(index + 1, position + len(part), arguments)
            return
        if part in arguments:
            value = arguments[part]
            if text.startswith(value, position):
                walk(index + 1, position + len(value), arguments)
            return
        maximum = min(len(text), position + (32 if part == 1 else 512))
        if index + 1 == len(parts):
            endpoints = [len(text)] if len(text) <= maximum else []
        else:
            following = parts[index + 1]
            endpoints = []
            end = text.find(following, position + 1)
            while end != -1 and end <= maximum and len(endpoints) <= MAX_MATCH_STEPS:
                endpoints.append(end)
                end = text.find(following, end + 1)
        for end in endpoints:
            value = text[position:end]
            if not value or (part == 1 and _PLAYER.fullmatch(value) is None):
                continue
            walk(index + 1, end, arguments | {part: value})
            if steps > MAX_MATCH_STEPS or len(matches) > 1:
                break

    walk(0, 0, {})
    return matches, steps > MAX_MATCH_STEPS


@dataclass(frozen=True)
class DeathTranslation:
    player: str
    text: str


class DeathTranslator:
    def __init__(self, templates=()):
        self.templates = []
        for english, target in templates:
            source_parts = _parts(english, source=True)
            if source_parts is None:
                continue
            target_parts = _parts(target) if target is not None else None
            if target_parts is not None:
                source_arguments = {part for part in source_parts if isinstance(part, int)}
                target_arguments = {part for part in target_parts if isinstance(part, int)}
                if target_arguments != source_arguments:
                    target_parts = None
            self.templates.append((source_parts, target_parts))

    def translate(self, text: str) -> DeathTranslation | None:
        if len(text) > MAX_MESSAGE_LENGTH or "\n" in text or "\r" in text:
            return None
        candidates = set()
        players = set()
        for source_parts, target_parts in self.templates:
            matches, exhausted = _match(source_parts, text)
            if not matches:
                continue
            players.update(arguments[1] for arguments in matches)
            if exhausted or len(matches) != 1 or target_parts is None:
                candidates.add(text)
                continue
            arguments = matches[0]
            candidates.add("".join(arguments[part] if isinstance(part, int) else part for part in target_parts))
        if not candidates or len(players) != 1:
            return None
        return DeathTranslation(next(iter(players)), next(iter(candidates)) if len(candidates) == 1 else text)
