# Recovery archive, 2026-10-23

This branch is a preservation index, not a product implementation or merge proposal.
Original committed work and unreviewed working/staged/conflict snapshots are reachable
through this commit's parent history. The index tree deliberately contains only recovery
records. No active branch, original staging area, service or working file was replaced.

## Contents

- 0 local branch references absent from the published heads/PR histories inspected.
- 3 working-folder snapshots, 0 separate staged snapshots, 0 unresolved conflict alternatives.
- 8 excluded untracked generated/model/nested-repository entries; see working-snapshots.json.
- 3 previously unreferenced commits, including the new recovery snapshots.
- Published main at capture: 614f4ba56487ad420f43980b12e48b66768d6d21.

The capture covered discovered workspace clones and their registered worktrees for
Sovereign Core, Omega and CUDApp, plus their existing omega-bridge migration repository.
Ignored files, arbitrary reflog-only objects and unrelated repositories were not swept.
Six missing registered worktree directories were recorded in the cross-repository summary.
Known compiler/device owners retain implementation ownership. No test, quality, hardware,
license-transition or release approval is implied by publication. Historical Rust/C/.osc
is retained here as recovery history, not adopted as the final first-party implementation.

## Recover saved work

Use the commit links below, or fetch this branch and create a new local branch at the
desired commit. Do not reset an active working folder. Working snapshots capture eligible
on-disk files; staged and conflict snapshots preserve additional index alternatives.
Generated/model artifacts and nested repositories are excluded explicitly.

### Previously unpublished branch tips

| Original local branch | Saved commit |
|---|---|

### Unfinished working-folder snapshots

| Source folder | Saved commit |
|---|---|
| omega-command-bootstrap | [8ad201f47c6a](https://github.com/aien-dev/omega-bridge/commit/8ad201f47c6ad874ca057a6f8647efe5e5d4d887) |
| omega-live-opt-L739 | [669cdd957d9a](https://github.com/aien-dev/omega-bridge/commit/669cdd957d9a7ed9d44b286b78a510521722ed6c) |
| omega-renda8b-L720 | [806ef588f154](https://github.com/aien-dev/omega-bridge/commit/806ef588f154e3f2f623db71989fca3718edcc74) |

## Verification and limits

Unpublished blobs were read and checked for credential filenames, common token/private-key
patterns and oversized objects. Two CUDApp audit-selftest blobs contain intentional fake
secret negative controls; those exact blobs were reviewed. Pattern screening is not a
formal security audit. Original source tests were not rerun for recovery publication.
Working files selected for capture were reread and compared before creating snapshots.
Root publication and reachability are verified separately after upload.
