from pathlib import Path
import sys

from utils.config import CONFIG_FILENAME, TEMPLATE_FILENAME, write_private_config
from message.locales import SUPPORTED_LOCALES, normalize_locale


def resource_path(relative_path: str) -> Path:
    """Read immutable resources from the source tree or the onefile bundle."""
    if getattr(sys, "frozen", False):
        root = Path(sys._MEIPASS)
    else:
        root = Path(__file__).resolve().parents[2]
    return root / relative_path


def default_config_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / CONFIG_FILENAME
    return Path.cwd() / CONFIG_FILENAME


def config_in_directory(directory: Path) -> Path:
    """Prefer this application's TOML, falling back to an existing old .env."""
    canonical = directory / CONFIG_FILENAME
    if canonical.exists() or canonical.is_symlink():
        return canonical
    legacy = directory / ".env"
    return legacy if legacy.is_file() or legacy.is_symlink() else canonical


def find_legacy_config() -> Path | None:
    """Find a known Python checkout without scanning unrelated directories."""
    def config_in(directory: Path) -> Path | None:
        config = config_in_directory(directory)
        if config.is_file() and (config.name == CONFIG_FILENAME or all(
            (directory / marker).is_file()
            for marker in ("src/main.py", "src/handlers/secrets.py")
        )):
            return config
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


def translation_path(config_path: Path, locale: str = "ja") -> Path:
    mc_locale = SUPPORTED_LOCALES[normalize_locale(locale)]
    custom = Path(config_path).parent / "translations" / f"{mc_locale}.json"
    return custom if custom.is_file() else resource_path(f"translations/{mc_locale}.json")


def create_config(config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    write_private_config(config_path, resource_path(TEMPLATE_FILENAME).read_text(encoding="utf-8"))
