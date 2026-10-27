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
