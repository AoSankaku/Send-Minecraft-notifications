from pathlib import Path
import sys


def resource_path(relative_path: str) -> Path:
    """Read immutable resources from the source tree or the onefile bundle."""
    if getattr(sys, "frozen", False):
        root = Path(sys._MEIPASS)
    else:
        root = Path(__file__).resolve().parents[2]
    return root / relative_path


def default_config_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / ".env"
    return Path.cwd() / ".env"


def translation_path(config_path: Path) -> Path:
    custom = config_path.parent / "translations" / "ja_jp.json"
    return custom if custom.is_file() else resource_path("translations/ja_jp.json")


def create_config(config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves existing secrets and custom settings.
    with config_path.open("x", encoding="utf-8") as output:
        output.write(resource_path(".env.example").read_text(encoding="utf-8"))
