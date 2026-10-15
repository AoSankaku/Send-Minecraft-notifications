# Release checks

For a release request, prepare and commit the version and release notes before tagging. Push only when the user has authorized pushing.

Before creating or pushing the release tag, confirm that the `Build and release` workflow succeeded for the exact candidate commit. The `Check release publishing`, `Build (windows x64)` and `Build (linux x64)` jobs must all pass, including standalone startup checks. A successful run for a different commit does not establish release readiness.

Relevant main pushes and pull requests run this workflow automatically. If the candidate has no successful run, use `workflow_dispatch` on its branch, optionally setting `release_version` to the planned tag, and confirm the resulting `headSha`. Manual and branch runs do not publish releases. Do not use the first tag-triggered run as the initial packaging test.

Only push the new tag after these checks pass. Preserve existing published tags and assets.
