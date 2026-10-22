# L529 path safety qualification

Scope: build-output clobber and uninstall parent traversal only. No imported
source, provenance lock, compiler, converter or math changes. Linux AArch64 host;
POSIX shell remains disclosed host glue. No runtime hooks or system retirement.

`tests/native/path-safety.mjs` drives actual installation and uninstallation in
disposable /tmp source copies with isolated HOME and prefixes. `red.json` and
`red.log` record the original 53708d4 behavior: status/stdout/stderr and victim
SHA-256 before/after for every case. Baseline: 5 pass, 40 fail. The primary seed
case and other redirections overwrite the victim. Rename-published final outputs
can preserve victim bytes yet still fail the new conservative refusal policy.
Directory-link tests also inspect outside directory contents. No fake compiler
failure is used. `green.json` and `green.log`: the expanded 57 checks pass after fixes.
`red-expanded.json`/`.log` record the same 57 checks against a fresh 53708d4
source export (5 pass, 52 fail, exit 1). The expansion covers direct builders,
the installed uninstaller entry point, link/.. normalization and a deterministic
parent change at the lock-acquisition seam. No fixture setup errors occurred.

Ranked resolutions:
1. Important: complete shared build tree preflight at every default builder entry
   refuses symlinks, multiply linked files and special files before output writes.
2. Minor reviewed direct-entry uninstall: named ancestor checks before realpath
   and before/after the lock refuse relocated parents. In the original lib-link
   fixture, direct uninstall deletes outside files while both actual aliases
   already refuse. Additional bin/root/ancestor fixtures also reproduced through
   actual aliases; their invocation parents are now checked too.

Original manifests remain fixed deletion lists, never removal instructions.
The guards address preexisting paths on a single-user host, not malicious
concurrent mutations, crash recovery or tamper-proof manifests. No ownership
claims or permission changes to unrelated files. Full native gate and committed
source-export replay receipts will be added before READY.

Final source qualification: 31c5b9b49bc863c4805a2571d4be8b22e9c4cb65.
`qualification.json` records exact commands, all gate summaries and log hashes.
`quiet-build tools/test-native.sh`: exit 0, all original converter/math gates,
69 command checks, 7 parent regressions, 18 provenance checks, 57 path checks.
`quiet-build node tests/native/replay-path-safety.mjs`: exit 0, a fresh committed
source export rebuilt all three byte-identical binaries, installed from an
unrelated cwd, passed 57 path controls and uninstalled with no isolated HOME state.
`replay-build.trace` plus the original gate's runtime traces show no first-party
C/Rust build/runtime fallback. readelf checks find no INTERP/NEEDED closure.
`tools/verify-sources.sh`: exit 0; diff of seed/, src/ and provenance/ from baseline
is empty. Final binary hashes are in binaries.sha256 and replay.json.

The inherited evidence/native-commands/binaries.sha256 had a stale pre-review
math hash although the source pins and built math were correct. It is refreshed
from the qualified binaries here; no math implementation was changed.

L529 is READY for parent verification. L528 stays OPEN and L521 acceptance stays
HOLD until the parent independently verifies this branch. No PR or merge made.
