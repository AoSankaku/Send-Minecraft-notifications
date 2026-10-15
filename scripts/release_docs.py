"""Generate versioned installation instructions for READMEs and GitHub Releases."""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPOSITORY = "AoSankaku/Send-Minecraft-notifications"
PRODUCT = "send-minecraft-notifications"
LEGACY_CONFIG_TAGS = {"v1.0.0-beta0", "v1.0.0-beta1"}
CONFIG_FILENAME = f"{PRODUCT}.toml"


def validate_inputs(tag: str, repository: str, windows_exe: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/+\-]*", tag):
        raise ValueError(f"Unsupported release tag: {tag!r}")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError(f"Invalid GitHub repository: {repository!r}")
    if not re.fullmatch(r"smn-[A-Za-z0-9_.-]+-[0-9a-f]{7,}\.exe", windows_exe) or len(windows_exe) > 28:
        raise ValueError(f"Invalid Windows release filename: {windows_exe!r}")


def installation_section(tag: str, repository: str, windows_exe: str, language: str) -> str:
    validate_inputs(tag, repository, windows_exe)
    release_url = f"https://github.com/{repository}/releases/tag/{quote(tag, safe='')}"
    download_url = f"https://github.com/{repository}/releases/download/{quote(tag, safe='')}"
    linux = f"{PRODUCT}-linux-x64"
    legacy_config = tag in LEGACY_CONFIG_TAGS
    if language == "ja":
        introduction = f"対象リリース: [{tag}]({release_url})。Python のインストールや ZIP の展開は不要です。設定を書き込めるフォルダーで実行してください。"
        linux_title = "Ubuntu Server / Linux x64 でのダウンロードと起動"
        checksum = "任意で、実行前に同じリリースのチェックサムで検証します。未取得の ZIP は検査対象から外れます。"
        config_name = "`.env`" if legacy_config else f"`{CONFIG_FILENAME}`"
        first_run = ("実行権限を付けて初回起動します。同じフォルダーに `.env` の雛形を作成して終了します。"
                     if legacy_config else f"実行権限を付けて初回起動します。旧 `.env` がなければ同じフォルダーに `{CONFIG_FILENAME}` の雛形を作成して終了します。旧設定が見つかれば、元ファイルを残して同じフォルダーに変換します。")
        configure_linux = f"エディターで {config_name} の `WEBHOOK_URL` と `TARGET_DIR`（Minecraft サーバーのログフォルダー）を設定してから、設定を検査して起動します。"
        windows_title = "Windows x64 / PowerShell でのダウンロードと起動"
        configure_windows = f"初回起動で作られた {config_name} をエディターで開き、`WEBHOOK_URL` と `TARGET_DIR` を設定してから、次を実行します。"
        preserved_file = "`.env`" if legacy_config else f"`{CONFIG_FILENAME}`"
        curl_help = f"`-L` は GitHub の転送先を追い、`-o` はファイルに保存し、`-f` は HTTP エラー時に失敗させます。既存の {preserved_file} は上書きされません。設定検査では Discord へ送信しません。"
    elif language == "en":
        introduction = f"Release: [{tag}]({release_url}). No Python installation or ZIP extraction is required. Run these commands in a writable directory."
        linux_title = "Ubuntu Server / Linux x64 download and startup"
        checksum = "Optionally verify the checksum before execution. The ZIP is ignored if it was not downloaded."
        config_name = "`.env`" if legacy_config else f"`{CONFIG_FILENAME}`"
        first_run = ("Make the binary executable, then run it once to create a `.env` template beside it and exit."
                     if legacy_config else f"Make the binary executable, then run it once. Without legacy settings, it creates a `{CONFIG_FILENAME}` template beside it and exits. If old settings are found, it converts them in place and preserves the `.env` file.")
        configure_linux = f"Use an editor to set `WEBHOOK_URL` and `TARGET_DIR` (your Minecraft server's log directory) in {config_name}. Validate the settings, then start the notifier:"
        windows_title = "Windows x64 / PowerShell download and startup"
        configure_windows = f"Open the generated {config_name} in an editor and set `WEBHOOK_URL` and `TARGET_DIR`, then run:"
        preserved_file = "`.env` files" if legacy_config else f"`{CONFIG_FILENAME}` files"
        curl_help = f"`-L` follows GitHub redirects, `-o` saves to a file, and `-f` fails on HTTP errors. Existing {preserved_file} are preserved. Configuration checks do not send Discord notifications."
    else:
        raise ValueError(f"Unsupported language: {language}")

    return f"""{introduction}

### {linux_title}

```sh
curl -fL -o {linux} \\
  {download_url}/{linux}
```

{checksum}

```sh
curl -fL -o SHA256SUMS-linux-x64.txt \\
  {download_url}/SHA256SUMS-linux-x64.txt
sha256sum --check --ignore-missing SHA256SUMS-linux-x64.txt
```

{first_run}

```sh
chmod +x ./{linux}
./{linux}
```

{configure_linux}

```sh
./{linux} --check-config
./{linux}
```

### {windows_title}

```powershell
curl.exe -fL -o {windows_exe} `
  {download_url}/{windows_exe}
.\\{windows_exe}
```

{configure_windows}

```powershell
.\\{windows_exe} --check-config
.\\{windows_exe}
```

{curl_help}

{legacy_configuration_section(windows_exe, language, legacy=legacy_config)}
"""


def legacy_configuration_section(windows_exe: str, language: str, *, legacy: bool) -> str:
    if not legacy:
        if language == "ja":
            title = "旧Python版の設定を引き継ぐ"
            description = (f"旧Python版のフォルダーまたは `.env` を `--config` に指定できます。初回は同じフォルダーに `{CONFIG_FILENAME}` を作成し、元の `.env` は変更せず残します。"
                           "作成後は新しいTOML設定を優先します。相対パスは設定ファイルのあるフォルダーを基準にします。")
        else:
            title = "Reuse settings from the legacy Python version"
            description = (f"Pass the old Python installation directory or its `.env` file to `--config`. The first run creates `{CONFIG_FILENAME}` in the same directory and preserves the original `.env`."
                           " Later runs prefer the TOML file. Relative paths remain based on the selected configuration directory.")
        return f"""### {title}

{description}

```sh
./{PRODUCT}-linux-x64 --config /path/to/Send-Minecraft-notifications --check-config
./{PRODUCT}-linux-x64 --config /path/to/Send-Minecraft-notifications/.env
```

```powershell
.\\{windows_exe} --config 'C:\\path\\to\\Send-Minecraft-notifications' --check-config
.\\{windows_exe} --config 'C:\\path\\to\\Send-Minecraft-notifications\\.env'
```
"""

    if language == "ja":
        title = "旧Python版の .env を引き継ぐ"
        description = "旧版の `.env` を `--config` で直接指定して起動できます。元の設定は変更されず、`TARGET_DIR` と `PLUGIN_DIR` の相対パスも旧 `.env` のフォルダーを基準に解決されます。設定を検査した後、同じ引数を付けて起動してください。パスは実際の旧版の場所へ置き換えます。"
    else:
        title = "Reuse a legacy Python .env"
        description = "Pass the old `.env` to `--config` to reuse it without modifying it. Relative `TARGET_DIR` and `PLUGIN_DIR` paths remain based on the old `.env` directory. Validate first, then start with the same argument each time. Replace the example paths with your old installation's location."
    return f"""### {title}

{description}

```sh
./{PRODUCT}-linux-x64 --config /path/to/Send-Minecraft-notifications/.env --check-config
./{PRODUCT}-linux-x64 --config /path/to/Send-Minecraft-notifications/.env
```

```powershell
.\\{windows_exe} --config 'C:\\path\\to\\Send-Minecraft-notifications\\.env' --check-config
.\\{windows_exe} --config 'C:\\path\\to\\Send-Minecraft-notifications\\.env'
```
"""


def replace_section(document: str, name: str, body: str, *, required: bool) -> str:
    start = f"<!-- smn:{name}:start -->"
    end = f"<!-- smn:{name}:end -->"
    replacement = f"{start}\n{body.rstrip()}\n{end}"
    if start not in document and end not in document and not required:
        return f"{replacement}\n\n{document}".rstrip() + "\n"
    if document.count(start) != 1 or document.count(end) != 1:
        raise ValueError(f"Expected exactly one pair of {name} markers")
    before, remaining = document.split(start)
    if end not in remaining:
        raise ValueError(f"Reversed {name} markers")
    _, after = remaining.split(end)
    return before + replacement + after


def render_readme(document: str, tag: str, repository: str, windows_exe: str) -> str:
    for language in ("ja", "en"):
        document = replace_section(
            document, f"install-{language}",
            installation_section(tag, repository, windows_exe, language), required=True,
        )
    return document


def render_notes(document: str, tag: str, repository: str, windows_exe: str) -> str:
    instructions = "## CLI でのインストールと起動\n\n" + installation_section(tag, repository, windows_exe, "ja")
    instructions += "\n## CLI installation and startup\n\n" + installation_section(tag, repository, windows_exe, "en")
    return replace_section(document, "release-install", instructions, required=False)


def github_api(endpoint: str, *, payload: dict | None = None, paginate: bool = False):
    command = ["gh", "api", "--method", "PUT" if payload is not None else "GET", endpoint]
    if paginate:
        command += ["--paginate", "--slurp"]
    if payload is not None:
        command += ["--input", "-"]
    try:
        result = subprocess.run(
            command, input=json.dumps(payload) if payload is not None else None,
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"GitHub API request failed for {endpoint}: {error.stderr.strip()}") from error
    return json.loads(result.stdout)


def sync_readme(tag: str, repository: str) -> bool:
    """Update only managed sections on the default branch after publication."""
    # Validate before using either value in an API path.
    validate_inputs(tag, repository, "smn-main-0000000.exe")
    releases = [release for page in github_api(f"repos/{repository}/releases", paginate=True) for release in page]
    published = [release for release in releases if not release["draft"] and release.get("published_at")]
    if not published:
        raise ValueError("No published releases found")
    newest = max(published, key=lambda release: release["published_at"])
    if newest["tag_name"] != tag:
        print(f"Skipping README update for older release {tag}.")
        return False
    windows_executables = [asset["name"] for asset in newest["assets"] if asset["name"].endswith(".exe")]
    if len(windows_executables) != 1:
        raise ValueError("Expected exactly one published Windows executable")
    branch = github_api(f"repos/{repository}")["default_branch"]
    endpoint = f"repos/{repository}/contents/README.md"
    readme = github_api(f"{endpoint}?ref={quote(branch, safe='')}")
    if readme.get("type") != "file" or readme.get("encoding") != "base64":
        raise ValueError("Expected a base64-encoded README file")
    original = base64.b64decode(readme["content"]).decode("utf-8")
    updated = render_readme(original, tag, repository, windows_executables[0])
    if updated == original:
        print(f"README already documents {tag}.")
        return False
    # The blob SHA prevents overwriting a concurrent edit. A conflict fails the
    # job instead of replacing newer content; rerunning reads it again.
    github_api(endpoint, payload={
        "message": f"docs: update installation commands for {tag} [skip ci]",
        "branch": branch, "sha": readme["sha"],
        "content": base64.b64encode(updated.encode("utf-8")).decode("ascii"),
    })
    print(f"Updated README for {tag} on {branch}.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("readme", "notes", "sync-readme"))
    parser.add_argument("--tag", required=True)
    parser.add_argument("--repo", default=os.environ.get("GH_REPO", DEFAULT_REPOSITORY))
    parser.add_argument("--windows-exe")
    parser.add_argument("--path", type=Path, default=ROOT / "README.md")
    parser.add_argument("--existing", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.mode == "sync-readme":
        sync_readme(arguments.tag, arguments.repo)
        return
    windows_exe = arguments.windows_exe
    if windows_exe is None:
        from build_release import build_windows_filename, project_name, resolve_source_identity

        branch, commit = resolve_source_identity(ROOT, os.environ.get("SMN_BUILD_BRANCH"))
        windows_exe = build_windows_filename(project_name(ROOT / "pyproject.toml"), branch, commit)
    if arguments.mode == "readme":
        document = render_readme(arguments.path.read_text(encoding="utf-8"), arguments.tag, arguments.repo, windows_exe)
        destination = arguments.output or arguments.path
    else:
        document = render_notes(
            arguments.existing.read_text(encoding="utf-8") if arguments.existing else "",
            arguments.tag, arguments.repo, windows_exe,
        )
        if arguments.output is None:
            parser.error("notes requires --output")
        destination = arguments.output
    destination.write_text(document, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
