# Server crash notifications and report sharing

## Intent and acceptance criteria

The user requested abnormal-server-termination notifications, automatic crash
report uploads, and independent delivery to the normal and administrator Discord
channels. The following journeys were derived during this implementation; there
was no external plan document.

- A server operator receives one abnormal-termination alert for definitive
  server failure evidence, even if no upload succeeds.
- A newly written server report triggers detection without a matching log line.
  Existing reports, client-only reports, chat and generic errors do not.
- An operator may additionally monitor a specific Java PID for termination
  without a crash log; ordinary idle periods do not trigger alerts.
- Uploads are opt-in. Stable reports are preferred; a bounded current-log tail
  is the fallback. Credentials and common private identifiers are redacted before
  upload to the fixed official mclo.gs API.
- Alerts and report links can go to the main webhook, the administrator webhook,
  or both. A failed destination or upload does not prevent the other delivery.
- Crash processing keeps normal forwarding responsive and releases pending
  tasks and HTTP sessions on shutdown.

## RED checkpoint

Commit `9632e93` on the active `main` branch added the test-first reproducer.
The canonical focused run collected and executed **44 tests: 38 failed,
5 passed, 1 skipped**. Positive server crash records yielded no abnormal alert;
report/PID polling, crash configuration and upload implementations were missing.
The five existing generic/client false-positive exclusions already passed.

The platform skip concerns Windows symbolic-link creation privileges. A separate
portable symlink-flag test exercises the rejection requirement without that
privilege. Test compilation and collection succeeded before the checkpoint;
these failures were feature failures rather than syntax or environment errors.
The tests mocked all external notification/upload boundaries.

Local detailed RED output: `.test-crash-red.log` (excluded from Git).

## Verification results

Final combined verification passed **245 tests, with 2 skips**, in 6.21 seconds.
Both skips concern actual symbolic-link creation privileges on this Windows
host; the portable crash-report symlink-flag rejection test passed. The existing
discord.py `audioop` deprecation warning is unrelated to this feature.

The successful command was run outside the Windows sandbox because its
temporary-directory/socketpair restrictions prevent normal asyncio tests:

```powershell
$env:PYTHONPATH = (Join-Path $PWD '.pytest_cache/coverage-tool') + [IO.Path]::PathSeparator + (Join-Path $PWD 'src')
.\.venv\Scripts\python.exe -m coverage run --data-file .pytest_cache/crash.coverage --source=server.crash,message.log_upload -m pytest -q --basetemp .pytest_cache/crash-final-accepted src/tests/test_crash_notifications.py src/tests/test_log_upload.py src/tests/test_config.py src/tests/test_toml_config.py src/tests/test_legacy_config.py src/tests/test_runtime.py src/tests/test_notification_locales.py src/tests/test_webhook.py src/tests/test_parser.py src/tests/test_advancement_pipeline.py src/tests/test_mod_log_pipeline.py
.\.venv\Scripts\python.exe -m coverage report --data-file .pytest_cache/crash.coverage --show-missing --fail-under 80
```

Coverage 7.17.0 was installed only into the ignored
`.pytest_cache/coverage-tool` directory; it is not an application dependency.
The report covers the two new production modules, not the entire application:

| Module | Statements | Covered | Coverage |
| --- | ---: | ---: | ---: |
| `message/log_upload.py` | 98 | 89 | 91% |
| `server/crash.py` | 459 | 389 | 85% |
| Total | 557 | 478 | 86% |

| Guarantee | Evidence | Result |
| --- | --- | --- |
| Definitive server failures alert once, suppress normal-stop notices, and reset on the next trusted boot | `test_crash_notifications.py` lifecycle and startup regressions | PASS |
| Main/render/client crash preparation and FML client reports cannot masquerade as server failures | Server/client classification regressions | PASS |
| Existing reports never replay, including reports outside the active scan window | Historical-report and large-directory regressions | PASS |
| New reports wait for stable content; incomplete/malformed reports do not block fallback forever | Stable/incomplete/report-grace regressions | PASS |
| Actual reports prevent unnecessary tail uploads; a full queue retries pending details | Upload fallback and queue regressions | PASS |
| Fast restart preserves unpolled previous-crash details without a second alert | Upload-enabled no-intervening-poll regression; failed before correction, then passed | PASS |
| PID exit has a final-log grace period, respects clean stops, and consumes old process identities | PID lifecycle regressions | PASS |
| Main/admin/both routing, identical-URL deduplication and failure isolation work | Configuration-to-notification integration tests | PASS |
| Uploads are opt-in, sanitize common credential forms, enforce byte/line bounds and validate response links | `test_log_upload.py`, including JSON auth, CLI access tokens, mapped IPv6 and multibyte input | PASS |
| In-flight upload does not block normal chat; shutdown cancels work and closes sessions | Async cleanup and quiet-watcher regressions | PASS |
| Existing config migration, parser, translation and webhook behavior remain compatible | Shared regression targets in the command above | PASS |

The user-designated 26.2 / NeoForge 26.2.0.88 runtime captures were also replayed
using the existing local no-network harness:

```powershell
.\.venv\Scripts\python.exe .pytest_cache/replay-minecraft-26.2.py
```

All **18 files / 3,898 lines** completed. Both Japanese and English produced
the same 14 shutdown and 2 chat payloads as before this feature, with no false
server-crash alert from the captured client crashes. The last correction only
changes handling of pending server report files; these captures' temporary
replay directory contains none, so the replay evidence remains applicable.

An independent reviewer identified and rechecked the report queue/fallback,
client/server classification and restart-generation corrections. The final
recheck reported **no remaining actionable findings**. Targeted compilation and
`git diff --check` passed. Detailed outputs are kept in ignored
`.test-crash-final.log`, `.test-crash-26-2-replay.log`, and
`.pytest_cache/crash.coverage`.

No Minecraft process or real webhook/mclo.gs request was needed. The HTTP
protocol was tested using mocked responses, not live publication. There is no
claim of a full Minecraft version/loader matrix or successful public-service
delivery during this task. The original 26.2 single-player log limitations
documented in `minecraft-26.2-log-replay.md` remain separate from this feature.

## Upload protocol and operational scope

The uploader uses the [official mclo.gs API](https://api.mclo.gs/): JSON POST
to `https://api.mclo.gs/1/log`, with redirects disabled and a bounded timeout.
The application limits content below the service's 10 MiB / 25,000-line
ceiling, validates the returned public link, and discards the deletion token.
No report content or API response body is included in a Discord failure notice.

This feature observes Minecraft failures; it does not restart or terminate the
server. Silent termination requires an explicitly configured Minecraft process
PID. The process identity is retained rather than looking up arbitrary Java
processes. The user must update that setting after recreating the server process.

Automatic upload is disabled by default because it shares local log content with
a public service. Redaction covers configured credentials and common secret/IP/
home-directory forms, but does not claim to recognize all private mod output.
