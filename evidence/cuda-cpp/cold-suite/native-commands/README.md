# L514 qualification

The first missing-interface RED is in red.log, captured before implementation.
removal-red.log records the additional changed-permission regression before its
fix. tools/test-native.sh is the combined source-only build/test entry point.
Tests use isolated HOME/prefix under /tmp; no actual account installation occurs.

| Gate | Executed result |
|---|---|
| Original converter suites | 397 checks (113 differential, 50 refusal, 2 callers, 7 controls, 225 robustness), all pass |
| Imported math golden | 42/42 |
| Imported math exact oracle | 1048/1048, includes 9 saved Wolfram fixtures |
| Math module | 23/23 |
| Math wrong-rule controls | 13 valid compiled mutants, 13 detected; 546 executed comparisons |
| Math stream transport/reset | 6/6 |
| Math malformed/recovery | 1200 replies: 600 refusals, 600 successful recoveries |
| Installed commands | 69/69 |
| Source/provenance/build controls | 18/18 |
| Pinned owner binary equivalence | Same bytes/hash; 42 request outputs compared |
| Clean checkout replay | PASS: all 3 binary hashes and both conversion outputs match; 69 command and 18 provenance checks repeated |

full.log records the combined gate result. commands.json and provenance.json name
each integration check. Converter and math logs retain actual suite counts. Math
checks.json and mutant logs under ../math-native record compilation success,
nonempty valid ELF and executed output mismatches; failed compilation never counts
as a caught math mutant. The dispatch negative control redirects the installed
math invocation to the already built native converter, updates the local integrity
manifest, and checks that the expected successful derivative assertion fails.

The source controls include dirty math/converter/compiler, malformed and wrong
pins, unsafe import paths, manifest/lock corruption, source overlays/symlinks,
missing offline pins, dirty source cache, unsupported host, empty ELF and dynamic
host ELF. Failed pin installation publishes no prefix. An offline import from the
pinned original clean Git cache was executed; import.log is empty on success.

binaries.sha256 and bootstrap-binaries.sha256 record the executable chain.
pinned-equivalence.json records comparison with the existing owner's artifact.
fib-output.sha256 freezes both target output hashes. tools.txt identifies host
and test tools. Build, math and conversion exec traces show native subprocesses
and shell utilities, with no first-party C/Rust launcher/toolchain or fallback.
GCC and Python execute emitted targets only in converter tests. Node/Python test
infrastructure is excluded from the installed command path. Traces are sampled
execution evidence, not exhaustive proof of all possible host behavior.

Commands executed on Spark under quiet-build:

```sh
tools/bootstrap.sh --offline
tools/build-native.sh
tools/test.sh
node seed/math/gate.mjs
node seed/math/oracle.mjs
node seed/math/checks.mjs
node seed/math/robustness.mjs
node tests/native/commands.mjs
node tests/native/provenance.mjs
tools/test-native.sh
```

Source pins, lock verification and exact-byte import mapping are in
../../provenance and ../../docs/NATIVE-PROVENANCE.md. The independent clean clone and full suite passed at the implementation commit
recorded in replay.json. Both PATH aliases were invoked from an unrelated directory
and the isolated installation was then removed. shared-seed.log records exact
byte equality of all consumed seed sources at the seed and math commits. No benchmark speed claim,
real language attachment, external service replacement, PR/merge, visibility change
or GPU/model/server access is part of this qualification. System retirements: 0.
