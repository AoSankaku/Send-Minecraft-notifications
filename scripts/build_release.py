from __future__ import annotations

import hashlib
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = "send-minecraft-notifications"


def resolve_target() -> tuple[str, str, str]:
    system = platform.system().lower()
    machine = platform.machine().lower()

    operating_systems = {"windows": "windows", "linux": "linux"}
    architectures = {"x86_64": "x64", "amd64": "x64"}
    target_os = operating_systems.get(system)
    target_arch = architectures.get(machine)
    if target_os is None or target_arch is None:
        raise SystemExit(
            f"Unsupported release target: {platform.system()} {platform.machine()}; "
            "only Windows x64 and Linux x64 builds are configured."
        )

    suffix = ".exe" if target_os == "windows" else ""
    return target_os, target_arch, suffix


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_archive(path: Path, expected_members: set[str]) -> None:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if names != expected_members:
            raise RuntimeError(f"Unexpected files in release archive: {sorted(names)}")
        if any(name == ".env" or (name.startswith(".env.") and name != ".env.example") for name in names):
            raise RuntimeError("A local environment file must never be included in a release.")


def main() -> None:
    target_os, target_arch, suffix = resolve_target()
    platform_arch = f"{target_os}-{target_arch}"
    binary_name = f"{PRODUCT}-{platform_arch}{suffix}"
    dist_dir = ROOT / "dist"
    release_dir = dist_dir / "release"
    release_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "send-minecraft-notifications.spec",
        ],
        cwd=ROOT,
        check=True,
    )

    built_binary = dist_dir / f"{PRODUCT}{suffix}"
    if not built_binary.is_file():
        raise FileNotFoundError(f"PyInstaller did not produce {built_binary}")

    binary = release_dir / binary_name
    shutil.copy2(built_binary, binary)
    archive_path = release_dir / f"{PRODUCT}-{platform_arch}.zip"
    archive_sources = [binary, ROOT / "README.md", ROOT / "LICENSE", ROOT / ".env.example"]
    if any(not path.is_file() for path in archive_sources):
        missing = [str(path) for path in archive_sources if not path.is_file()]
        raise FileNotFoundError(f"Required release files are missing: {missing}")

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in archive_sources:
            archive.write(source, arcname=source.name)

    validate_archive(archive_path, {path.name for path in archive_sources})

    checksum_path = release_dir / f"SHA256SUMS-{platform_arch}.txt"
    checksum_assets = [binary, archive_path]
    checksum_lines = [f"{sha256(path)}  {path.name}" for path in checksum_assets]
    checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    print(f"Release assets for {platform_arch} written to {release_dir}")
    for path in [*checksum_assets, checksum_path]:
        print(f"  {path.name}")


if __name__ == "__main__":
    main()
