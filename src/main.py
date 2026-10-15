import argparse
import asyncio
import os
from pathlib import Path
import sys
import traceback

from handlers.secrets import BotEnv
from message.i18n import I18n
from server.server import Server
from utils.runtime import create_config, default_config_path, find_legacy_config, translation_path


async def main(config_path: Path | None = None) -> int:
    server = Server()
    try:
        server.init(config_path)
        await server.listen_file_change()
        return 0
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 0
    except Exception:
        await server.crash()
        # Keep diagnostics local: tracebacks may contain webhook credentials.
        traceback.print_exc()
        return 1
    finally:
        await server.shutdown()


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forward Minecraft server logs to Discord via a webhook.")
    parser.add_argument(
        "--config", type=Path,
        help="Path to .env or an existing configuration directory; standalone builds also detect nearby legacy Python installations",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--init-config", action="store_true", help="Create an example .env without overwriting existing settings")
    mode.add_argument("--check-config", action="store_true", help="Validate settings and translations without sending notifications")
    args = parser.parse_args(argv)
    try:
        config_path = (args.config or default_config_path()).resolve()
        if args.config is not None and config_path.is_dir():
            config_path = config_path / ".env"
        if (
            args.config is None
            and not args.init_config
            and getattr(sys, "frozen", False)
            and not config_path.exists()
        ):
            legacy_config = find_legacy_config()
            if legacy_config is not None:
                config_path = legacy_config
                print(f"旧Python版の設定を使用します / Legacy configuration: {config_path}")
        if args.init_config or (
            args.config is None
            and getattr(sys, "frozen", False)
            and not args.check_config
            and not config_path.exists()
            and "WEBHOOK_URL" not in os.environ
        ):
            create_config(config_path)
            print(f"Created configuration: {config_path}")
            print("WEBHOOK_URL と TARGET_DIR を設定してから、もう一度実行してください。")
            print("Set WEBHOOK_URL and TARGET_DIR, then run this program again.")
            if not args.init_config:
                _pause_console()
            return 0
        if args.config is not None and not config_path.is_file():
            raise ValueError(f"Configuration file not found: {config_path}")
        BotEnv.init(config_path)
        translator = I18n()
        if not translator.load_translation("ja_jp", str(translation_path(config_path))):
            raise ValueError("Japanese translation file is missing.")
        if args.check_config:
            print("Configuration and translations are valid. No notifications were sent.")
            return 0
        return asyncio.run(main(config_path))
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        if not args.init_config and not args.check_config:
            _pause_console()
        return 1
    except KeyboardInterrupt:
        return 130


def _pause_console() -> None:
    if getattr(sys, "frozen", False) and sys.platform == "win32" and sys.stdin.isatty():
        try:
            input("Enter キーを押すと終了します / Press Enter to exit: ")
        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    # Redirected Windows output may default to a codec that cannot encode Japanese.
    for output_stream in (sys.stdout, sys.stderr):
        if hasattr(output_stream, "reconfigure"):
            output_stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(cli())
