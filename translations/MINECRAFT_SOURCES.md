# Minecraft title translations

`minecraft.json` contains only advancement title and legacy achievement name entries extracted from official Mojang language resources. It contains no game code, textures, descriptions, or executable content. It is included in the existing PyInstaller `translations` data directory and requires no network access at runtime.

The language strings originate from Minecraft / Mojang Studios and its translation contributors; they are not original project text. The project's MIT license does not relicense third-party Minecraft resources. Notification templates in the sibling locale JSON files are maintained by this project.

Sources are the official [version manifest](https://piston-meta.mojang.com/mc/game/version_manifest_v2.json), version metadata and client archives on `piston-meta.mojang.com` / `piston-data.mojang.com`, and language assets on `resources.download.minecraft.net`. Each downloaded version metadata document, asset index, client archive, and language file has its source URL and verified SHA-1 recorded in the catalog's `sources` array. SHA-1 here verifies Mojang asset identity, not authentication of arbitrary content.

Pinned source releases, in chronological order:

| Release | English titles | Purpose |
| --- | ---: | --- |
| 1.11.2 | 34 | Legacy achievements (`.lang`) |
| 1.12.2 | 55 | Early advancements (`.lang`) |
| 1.16.5 | 80 | Nether-era advancements |
| 1.20.1 | 110 | Trails & Tales advancements |
| 1.21.11 | 126 | Later advancement names |
| 26.3 | 127 | Newest bundled advancement names |

The application supports 22 locale codes listed in the README. Missing historical locales, such as `zh-HK` before it was available, remain empty in those snapshots. Individual untranslated entries are omitted. The runtime preserves the English title when it has no matching translation. Automatic mode uses the latest available translation per key and keeps English aliases from older snapshots. Different keys with the same English name and different output translations remain ambiguous; use a custom dictionary to resolve them.

To rebuild from official data (maintainer-only network operation):

```sh
uv run python scripts/update_minecraft_translations.py
```

To add a source release, pass the complete ordered set of versions, oldest first:

```sh
uv run python scripts/update_minecraft_translations.py --versions 1.11.2 1.12.2 1.16.5 1.20.1 1.21.11 26.3
```

The updater caches checksum-verified downloads under `.uv-cache/minecraft`, reads JARs as ZIPs, and accepts only the fixed official HTTPS host allowlist. It never starts Minecraft or loads Java classes. Inspect catalog changes and run the targeted tests before committing updated data. Cached files and full downloaded resources are excluded from Git.

This is coverage of language-resource snapshots, not a promise that all Minecraft versions/loaders were started or tested. Server logs contain rendered display names; they do not reliably retain the original advancement ID or translation key.
