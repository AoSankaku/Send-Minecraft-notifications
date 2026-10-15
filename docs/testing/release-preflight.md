# Release checks before tagging

## Investigated failures

| Run | Failure | Existing correction |
| --- | --- | --- |
| `38621397129` (beta0) | Windows standalone first run could not encode Japanese text with the console code page | `cf422f8` configures UTF-8 output and covers a Western console encoding |
| `38691010378` (beta1) | Windows smoke check compared a reported path as a raw string | `0ff73d1` compares filesystem identity |
| `38763058845` (beta2) | Both platform builds succeeded; the later Linux publishing test used an incomplete prerelease version fixture | `defa8cf` fixes the fixture; all 13 Linux publishing tests passed |

The remaining workflow gap was that ordinary product changes did not run Windows packaging/startup checks until a release tag was pushed. Publishing tests also ran after both expensive builds completed.

## Change

The existing release workflow now runs for relevant main pushes and pull requests, so the same Windows/Linux application tests, public-mode packaging and frozen-binary smoke checks execute before tagging. Changes limited to other documentation avoid packaging runs. Linux publishing tests run first and gate both platform builds. The separate publishing-only workflow is consolidated into this workflow.

The publication job retains its existing push-plus-tag condition and is the only job with repository write permission. Branch, pull-request and manual runs build artifacts without publication. The optional manual `release_version` input can exercise a planned public tag. Superseded branch/PR runs are canceled; tag builds and the serialized publication queue remain preserved.

`AGENTS.md` records the release procedure: prepare the candidate commit, verify a successful run for its exact SHA, then create/push the release tag. This prevents using the public release attempt as the initial Windows packaging check.

## Verification

Independent review found no concrete issues in triggers, tag behavior, permissions or publication conditions. Actionlint 1.7.12 validates the modified workflow with one narrowly scoped exclusion for its unsupported `concurrency.queue` key. The same warning occurs on the unchanged baseline. GitHub documents `queue: max` and the existing successful release runs use it; its behavior was preserved.

References: [workflow trigger/path rules](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onpushpull_requestpull_request_targetpathspaths-ignore), [concurrency queue](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#concurrency).

Main-branch push run [38765182746](https://github.com/AoSankaku/Send-Minecraft-notifications/actions/runs/38765182746) completed successfully for exact implementation commit `4844b8465ffa4102ccf6351504c92c09347d317b`. Its publishing check passed all 13 cases before the platform builds. Windows and Linux each passed 545 application tests, built public-mode binaries and passed the standalone smoke check (including UTF-8 initialization and legacy settings migration). The publication job was skipped as intended. No new release was created; the published beta2 release and its timestamp remained unchanged.

Only this verification record changed after that run, so no repeated packaging run was required.
