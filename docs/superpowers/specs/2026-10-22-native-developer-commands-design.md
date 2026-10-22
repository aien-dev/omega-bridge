# Native developer commands

Goal: make the existing seeded Omega compiler directly usable through `om`, with
`omg` only an alias. This is a coordinator-selected next step under the user's
instruction to continue, not a change to the language or a production cutover.

## Interfaces

- `om check [--] input.om`: snapshot a readable regular source file, compile with
  the installed pinned native compiler, require a nonempty static AArch64 EXEC
  ELF, discard it and return0 with no stdout. Never execute source.
- `om build [--] input.om -o output`: same native compilation; atomically publish
  to the explicit destination with mode700. Never execute source. Successful
  replacement of a regular file is intentional, like existing convert -o;
  refuse symlinks/nonregular destinations and preserve old output on failure.
  Refuse an output naming the source's own inode, including aliases.
- `om run [--] input.om`: same native compilation and ELF qualification, then run
  that executable, forwarding inherited stdin/stdout/stderr and program status.
  Source compilation must not consume the program's stdin. No program argv yet;
  extra arguments return64. This is explicit code execution, not a sandbox.

Both names must have identical behavior and implementation/config/state. The
existing default names, math/conversion protocols, source pins and output safety
must not change. No compiler features, new IR dialect, C/Rust launcher, generated
C build, Python interpreter fallback, network download or runtime hooks.

The existing verifier shell helper/readelf is disclosed host metadata glue. Ship
it as an owned, hash-checked executable in the payload, with fixed-list uninstall.
Keep imported compiler/math/converter bytes and their provenance lock unchanged.

Existing statuses apply:64usage,65compile/ELFintegrity/refusal,66badinput,
73destination/collision,74I/O. A successfully launched program's status is not
normalized to65. All temporary artifacts are private and cleaned after ordinary
completion, failure and supported shell signal handling. Host-native inherited
signal behavior remains; no crash-durability or hostile-race claim.

Acceptance: fail-first installed regressions for both names, observable native
program output and exit behavior, program stdin, malformed source, bad ELF,
no-execution checks, path quoting, atomic preservation/permissions, alias identity,
modified-helper integrity, no foreign-toolchain execution trace and no temporary
leaks. Existing full suite/path safety must stay green. Rebuild from committed
source only, compare native identities, publish receipts and obtain one independent
whole-feature review before desk acceptance. Tests use isolated HOME/prefix only.
