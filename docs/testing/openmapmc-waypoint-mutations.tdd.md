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

Producer-generated mutation-log verification will be recorded after the owning chat captures the new source events. An older installed server JAR requires an update before it can emit editing/deletion logs.
