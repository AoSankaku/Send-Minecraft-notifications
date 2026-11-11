# v1.0.0-beta3 release verification

Published as a prerelease on 2026-11-11 at 19:21 JST:
[v1.0.0-beta3](https://github.com/AoSankaku/Send-Minecraft-notifications/releases/tag/v1.0.0-beta3).

## Candidate and pre-tag checks

Candidate commit `3e74df925196723784428119ae789993dc1899d3` updates the project
and lockfile to `1.0.0b3` and commits the Japanese/English release notes at
`docs/releases/v1.0.0-beta3.md`. Local release-documentation tests passed all
19 cases, and `uv --cache-dir .uv-cache lock --offline --check` passed.

Before creating or pushing the tag, the main-branch
[Build and release run 43002454122](https://github.com/AoSankaku/Send-Minecraft-notifications/actions/runs/43002454122)
completed successfully for that exact candidate SHA. The required publishing
check and both platform builds passed. Each platform passed **660 application
tests**, built its public-mode executable and passed the standalone startup
check. Publishing tests passed 13 cases; documentation tests passed 19 on each
platform; Windows executable naming tests passed 26 cases. The publication job
was skipped for this main-branch run, as intended.

## Publication and verification

The signed annotated `v1.0.0-beta3` tag points to the verified candidate commit.
The tag-triggered
[Build and release run 43002725670](https://github.com/AoSankaku/Send-Minecraft-notifications/actions/runs/43002725670)
then passed all four jobs, including publication, for the same SHA.

The published release is a prerelease, not a draft, with exactly six nonempty
uploaded assets:

- `send-minecraft-notifications-v1.0.0-beta3-windows-x64.exe`
- `send-minecraft-notifications-windows-x64.zip`
- `SHA256SUMS-windows-x64.txt`
- `send-minecraft-notifications-linux-x64`
- `send-minecraft-notifications-linux-x64.zip`
- `SHA256SUMS-linux-x64.txt`

Both checksum files were downloaded. Their own SHA-256 values match GitHub's
asset digests, and all four binary/archive entries match the corresponding
GitHub asset digests. The published release body matches the prepared bilingual
notes and generated beta3 installation instructions.

All three previously published releases retain the same release IDs and asset
IDs/names/digests. All four pre-existing tag references retain the same object
SHAs. No existing release or asset was replaced.

The successful publication automatically updated the managed README
installation sections in commit `49ff69b`; local main was fast-forwarded to
that update. Full CI logs, API snapshots and downloaded checksum files were
kept only in ignored local verification paths.
