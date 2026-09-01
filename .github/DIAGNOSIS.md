# CI failure diagnosis (run 33464282392)

Root cause: the restore step in upstream `Eeems/wheels` references `.github#<PR>` for several packages (e.g. `.github#115, #122, #136, #142, #386, #387, #393, #467`). The error `Failed to restore: <package>: .github#...` means the CI restore tool cannot resolve those `.github` subpaths (the restore action expects `.github/{build,mirror,...}` directories that exist upstream but may be missing/empty locally).

Fix scope here: add an explicit `.github/DIAGNOSIS.md` documenting the failure and pin the restore ref so a missing directory is reported clearly. A full fix requires the upstream author to either:

1. Vendor `.github/build/` and `.github/mirror/` so submodule-style refs resolve, or
2. Replace `.github#<PR>` references with pinned commits/sha, or
3. Add an `actions/checkout` step that clones the referenced PR head before restore.

For a local-only run on this fork, the build job is run as-is and the failure is the same as upstream; PR opened to share diagnosis and propose (1)/(2)/(3).
