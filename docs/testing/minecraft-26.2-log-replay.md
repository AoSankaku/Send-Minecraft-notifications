# Minecraft 26.2 captured-log verification

Verified on 2026-10-27 against application commit
`89d680e9f0b72ffc5523e291950458557de105df`.

## Result

The captured 26.2 records exercise chat and shutdown notifications successfully,
but do **not** establish complete dedicated-server compatibility. Monitoring this
single-player client's log directly also reproduces a duplicate chat notification
and leaves its localized advancement messages unrecognized. No application code
was changed during this verification.

## Actual source

The user designated the 26.2 single-player verification launch configuration:

```text
~\AppData\Roaming\PrismLauncher\instances\26.2 mod creation test\minecraft\logs
```

The input was `latest.log` and all 17 dated `*.log.gz` archives, covering
2026-10-06 through 2026-10-26: **18 files, 3,898 lines**. All decoded as UTF-8
without replacement characters. Debug logs were excluded to avoid counting a
second capture of the same events.

The instance's `mmc-pack.json` specifies Minecraft `26.2` and NeoForge
`26.2.0.88`. Fourteen captures contain an actual integrated-server startup
record. For example, `latest.log` contains:

```text
[26Oct2026 21:41:07.242] [Server thread/INFO] [net.minecraft.client.server.IntegratedServer/]: Starting integrated minecraft server version 26.2
```

The other four files contain no integrated-server startup record and contribute
no recognized notifications. These inputs are actual captured runtime logs,
separate from the previously documented OpenMapMC producer harness logs.

## Replay method and observations

Each capture was replayed independently for `ja` and `en`, using a temporary
configuration with the default `MINECRAFT_VERSION = ""`. The harness appended
the captured records to a temporary log in batches of 64 lines and used the
application's `LogUtil.get_log_diff`, `combine_chat_records`,
`Server.on_line_added`, translations, `DiscordWebhook`, and discord.py payload
construction. It replaced only the final
`AsyncWebhookAdapter.execute_webhook` transport with an `AsyncMock`.

Assertions checked that every input line was consumed once, unchanged files
produced an empty diff, generated payloads were nonempty, and mentions were
disabled. Each language produced exactly **16 mocked Discord payloads**:

| Actual captured records | Records | Observed result per language |
| --- | ---: | --- |
| Server shutdown (`Stopping server`) | 14 | 14 shutdown payloads |
| One player chat, recorded by server and client | 2 | 2 identical player payloads |
| Japanese client-side advancement announcements | 6 | No advancement payloads |
| Integrated-server startup announcement | 14 | No startup payloads |

The chat pair is at lines 132–133 of `2026-10-24-3.log.gz`. Its first record
uses `Server thread` / `net.minecraft.server.MinecraftServer`; its second uses
`Render thread` / `net.minecraft.client.gui.components.ChatComponent` with
`[CHAT]`. Both become `on_secure_chat_other`, with the same sender and
content `` `:squirr:` ``. The duplicate comes from two source records, not
repeated file-diff delivery.

Six advancement announcements occur in archives `2026-10-25-1`,
`2026-10-25-3`, `2026-10-25-4`, and `2026-10-25-7`. They use
`Render thread` and `[System] [CHAT]` with Japanese announcement text. The
current parser's English server announcement rules do not recognize them.

The integrated startup record is an early startup announcement, not the
dedicated server's `Done (...)!` readiness record. It does not exercise the
existing startup-notification rule.

## Related verification

The existing parser and translation pipeline targets passed:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest_cache/26-2-baseline-unrestricted src/tests/test_parser.py src/tests/test_advancement_pipeline.py src/tests/test_mod_log_pipeline.py
# 70 passed, 1 warning in 1.05s
```

A separate offline `--check-config` call confirmed that explicitly setting
`MINECRAFT_VERSION = "26.2"` fails validation because that version is not a
bundled translation snapshot. Leave this setting empty when using these logs;
it selects translation data and is not a declaration of the running server
version. The default configuration was accepted throughout the replay.

Local evidence from this run, kept outside version control:

- `.test-26-2-baseline.log`: related test result.
- `.test-26-2-replay.log`: replay summary.
- `.pytest_cache/replay-minecraft-26.2.py`: local replay harness.
- `.pytest_cache/minecraft-26.2-replay-results.json`: per-file SHA-256 hashes,
  line counts, observed announcement counts, and per-language payload totals.

Windows sandbox restrictions prevented normal temporary-directory/asyncio
operation. The successful tests and replay ran outside that sandbox with the
Discord transport still mocked.

## Limits

These are single-player client captures containing an integrated server, not
dedicated-server logs. They contain no English server-side join, leave,
advancement, goal, challenge, or death announcements, and no
`OPENMAPMC_EVENT` records. Those behaviors remain unverified with actual 26.2
runtime records; the existing tests use representative records instead.

No new Minecraft process or file watcher was started. The replay exercises
log reading through outbound payload construction, but does not exercise live
filesystem notifications or delivery to Discord. **No external notifications
were sent.**
