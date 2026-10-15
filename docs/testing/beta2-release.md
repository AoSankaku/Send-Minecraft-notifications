# v1.0.0-beta2 release verification

Published on 2026-10-16 JST from signed tag `v1.0.0-beta2`, commit `ae984f4`:

https://github.com/AoSankaku/Send-Minecraft-notifications/releases/tag/v1.0.0-beta2

## Build evidence

- Build run `38763058845`: Linux x64 and Windows x64 build jobs succeeded. Each platform passed 545 application tests and 19 release-documentation tests. Windows also passed 26 executable-naming tests. Both standalone smoke checks passed, including bundled resources, TOML initialization, configuration validation and legacy settings migration.
- Docker run `38763058403` succeeded. The beta tag remains a prerelease and does not replace the stable `latest` container tag.
- The final six assets include both standalone binaries, both ZIPs and both checksum files. All four binary/archive SHA-256 entries matched. Both ZIPs contain exactly their matching binary, README, LICENSE and example TOML.

## Publishing-test correction and recovery

The initial publishing job stopped before uploading any assets because a Linux-only test fixture used `v1.2345678901234567890-beta.123`, which lacks the patch component required by the publisher's prerelease detection. Its assertion incorrectly expected prerelease publication for that fixture.

Commit `defa8cf` corrects the fixture to `v1.2345678901234567890.0-beta.123` and adds a small Linux publishing-check workflow for relevant pushes and pull requests. Run `38763692413` passed all 13 publishing tests. Product code and the existing release tag were unchanged.

The already successful build artifacts were then downloaded and verified, attached to the existing draft, and published using the same versioned filenames and generated installation instructions. The original release run retains its failed publishing-test result; the separate corrected check records the successful verification. No tag was moved and no product rebuild was necessary.

## Publication verification

GitHub reports the release as published and prerelease, with exactly six assets. GitHub's SHA-256 digest for every uploaded asset matches the locally verified CI artifact. The Windows executable downloaded from the published release also matches the CI output byte for byte. Release notes include the Japanese/English changes and generated installation commands.

The self-contained Windows binary was exported as `smn-main-ae984f4.exe` to `C:\Users\abcde\dev\normal-apps\[output-executables]`, using the app, branch and source HEAD resolved before the build. The exported file's SHA-256 matches, and every direct child of that folder is an EXE or shortcut.
