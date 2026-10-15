# OpenMapMC shared waypoint creation notifications

The user requested notifications when an OpenMapMC shared waypoint is created, and explicitly authorized asking the existing OpenMapMC chat to add a log if no suitable log existed.

## Source investigation and contract

The local OpenMapMC Delta repository is `C:\Users\abcde\dev\minecraft\mods\odyssey-map-delta`. Its `SharedWaypointServer` CREATE path commits persistent state and returns success feedback, but the investigated baseline had no creation INFO log. This was checked across the maintained 1.20.1, 1.21.1, 26.1.2 and 26.2 roots; ordinary warning/error logs were insufficient to identify creation.

The authorized change was sent to its existing chat `設定画面にサーバー設定を追加` (`01a13ba3-cc27-7c80-9950-feb55cc334cd`), which owns that repository. The receiving chat confirmed the four source paths and began source-side tests/implementation. No OpenMapMC source files were edited by this notifier task.

Source-side implementation then passed its creation-event checks in all four roots. As an integration check, the actual captured `OPENMAPMC_EVENT` records in `.task-work/shared-events-20261015/green-{1.20.1,1.21.1,26.1.2,26.2}.log` were fed into the notifier's real `LogParser` and selected Japanese `I18n`. All four were accepted as `on_shared_waypoint_created`, creator `Alice`, name `拠点`, dimension `minecraft:overworld`, coordinates `123, 64, -456`. This verifies the producer/consumer contract using produced logs, not only a separately written fixture. An additional harness log was also accepted. Source-side builds/deployment remain owned and reported by that chat.

The agreed log body is `OPENMAPMC_EVENT ` followed by compact single-line JSON with `schema_version: 1`, `event: "shared_waypoint_created"`, UUID strings `waypoint_id` / `creator_uuid`, string fields `creator_name` / `name` / `dimension`, and finite numeric `x` / `y` / `z`. The source must log exactly once after successful CREATE persistence, never on rejected/failed creation, loading, snapshots, editing, deletion or personal waypoint operations. This is independent of MOD language-file extraction.

## RED / GREEN evidence

- Before implementation, all five representative log-layout tests executed and failed because the parser returned no creation notification. The 22 catalog tests failed because the event key was absent. These tests are recorded in local checkpoint `0c6880b` (`test: cover shared waypoint creation notifications`).
- Added strict bounded parsing, source restrictions, nonrecursive literal substitution, configuration switch and 22 localized event templates.
- A focused synchronous run passed 39 parser/config cases. Catalog tests passed for all 22 languages.
- Final affected-area verification: **403 passed, 4 skipped, 1 warning in 4.56s**. Skipped tests require symlink creation unavailable on this Windows host. The existing Discord dependency warns about deprecated `audioop`.

Final command (PowerShell, test tools already cached):

```powershell
$env:COVERAGE_FILE = '.uv-cache\coverage-openmapmc.data'
uv --cache-dir .uv-cache run --offline --frozen --with pytest-cov pytest src/tests/test_openmapmc.py src/tests/test_waypoint_locales.py src/tests/test_mod_catalog.py src/tests/test_mod_deaths.py src/tests/test_mod_log_pipeline.py src/tests/test_advancements.py src/tests/test_advancement_pipeline.py src/tests/test_notification_locales.py src/tests/test_i18n.py src/tests/test_parser.py src/tests/test_config.py src/tests/test_toml_config.py src/tests/test_legacy_config.py src/tests/test_runtime.py src/tests/test_japanese_chat.py src/tests/test_webhook.py --basetemp=.uv-cache/pytest-openmap-final -q -rs -o faulthandler_timeout=20 --cov=message.openmapmc --cov=message.parser --cov=message.i18n --cov=handlers.secrets --cov=utils.config --cov=server.server --cov-report=term-missing:skip-covered --cov-report=json:.uv-cache/coverage-openmapmc.json
```

Measured selected-module coverage: 87%; new OpenMapMC helper: 98%, parser: 95%, I18n: 92%. Existing server lifecycle branches were not exhaustively exercised. `compileall` and `git diff --check` passed. An independent reviewer found no concrete issues in the notifier changes.

| Guarantee | Evidence |
| --- | --- |
| Creator, waypoint name, dimension and coordinates reach the mocked player webhook | `test_server_routes_waypoint_to_creator_and_preserves_name_tokens` |
| Common Vanilla/Fabric, Forge/NeoForge, Paper and old INFO layouts work | Five `test_shared_creation_event_extracts_creator_name_location_and_dimension` cases |
| Invalid UUIDs, dimensions, coordinate ranges, types and names are dropped | Parameterized invalid-event tests |
| Oversized/malformed JSON, duplicate fields, unsupported event/schema and booleans in numeric fields are rejected | Reserved-event tests |
| Chat, unsigned wrappers, other explicit loggers and async chat threads cannot impersonate events | Source validation tests |
| User labels preserve placeholder-like text, Unicode and section signs literally | Literal-name tests |
| Events can be disabled and invalid switch values fail config checks | Switch/config tests |
| Each of the 22 languages preserves exactly the five required placeholders | `test_waypoint_locales.py` |
| Existing MOD/vanilla translations, chat handling, config migration and mention suppression remain compatible | Listed affected-area regression targets |

No live Discord notification or Minecraft startup was required. Mocked asyncio integration tests ran outside the restricted Windows sandbox because the sandbox blocks Python's event-loop socket pair. Source-side packaging/deployment and version-specific build results belong to the OpenMapMC chat; source changes alone do not imply that an installed older server JAR emits the new log.
