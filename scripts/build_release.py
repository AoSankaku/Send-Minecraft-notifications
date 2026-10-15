from __future__ import annotations

import hashlib
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = "send-minecraft-notifications"
CONFIG_FILENAME = f"{PRODUCT}.toml"
CONFIG_TEMPLATE = f"{PRODUCT}.example.toml"
MAX_WINDOWS_FILENAME_LENGTH = 28
LOCAL_WINDOWS_EXPORT_DIR = Path(r"C:\Users\abcde\dev\normal-apps\[output-executables]")


def run_git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "command returned a nonzero status"
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def resolve_source_identity(repo_root: Path, build_branch: str | None = None) -> tuple[str, str]:
    if build_branch is None:
        branch = run_git(repo_root, "branch", "--show-current")
        if not branch:
            raise RuntimeError(
                "Git branch is unknown (detached HEAD); set SMN_BUILD_BRANCH to a verified branch."
            )
    else:
        if not build_branch or build_branch.strip() != build_branch:
            raise RuntimeError("SMN_BUILD_BRANCH must name a non-empty Git branch.")
        run_git(repo_root, "check-ref-format", f"refs/heads/{build_branch}")
        remote_ref = f"refs/remotes/origin/{build_branch}"
        run_git(repo_root, "show-ref", "--verify", "--quiet", remote_ref)
        run_git(repo_root, "merge-base", "--is-ancestor", "HEAD", remote_ref)
        branch = build_branch

    commit = run_git(repo_root, "rev-parse", "--short=7", "HEAD").lower()
    if not re.fullmatch(r"[0-9a-f]{7,}", commit):
        raise RuntimeError(f"Git returned an invalid short HEAD hash: {commit!r}")
    return branch, commit


def sanitize_filename_component(value: str) -> str:
    safe = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "-", value)
    safe = safe.strip(" .")
    if not safe:
        raise ValueError("Filename component is empty after Windows filename sanitization.")
    return safe


def build_windows_filename(
    app_name: str,
    branch: str,
    commit: str,
    max_length: int = MAX_WINDOWS_FILENAME_LENGTH,
) -> str:
    app = sanitize_filename_component(app_name)
    safe_branch = sanitize_filename_component(branch)
    if not re.fullmatch(r"[0-9a-fA-F]{7,}", commit):
        raise ValueError(f"Expected a short hexadecimal Git hash, got {commit!r}.")
    commit = commit.lower()

    suffix = f"-{commit}.exe"
    component_budget = max_length - len(suffix) - 1
    if component_budget < 2:
        raise ValueError(
            f"Maximum filename length {max_length} cannot fit both app and branch with {suffix}."
        )

    if len(app) + len(safe_branch) > component_budget:
        app_budget = min(len(app), max(1, component_budget // 2))
        branch_budget = min(len(safe_branch), component_budget - app_budget)
        app_budget = min(len(app), component_budget - branch_budget)
        app = app[:app_budget]
        safe_branch = safe_branch[:branch_budget]

    filename = f"{app}-{safe_branch}{suffix}"
    if len(filename) > max_length:
        raise ValueError("Unable to shorten Windows executable name within the required limit.")
    return filename


def project_name(pyproject_path: Path) -> str:
    project = tomllib.loads(pyproject_path.read_text(encoding="utf-8")).get("project", {})
    name = project.get("name")
    if not isinstance(name, str) or not name:
        raise RuntimeError(f"Project name is missing from {pyproject_path}.")
    return name


def copy_local_windows_executable(
    binary: Path, filename: str, destination: Path = LOCAL_WINDOWS_EXPORT_DIR
) -> Path:
    if not binary.is_file():
        raise FileNotFoundError(f"Completed Windows executable not found: {binary}")
    destination.mkdir(parents=True, exist_ok=True)
    exported = destination / filename
    shutil.copy2(binary, exported)
    return exported


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


def cleanup_previous_windows_executables(
    release_dir: Path, checksum_path: Path, current_executable_name: str
) -> list[Path]:
    """Remove only verified Windows executables listed in the previous checksums."""
    if checksum_path.is_symlink():
        raise RuntimeError(f"Refusing to read a symlink checksum file: {checksum_path}")
    if not checksum_path.exists():
        return []
    if not checksum_path.is_file():
        raise RuntimeError(f"Refusing to read a non-regular checksum file: {checksum_path}")

    removed: list[Path] = []
    checksum_line = re.compile(r"^([0-9a-fA-F]{64})  (.+)$")
    legacy_name = f"{PRODUCT}-windows-x64.exe"
    dynamic_name = re.compile(r"smn-.+-[0-9a-fA-F]{7,}\.exe")

    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        match = checksum_line.fullmatch(line)
        if match is None:
            continue
        expected_digest, name = match.groups()
        if name == current_executable_name:
            continue
        if name != legacy_name and not (
            len(name) <= MAX_WINDOWS_FILENAME_LENGTH and dynamic_name.fullmatch(name)
        ):
            continue
        # The allowlist above excludes separators; keep an explicit basename check
        # so future naming changes cannot turn a checksum entry into a path.
        if Path(name).name != name or "/" in name or "\\" in name or name in {".", ".."}:
            continue

        previous_executable = release_dir / name
        try:
            file_stat = previous_executable.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(file_stat.st_mode):
            continue
        if sha256(previous_executable).lower() != expected_digest.lower():
            raise RuntimeError(
                f"Refusing to remove previous Windows executable because its checksum "
                f"does not match: {previous_executable}"
            )
        previous_executable.unlink()
        removed.append(previous_executable)

    return removed


def validate_archive(path: Path, expected_members: set[str]) -> None:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if any(
            name == CONFIG_FILENAME
            or name == ".env"
            or name.startswith(".env")
            or (name.startswith(f".{CONFIG_FILENAME}.") and name.endswith(".tmp"))
            for name in names
        ):
            raise RuntimeError("A local environment file must never be included in a release.")
        if names != expected_members:
            raise RuntimeError(f"Unexpected files in release archive: {sorted(names)}")


def main() -> None:
    target_os, target_arch, suffix = resolve_target()
    platform_arch = f"{target_os}-{target_arch}"
    if target_os == "windows":
        build_branch = os.environ.get("SMN_BUILD_BRANCH")
        branch, commit = resolve_source_identity(ROOT, build_branch)
        binary_name = build_windows_filename(
            project_name(ROOT / "pyproject.toml"), branch, commit
        )
    else:
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
    archive_sources = [binary, ROOT / "README.md", ROOT / "LICENSE", ROOT / CONFIG_TEMPLATE]
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
    if target_os == "windows":
        removed = cleanup_previous_windows_executables(
            release_dir, checksum_path, binary.name
        )
        for path in removed:
            print(f"  Removed previous Windows executable: {path.name}")
    checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    if target_os == "windows" and os.environ.get("GITHUB_ACTIONS", "").lower() != "true":
        exported = copy_local_windows_executable(binary, binary.name)
        print(f"  Local export: {exported}")

    print(f"Release assets for {platform_arch} written to {release_dir}")
    for path in [*checksum_assets, checksum_path]:
        print(f"  {path.name}")


if __name__ == "__main__":
    main()
