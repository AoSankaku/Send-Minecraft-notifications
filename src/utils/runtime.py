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


def find_legacy_config() -> Path | None:
    """Find a known Python checkout without scanning unrelated directories."""
    def config_in(directory: Path) -> Path | None:
        config = directory / ".env"
        if config.is_file() and all(
            (directory / marker).is_file()
            for marker in ("src/main.py", "src/handlers/secrets.py")
        ):
            return config.resolve()
        return None

    # Running from an old checkout explicitly selects that installation.
    working_config = config_in(Path.cwd())
    if working_config is not None:
        return working_config

    executable_dir = Path(sys.executable).resolve().parent
    candidates = {
        config
        for directory in (
            executable_dir / "Send-Minecraft-notifications",
            executable_dir.parent / "Send-Minecraft-notifications",
        )
        if (config := config_in(directory)) is not None
    }
    if len(candidates) > 1:
        raise ValueError(
            "旧Python版が複数見つかりました。--config <旧フォルダー> で指定してください。\n"
            "Multiple legacy installations found; select one with --config <old-directory>."
        )
    return next(iter(candidates), None)


def translation_path(config_path: Path) -> Path:
    custom = config_path.parent / "translations" / "ja_jp.json"
    return custom if custom.is_file() else resource_path("translations/ja_jp.json")


def create_config(config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves existing secrets and custom settings.
    with config_path.open("x", encoding="utf-8") as output:
        output.write(resource_path(".env.example").read_text(encoding="utf-8"))
