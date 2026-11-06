# Modded dedicated-server startup failure detection

Verified on 2026-11-06. Requirements were derived from the user's report and
[shared Forge 1.20.1 / Forge 47.4.10 log](https://mclo.gs/JFEVENR).

## Findings and behavior

The pre-change source already recognized the final structured Minecraft main
error in the shared log. It did not recognize the preceding server-only
`ServerModLoader` report record. It also kept suppressing alerts after a failed
attempt when the next JVM failed before emitting the server-thread boot record.
This does not establish which executable/configuration caused the original
missed notification.

- Recognize complete startup-failure wording with or without `the` and
  `minecraft`, on main/server threads at ERROR/FATAL severity.
- Recognize saved/failed-to-save crash reports from Forge/NeoForge's server mod
  loader, including failures before the Minecraft server thread exists.
- Reset incident deduplication at Fabric loader boot, legacy Forge server
  tweaker boot, Forge/NeoForge ModLauncher server boot, and modern NeoForge FML
  entrypoint boot. These boot markers are not crash evidence.
- Normalize ANSI/Minecraft formatting codes and anchor crash markers at the
  beginning of the message. Preserve exclusions for client records, generic
  mod errors, quoted/chat markers and subordinate service failures.
- Retain existing alert routing, localization, disabled-detection behavior,
  report uploads, fallback uploads and normal-stop suppression.

## TDD and review evidence

| Stage | Local checkpoint | Observed result |
| --- | --- | --- |
| Initial reproductions | `6425056` | 22 failed, 23 passed, 50 deselected |
| Initial fix | `dda1595` | Same selected target: 45 passed, 50 deselected |
| Review reproductions | `e36f348` | 4 failed, 4 passed, 93 deselected |
| Review corrections | `73fdd8a` | 11 passed, 93 deselected, including extra punctuation/console-format checks |

The initial selected command was:

```powershell
.venv/Scripts/python.exe -m pytest -q src/tests/test_crash_records.py src/tests/test_crash_notifications.py -k 'server_failure_records or non_server_failures or loader_boot_records or chat_client_and_untrusted or reported_forge or failure_before_server_thread' --tb=short -o faulthandler_timeout=15 --basetemp .pytest_cache/startup-green-unrestricted
```

The English replay assertion was corrected to compare against the actual
translated notification; the old counting helper only recognized a different
English phrasing. Independent review then found the modern FML boot gap and
overly broad generic server-failure suffix matching. Both were reproduced,
corrected and accepted in focused re-review with no remaining findings.

## Final verification

```powershell
$env:COVERAGE_FILE = '.uv-cache/startup-failures.coverage'
uv --cache-dir .uv-cache run --offline --frozen --with pytest-cov pytest -q src/tests/test_crash_records.py src/tests/test_crash_notifications.py src/tests/test_log_upload.py src/tests/test_parser.py src/tests/test_notification_locales.py --tb=short -rs -o faulthandler_timeout=15 --basetemp .pytest_cache/startup-regressions --cov=server.crash --cov-report=term-missing:skip-covered --cov-report=json:.uv-cache/startup-coverage.json
```

Result: **173 passed, 1 skipped, 1 warning in 5.90s**. Crash-module statement
coverage: **86% (422/493)**. The skip is an existing symlink test because Windows
cannot create that symlink with the available privileges. The warning is the
existing Discord dependency's `audioop` deprecation. Compilation of the changed
Python files and `git diff --check` also passed. Tests used the existing Windows
sandbox workaround; no Minecraft process or watcher was launched.

| Guarantee | Evidence | Type |
| --- | --- | --- |
| Old Fabric and Forge-style runtime failures remain recognized | `test_crash_records.py` | Unit |
| Reported Forge startup failure is recognized before the final main error | `test_crash_notifications.py::test_reported_forge_startup_failure_replays_once_per_boot` | Offline integration, ja/en |
| Another failure before server-thread creation produces another alert | `test_failure_before_server_thread_is_notified_again_after_loader_restart` | Offline integration |
| Current NeoForge FML and older LaunchWrapper/ModLauncher boot formats reset incidents | `test_loader_boot_records_reset_failed_start_attempts` | Unit |
| Client errors, quoted markers and server status/metrics service failures do not trigger alerts | `test_non_server_failures_and_quoted_markers_are_ignored` | Unit |
| Routing, report uploads, fallback uploads and parser/localization regressions remain covered | Final command above | Unit / offline integration |

## Full shared-log replay

The captured UTF-8 copy contains **1,761 lines**. All lines were replayed through
`LogUtil.get_log_diff`, `combine_chat_records` and `Server.on_line_added` in
64-line batches. Both ja/en replays ran two complete startup attempts. Each
attempt consumed every line once, produced exactly **one crash alert**, and
scheduled exactly **one mocked latest-log fallback upload**. Re-reading an
unchanged file produced no additional records. Webhook delivery and uploads
were replaced with recording doubles; no external notifications or uploads
were sent.

Only a minimal anonymized excerpt is committed as a regression fixture. Local
evidence remains ignored under `.pytest_cache` and `.test-startup-*.log`.

## Format sources and limits

- [Fabric API's historical dedicated-server failure log](https://github.com/FabricMC/fabric-api/issues/617)
  supplies the main/FATAL server-failure form.
- [Forge 1.12 server patch](https://github.com/MinecraftForge/MinecraftForge/blob/1.12.x/patches/minecraft/net/minecraft/server/MinecraftServer.java.patch)
  preserves the unexpected-exception runtime marker.
- [Forge ServerModLoader](https://github.com/MinecraftForge/MinecraftForge/blob/1.20.x/src/main/java/net/minecraftforge/server/loading/ServerModLoader.java)
  and [NeoForge ServerModLoader](https://github.com/neoforged/NeoForge/blob/1.21.x/src/main/java/net/neoforged/neoforge/server/loading/ServerModLoader.java)
  pass their server-specific logger when reporting fatal mod-loading failures.
- [Current NeoForge FML entrypoint](https://github.com/neoforged/FancyModLoader/blob/main/loader/src/main/java/net/neoforged/fml/startup/Entrypoint.java)
  emits the new JVM-uptime boot record; its
  [logging configuration](https://github.com/neoforged/FancyModLoader/blob/main/loader/src/main/resources/net/neoforged/fml/startup/log4j2.xml)
  defines full file loggers and shortened console loggers.

This verifies representative log formats and the supplied real server log,
not a live runtime matrix of every Minecraft/loader release. Generic Fabric/FML
client-or-server failure titles alone are deliberately insufficient. Failures
that never reach the monitored log require a server crash report or configured
PID monitoring. Existing logs/reports are not replayed on notifier startup.
