# Multilingual advancement notification verification

Source requirements: issue #1 (advancement/achievement name translation), expanded by the user to the first and second language scopes, totaling 22 locales. Journeys were derived during this implementation.

## Intended behavior

- Administrators choose one notification language; existing settings default to Japanese.
- Vanilla advancement, goal, challenge and legacy achievement names use bundled official language data offline.
- Exact administrator dictionary entries override known titles and translate custom mod/datapack titles.
- Unknown titles and conflicting names belonging to different translation keys remain literal original text.
- Optional source-version selection chooses one bundled dictionary snapshot. Otherwise, historical English aliases use the newest available translation per key.
- Existing administrator-written server messages/tips and independent Japanese chat conversion retain their configured behavior.

## RED evidence

The initial engine and data-updater targets were executed before production code existed and failed on the intended missing `message.advancements` and `update_minecraft_translations` modules. Locale integration tests likewise failed on the missing `message.locales` API. These tests were recorded in local checkpoint commit `4537333` (`test: cover multilingual advancement notifications`).

Independent review later found two concrete edge cases. Both received reproducing tests before correction:

- Titles containing `joined the game` / `left the game` incorrectly reached generic join/leave handlers (2 failed, 2 passed before direct milestone dispatch).
- A literal `%server-count%` in a custom/unknown title was expanded unintentionally (1 failed before template-first rendering; subsequently parameterized over all four milestone event types).

## GREEN evidence

Final affected-area command (PowerShell, with the additional coverage tool already cached):

```powershell
$env:COVERAGE_FILE = '.uv-cache\coverage-localization-final.data'
uv --cache-dir .uv-cache run --offline --frozen --with pytest-cov pytest src/tests/test_advancements.py src/tests/test_advancement_pipeline.py src/tests/test_notification_locales.py src/tests/test_i18n.py src/tests/test_parser.py src/tests/test_config.py src/tests/test_toml_config.py src/tests/test_legacy_config.py src/tests/test_runtime.py src/tests/test_japanese_chat.py src/tests/test_webhook.py scripts/test_update_minecraft_translations.py --basetemp=.uv-cache/pytest-localization-reviewed -q -rs -o faulthandler_timeout=20 --cov=message.advancements --cov=message.locales --cov=message.i18n --cov=message.model --cov=message.parser --cov=handlers.secrets --cov=utils.config --cov=utils.runtime --cov=server.server --cov=main --cov-report=term-missing:skip-covered --cov-report=json:.uv-cache/coverage-localization.json
```

Result: **298 passed, 1 skipped, 1 warning in 3.69s**. The skipped existing test requires symlink creation, which is unavailable on this host. The warning comes from the existing Discord dependency's deprecated `audioop` import.

| Guarantee | Evidence | Result |
| --- | --- | --- |
| All 22 locales translate current vanilla names without network access | `test_advancements.py`, `test_advancement_pipeline.py` | PASS |
| Old achievements remain distinct from modern advancements | `test_advancements.py`, milestone handler tests | PASS |
| Missing/ambiguous names remain original; custom entries and explicit versions work | `test_advancements.py` | PASS |
| Invalid language, dictionary, boolean and version settings fail before connecting | `test_advancement_pipeline.py`, `test_notification_locales.py` | PASS |
| Every bundled event catalog has complete keys and preserved placeholders | `test_notification_locales.py` | PASS |
| Local event overrides merge per key with selected-language/English fallback | `test_i18n.py` | PASS |
| Common log headers, colored text, bracketed titles, chat/command exclusions work | `test_notification_locales.py`, `test_parser.py`, `test_japanese_chat.py` | PASS |
| Title text cannot trigger join/leave events or expand notification variables | Collision regressions and four literal-token pipeline cases | PASS |
| Frozen resource paths can load the bundled title dictionary | `test_advancement_pipeline.py` | PASS |
| Existing TOML/legacy config and webhook mention suppression remain compatible | Config/runtime/webhook regression targets | PASS, one platform skip |
| Updater validates language shapes, filters titles, verifies cached hashes and official HTTPS hosts | `scripts/test_update_minecraft_translations.py` | PASS |

Measured coverage for the selected affected modules: **86%** (806/934 statements). Advancement engine: 93%; locale normalization and message model: 100%; notification I18n: 92%; parser: 95%. Coverage is not a claim that every old server/lifecycle branch was exercised.

The official resource updater also completed a real checksum-verified import for all six pinned snapshots. `python -m compileall` and `git diff --check` passed. An independent reviewer reviewed the implementation and both corrective diffs; no actionable findings remained.

## Limits and environment

No Minecraft process or real Discord notification was needed. Tests use representative log records and mocked outbound webhook methods; there is no claim of a full Minecraft version/loader runtime matrix or exhaustive arbitrary mod coverage. Historical official language gaps remain untranslated as documented.

On this Windows host, the restricted sandbox blocks the loopback socket pair used to construct Python's asyncio event loop. A bounded faulthandler diagnostic identified that environment issue; the affected test processes were stopped, and the mocked offline integration tests passed outside that sandbox. No server or watcher was left running.

The verification above covers changes after the initial RED checkpoint. Preserve this report if local development commits are later squashed; no remote push is part of this task.
