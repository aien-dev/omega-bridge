# Seal 2026-10-27

`files.sha256` in this directory is a new seal over the same 183 paths as the
original seal `evidence/files.sha256` (commit `77376b1`, 2026-10-22, bound to
the L483 qualification of source commit `760a9d55`; sha256 of that list file
`6d3e4903e9a1ffe92023297a910da641bd7cbe6bb3d04cb07a3cf0dcf6d75d2b`). The
original seal is kept unchanged as history; it no longer matches the tree.

Check: `sha256sum --check --strict evidence/seal-2026-10-27/files.sha256`.
CI (`.github/workflows/ci.yml`) checks the newest `evidence/seal-*/files.sha256`
on every pull request, so an edit to a sealed file now fails CI until a new
seal directory with its own note is added.

## Why a new seal

An outside review (2026-10-27) found that 7 sealed files no longer matched
`evidence/files.sha256`. `sha256sum --check evidence/files.sha256` on `main`
`358c5051` reported exactly these 7 as FAILED and the other 176 as OK:

| File | Changed by | What changed |
|---|---|---|
| `.gitignore` | `cd96034` (2026-10-23, GPU adapter/MAX harness, #3 #4 #5 #7) | added `conformance/build/` |
| `LICENSE` | `3df5132` (2026-10-23, relicense) | AGPL-3.0 text replaced by Apache-2.0 WITH LLVM-exception |
| `README.md` | `cd96034`, `3df5132`, and this change | GPU adapter and licence paragraphs; this change labels the GPU adapter accept/refuse only |
| `docs/DESIGN.md` | `cd96034`, `3df5132` | GPU adapter boundary text; licence line |
| `docs/PROVENANCE.md` | `3df5132` | licence line |
| `docs/RECOVERY.json` | `3df5132` | `license` field value |
| `src/toc.om` | `3df5132` | first line only: the `note` comment's licence name. No other byte of the compiler source changed. |

None of these edits re-sealed the list, which is the defect this note fixes.

## What this seal does and does not say

- It records the bytes of the 183 paths at the commit that adds this
  directory. It is not a new qualification by itself.
- The L483 qualification logs (`evidence/20-final-suite.log` and others) were
  produced on source `760a9d55`, before the edits above. They are unchanged.
- Files added after 2026-10-22 (for example `src/native.om`,
  `src/gpu_adapter.om`, `conformance/`) are outside this seal's scope, as they
  were outside the original's.
- Open, not changed here: `docs/RECOVERY.json` now reads "Apache-2.0 WITH
  LLVM-exception, preserved from source; no relicensing", while the recovered
  source was AGPL-3.0 and `3df5132` is a relicensing. Licence wording changes
  need Drake, so this is left as found and reported.

## Evidence for this seal (run 2026-10-27 on the Spark, aarch64; builds on cores 10-14)

Logs are in this directory; `SHA256SUMS` covers them. Log 01 ran on a worktree
of `main` `358c5051`; logs 02-07 ran on worktrees of `11cbe8ac` (the commit
that adds `files.sha256`). Private paths in the logs are shortened to `~`.

| Log | What it shows | Result |
|---|---|---|
| `01-original-seal-on-main-red.log` | original `evidence/files.sha256` on `main` `358c5051` | RED as expected: 7 FAILED (the table above), 176 OK, RC=1 |
| `02-new-seal-green.log` | new seal on `11cbe8ac` | 183/183 OK, RC=0 |
| `03-negative-control-red.log` | one byte of `src/toc.om` changed in a scratch copy, new seal checked | RED: `src/toc.om: FAILED`, RC=1 |
| `04-bootstrap-seed-191b776e.log` | `tools/bootstrap.sh` from Omega source `29b12760` | fixpoint RC=0, seed sha256 `191b776e…` |
| `05-bridge-suites.log` | `tools/test.sh` with that seed | `ALL SUITES RC=0` |
| `06-native-pin-734f0a39.log` | `tests/native/run.sh` with the pinned native compiler `734f0a39` | C, C-BTI, C++, Python, Rust callers and the add→sub mutant PASS; Zig and Go NOT_RUN (toolchains not installed on this host), so the run reports `NATIVE-CALL NOT_RUN`, RC=1. Not a PASS. |
| `07-omega-mv-main-2c824805-refused.log` | omega-mv `main` `e5b32567` rebuilt from the seed (`sh seed/omega-from-seed.sh`; lines 3-5 are the tail of its output), giving `2c824805…`; then given to both bridge pins | both refuse: `tests/native/run.sh` RC=1 (`FAIL omc sha256`), `tools/build.sh` RC=1 (`seed fingerprint mismatch`) |

CI on this PR (`.github/workflows/ci.yml`, ubuntu-24.04-arm) runs the seal
check, the bootstrap, the bridge suites and the GPU adapter tests; the run for
`11cbe8ac` passed (actions run 40434390102).

## Three compiler digests

The bridge uses two compilers, and neither is the one omega-mv `main` ships now:

| sha256 | Where it comes from | Used by in this repo |
|---|---|---|
| `191b776e…` | bootstrap from Omega source `29b12760` (`tools/bootstrap.sh`) | `tools/build.sh`, `tools/bridge`, `tools/build-gpu-adapter.sh`, CI |
| `734f0a39…` | omega-mv `seed/out/omc` from PR #696 (`seed/omc-unified` `45e7519`) | `tests/native/run.sh` (`OMEGA_NATIVE_OMC`); not in CI |
| `2c824805…` | omega-mv `main` today (`evidence/BATCH-2c824805` there) | nothing; both pins refuse it (log 07) |

This seal does not move either pin. Moving the bridge to `2c824805` means
re-running every suite on it and re-pinning in one change; that is separate
work, not part of repairing the seal.
