"""Check a standalone build's first-run setup without Python on its PATH or network calls."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main() -> None:
    binary = Path(sys.argv[1]).resolve()
    environment = dict(os.environ)
    # Use the Windows system directory (or an empty PATH on Linux), never Python.
    environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32") if os.name == "nt" else ""
    for key in list(environment):
        if key.startswith(("PYTHON", "WEBHOOK", "SERVER_", "SENDER_", "TARGET_", "TIPS_", "JAPANIZE_")) or key in (
            "EMBED_MODE", "KILL_AFTER_CLOSED", "PLAYER_ICON_API", "IGNORE_NAMES", "PLUGIN_DIR",
            "RESTART_ANNOUNCEMENT_MESSAGE",
        ):
            del environment[key]

    with tempfile.TemporaryDirectory(prefix="smn-release-") as temporary:
        root = Path(temporary)
        installed = root / "installed"
        installed.mkdir()
        executable = installed / binary.name
        shutil.copy2(binary, executable)

        def run(*args: str, expected: int = 0) -> str:
            result = subprocess.run(
                [str(executable), *args], cwd=root, env=environment,
                capture_output=True, timeout=30,
            )
            if result.returncode != expected:
                raise RuntimeError(
                    f"Standalone command {args} exited {result.returncode}: "
                    + result.stderr.decode(errors="replace")
                )
            return result.stdout.decode(errors="replace")

        assert "--check-config" in run("--help")
        run()
        config = installed / "send-minecraft-notifications.toml"
        assert config.is_file() and not (installed / ".env").exists()
        text = config.read_text(encoding="utf-8")
        assert 'WEBHOOK_URL = "' in text and 'TARGET_DIR = "' in text
        run("--init-config", expected=1)
        assert config.read_text(encoding="utf-8") == text

        url = "https://discord.com/api/webhooks/123456789012345678/" + "test-token" * 6
        config.write_text(f'WEBHOOK_URL = "{url}"\nTARGET_DIR = "./logs"\n', encoding="utf-8")
        assert "No notifications were sent" in run("--check-config")
        with config.open("a", encoding="utf-8") as output:
            output.write('JAPANIZE_ENABLED = true\nJAPANIZE_MODE = "local"\nJAPANIZE_DICTIONARY = { "maikura" = "マイクラ" }\n')
        assert "No notifications were sent" in run("--check-config")
        external = root / "custom-config"
        external.mkdir()
        run("--config", str(external), "--init-config")
        external_config = external / "send-minecraft-notifications.toml"
        external_config.write_text(f'WEBHOOK_URL = "{url}"\n', encoding="utf-8")
        assert "No notifications were sent" in run("--config", str(external), "--check-config")
        custom_translation = external / "translations" / "ja_jp.json"
        custom_translation.parent.mkdir()
        custom_translation.write_text("[]", encoding="utf-8")
        run("--config", str(external), "--check-config", expected=1)

        # A nearby old Python checkout can supply settings to the standalone
        # binary. Check both discovery and an explicitly selected directory.
        legacy = root / "Send-Minecraft-notifications"
        for relative in ("src/main.py", "src/handlers/secrets.py"):
            marker = legacy / relative
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("# Legacy installation\n", encoding="utf-8")
        legacy_config = legacy / ".env"
        legacy_config.write_text(
            f"WEBHOOK_URL={url}\nTARGET_DIR=./server/logs\nPLUGIN_DIR=./plugins\n",
            encoding="utf-8-sig",
        )
        original = legacy_config.read_bytes()
        config.unlink()
        detected = run("--check-config")
        assert "Legacy configuration:" in detected or "Migrated legacy configuration:" in detected
        if "Legacy configuration:" in detected:
            reported_path = detected.split("Legacy configuration:", 1)[1].splitlines()[0].strip()
            assert Path(reported_path).samefile(legacy_config), f"Unexpected legacy path: {reported_path}"
        assert "No notifications were sent" in detected
        migrated_config = legacy / "send-minecraft-notifications.toml"
        assert migrated_config.is_file()
        assert migrated_config.parent.samefile(legacy_config.parent)
        assert legacy_config.read_bytes() == original
        # An intentionally invalid legacy file must not override the TOML made
        # during migration. This also checks directory selection on later runs.
        legacy_config.write_text("WEBHOOK_URL=not-a-webhook\n", encoding="utf-8")
        assert "No notifications were sent" in run("--config", str(legacy), "--check-config")
        assert url not in detected

    print("Standalone smoke check passed: help, TOML first run, config persistence, bundled data, validation, and legacy .env migration.")


if __name__ == "__main__":
    main()
