# OpenMapMC shared waypoint editing and deletion notifications

The user extended the existing creation notification request to editing and deletion. The earlier creation evidence remains in `openmapmc-waypoints.tdd.md`.

## Behavior and producer contract

- Keep the existing schema-version-1 creation record compatible.
- Accept `shared_waypoint_updated` and `shared_waypoint_deleted` with the existing waypoint fields and required `actor_uuid` / `actor_name`. The `creator_*` fields retain the waypoint owner's identity. Discord uses the actual actor, including an administrator operating on someone else's waypoint.
- Updates describe the saved new state; deletion describes the last stored state. The source logs once after successful persistence, excluding rejected operations, failures, loading and synchronization.
- The existing `OPENMAPMC_WAYPOINT_NOTIFICATIONS` switch covers all three events. All 22 catalogs contain separate creation, update and deletion templates with the same five location/name placeholders.
- Retain source restrictions, bounded JSON validation, literal label insertion and existing Discord mention suppression.

The producer change was requested in the existing owning chat `設定画面にサーバー設定を追加` (`01a13ba3-cc27-7c80-9950-feb55cc334cd`). That chat owns the OpenMapMC source changes, version-specific checks, builds and deployments. This notifier task does not edit that repository.

## RED / GREEN evidence

The new acceptance tests were committed first in `7b601d1` (`test: cover shared waypoint editing and deletion`). The selected RED run reported **48 failed, 23 passed, 70 deselected**: new mutation routing/template selection and the 44 new catalog entries failed before implementation. Existing creation cases passed.

After implementing event-specific routing and actor validation, focused synchronous parser checks passed **88 cases**. Catalog acceptance passed **66 cases** across the three events and 22 languages. The affected-area regression then passed **499 tests, 4 skipped, 1 warning in 4.16s**. Skips require Windows symlink privileges unavailable on this host; the warning is the existing Discord dependency's deprecated `audioop` import.

```powershell
$env:COVERAGE_FILE = '.uv-cache\coverage-waypoint-mutations.data'
uv --cache-dir .uv-cache run --offline --frozen --with pytest-cov pytest src/tests/test_openmapmc.py src/tests/test_waypoint_locales.py src/tests/test_mod_catalog.py src/tests/test_mod_deaths.py src/tests/test_mod_log_pipeline.py src/tests/test_advancements.py src/tests/test_advancement_pipeline.py src/tests/test_notification_locales.py src/tests/test_i18n.py src/tests/test_parser.py src/tests/test_config.py src/tests/test_toml_config.py src/tests/test_legacy_config.py src/tests/test_runtime.py src/tests/test_japanese_chat.py src/tests/test_webhook.py --basetemp=.uv-cache/pytest-waypoint-mutations -q -rs -o faulthandler_timeout=20 --cov=message.openmapmc --cov=message.parser --cov=message.i18n --cov=handlers.secrets --cov=utils.config --cov=server.server --cov-report=term-missing:skip-covered --cov-report=json:.uv-cache/coverage-waypoint-mutations.json
```

Selected-module coverage is 87%; `message.openmapmc` is **100%**, parser 95%, I18n 92%. Verification includes different actor/owner identities, missing and invalid actors, all five supported INFO layouts for each operation, custom operation templates, empty-template suppression, the shared disable switch, literal labels, and the mocked player-webhook path. An independent review found no concrete issues. Compilation and `git diff --check` passed.

Asyncio checks ran outside the restricted Windows sandbox because it blocks Python's event-loop socket pair. Discord calls were mocked. No Minecraft startup or live webhook was needed.

## Actual producer-log verification

The source event harness passed **163 checks per version** for 1.20.1, 1.21.1, 26.1.2 and 26.2. Its captured records are in the source repository's `.task-work/shared-mutations-20261015/green-{version}.log`. The records were consumed by this notifier's real `LogParser` and `I18n` for every supported language: **8 source samples × 22 languages = 176 accepted localized notifications**.

Every sample retained owner `Alice` while identifying the authenticated operation actor `Admin`. The update sample carried the new `admin edit` waypoint in `minecraft:the_end` at `101, 70, -202`; deletion carried the last saved `second point` waypoint in `minecraft:overworld` at `7, 68, 9`. All languages preserved these fields and routed the notification under `Admin`, with the matching update/deletion event ID and literal-text handling.

The source chat built and inspected distributable JARs for 1.20.1 Forge, 1.21.1 NeoForge, 26.1.2 NeoForge and 26.2 NeoForge. Its `artifacts.json` records matching event bytecode and metadata. `deployment.json` records SHA-256-matched deployment to the three designated Prism instances (1.20.1 Forge 47.4.0, 1.21.1 NeoForge 21.1.248, 26.2 NeoForge 26.2.0.88), with previous development JARs backed up and other MODs unchanged. There is no designated 26.1.2 deployment instance. Source packaging/deployment remains owned by that chat; this does not update an independent dedicated server. An older installed server JAR requires an update before it can emit editing/deletion logs.

The owning chat completed with signed source commits `3e52539` (tests) and `5b46096` (implementation), additionally reporting 730 existing configuration checks passed. No Minecraft runtime was started and no commits were pushed.
