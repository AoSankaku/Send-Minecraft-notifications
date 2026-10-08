import re


def convert_string_to_array(target: str):
    target = target[1:-1].replace('"', "").replace(", ", ",").replace(" ,", ",")
    target = target.split(",")
    return target


def hex_to_int(color_hex: str) -> int:
    if color_hex.startswith("#"):
        color_hex = color_hex[1:]  # #で始まるなら、'#'を取り除く
    return int(color_hex, 16)  # 16進数を整数に変換


def normalize_message_newlines(value: str) -> str:
    """Decode only message newline escapes; keep Unicode and other escapes intact."""
    value = value.replace("\r\n", "\n")
    return re.sub(
        r"\\(\\|r\\n|n)",
        lambda match: "\\" if match[1] == "\\" else "\n",
        value,
    )
