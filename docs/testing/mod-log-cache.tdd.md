# MOD resource translation and cache verification

User request: identify translations for Create and other MOD advancement/death logs from a configured `mods` folder, and persist extracted translation data in an automatically created cache directory. The current first/second language scope remains 22 locales.

## Behavior

- Empty `MODS_DIR` preserves the previous application behavior without creating a cache.
- A configured folder scans only direct child JARs. Language JSON/old `.lang` and advancement display definitions are read as ZIP data; Java code is never loaded or executed.
- `TRANSLATION_CACHE_DIR` defaults to `translation-cache` relative to the configuration file. Content SHA-256 keys extraction caches for all supported locales. Cache hits still hash the JAR to verify identity; they do not parse/decompress its resources again.
- Changed content, changed extractor schema and corrupt cache data trigger extraction again. A changed-during-extraction JAR is skipped instead of publishing mismatched cached data. Removed mods stop contributing translations without automatic cache deletion.
- English and selected-language strings retain source/namespace association. Conflicting translations and missing/incompatible translations preserve original text rather than borrowing an unrelated MOD's wording.
- Recognized death templates retain player/attacker/item arguments as literal values, independent of notification placeholder expansion. Arbitrary chat/command text is not reclassified as a death event.
- Cache contents are resource translations and title metadata, never observed log lines, chat, player data or webhook settings.

## RED evidence

Before implementation, the scanner and death matcher tests failed with missing `message.mod_catalog` / `message.mod_deaths` modules. A config-check pipeline test executed and failed because the requested cache folder was not created. These tests were recorded in SSH-signed local checkpoint `8272dad` (`test: cover cached mod log translations`).

Subsequent review led to reproducing regressions for multi-namespace resources, same-key/different-English collisions, conflicting translation-only providers, missing target death arguments, legacy MOD achievement integration, deep invalid JSON and JAR replacement during parsing. The missing-argument and legacy pipeline reproductions both failed before their corrective changes.

## Final verification

Executed affected-area regression/coverage command (PowerShell; pytest-cov was already cached):

```powershell
$env:COVERAGE_FILE = '.uv-cache\coverage-mod-logs.data'
uv --cache-dir .uv-cache run --offline --frozen --with pytest-cov pytest src/tests/test_mod_catalog.py src/tests/test_mod_deaths.py src/tests/test_mod_log_pipeline.py src/tests/test_advancements.py src/tests/test_advancement_pipeline.py src/tests/test_notification_locales.py src/tests/test_i18n.py src/tests/test_parser.py src/tests/test_config.py src/tests/test_toml_config.py src/tests/test_legacy_config.py src/tests/test_runtime.py src/tests/test_japanese_chat.py src/tests/test_webhook.py --basetemp=.uv-cache/pytest-mod-logs-reviewed -q -rs -o faulthandler_timeout=20 --cov=message.mod_catalog --cov=message.mod_deaths --cov=message.log_translations --cov=message.advancements --cov=message.parser --cov=message.model --cov=handlers.secrets --cov=server.server --cov=main --cov=utils.config --cov=utils.runtime --cov-report=term-missing:skip-covered --cov-report=json:.uv-cache/coverage-mod-logs.json
```

Result: **341 passed, 4 skipped, 1 warning in 3.99s**. Four symlink tests were skipped because this Windows environment cannot create symlinks; one is an existing TOML migration test. Existing Discord dependency emits an `audioop` deprecation warning.

Affected-module coverage: **87%** (1183/1358 statements). MOD scanner/cache: 86%; death matching: 97%; translator integration factory and message model: 100%; milestone parser: 95%. This does not claim exhaustive coverage of pre-existing server lifecycle/CLI branches.

| Guarantee | Tests | Result |
| --- | --- | --- |
| All supported locales reuse the same cached resource extraction | `test_mod_catalog.py` | PASS |
| Hash identity invalidates changed files even at equal size/mtime; removal is respected | `test_mod_catalog.py` | PASS |
| Namespace/source collisions and language-only providers preserve ambiguity | `test_mod_catalog.py` | PASS |
| Malformed archives, oversized resources and deep invalid JSON do not execute/extract code | `test_mod_catalog.py` | PASS |
| Death arguments, indexed/sequential placeholders, literal percent and ambiguous boundaries are handled conservatively | `test_mod_deaths.py` | PASS |
| Config -> MOD lookup -> milestone/death -> mocked webhook works; raw chat stays unchanged | `test_mod_log_pipeline.py` | PASS |
| Legacy MOD `.lang` achievements work and disabled scanning creates no cache | `test_mod_log_pipeline.py` | PASS |
| Existing config, vanilla translation, Japanese chat and mention suppression remain compatible | Other listed regression targets | PASS, one platform skip |

`python -m compileall -q src` and `git diff --check` also passed. Independent read-only review accepted all corrective changes with no remaining actionable findings.

## Official Create resource check

Three files from [Creators-of-Create/Create](https://github.com/Creators-of-Create/Create), branch `mc1.21.1/dev`, were downloaded as inert verification input:

| Resource | Git blob SHA |
| --- | --- |
| `src/generated/resources/assets/create/lang/en_us.json` | `930893da30f1834cd1135fe073f84c3946d57476` |
| `src/main/resources/assets/create/lang/ja_jp.json` | `b644fa93ad7d2d73389c8f27f525976eb76b2df4` |
| `src/generated/resources/data/create/advancement/crushing_wheel.json` | `522002a3657b01d2f51feabdc6bd00cbd8faed46` |

They were packaged into a temporary resource-only test JAR under ignored `.uv-cache`, with no Java classes. Real extracted results were `Wheels of Destruction` -> `破壊ホイール` and `Alice was processed by Crushing Wheels` -> `Aliceは破砕ホイールによって加工された`. A subsequent load reported one cache hit and zero extraction misses. After the schema update, the old verification cache was rebuilt as intended before successful reuse.

This is verification of actual resource formats, not an assumption about the user's server version or a Minecraft runtime compatibility matrix. Nested JARs, translations supplied only by external resource packs and arbitrary code-built diagnostics remain outside scope. No Minecraft process, development server or live Discord notification was used. Async mocked integration tests ran outside the restricted Windows sandbox because its loopback socket-pair restriction prevents constructing Python's event loop.
