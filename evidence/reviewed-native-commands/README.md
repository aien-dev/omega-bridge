# Reviewed native command integration (L521)

This branch supersedes the initial `integration/native-commands` milestone at
`9355ebe384296d3069fe1a5515504c9dc9e06671`. `om` is the primary command and `omg`
is an alias to the identical installed implementation. No second command engine
or state store is introduced.

## Exact correction

Imported byte-for-byte math source from
`508ddd7e02c303d0e2182721f9501c7a540c758f`, whose parent includes the original
`78477217b6803ad5d2b14caee40b65c7509aa40c` milestone. The math change accepts the
already documented CR command separator. The reference generator now checks all
four operand-sign combinations, and its extra whitespace/sign fixtures are in
the immutable import whitelist. The seed compiler and converter pins are unchanged.

`installed-red.log` records the real source-only install before this import:
seven checks executed, three passed and four failed on CR handling in `om` and
its alias. Alias identity, identical refusal status and isolated uninstall already
passed. `tests/native/review-regression.mjs` is the executable regression; the
combined `tools/test-native.sh` now includes it and both upstream new fixtures.
Negative provenance controls now mutate the current pin rather than a hardcoded
substring of the superseded pin, and assert that the mutation actually occurred.

## Independent retirement-policy check

`policy-parent/` holds the parent run on the frozen correction, not an author
summary. The new receipt tests passed on the fixed assessor, failed on the
original `12251e3403d42931ada27dc1c54b3b610954be5d` assessor for the exact
isolated-to-production relabeling counterexample, and passed again after restoring
the fixed source. The actual manifest was checked as `PARTIAL`, with no errors
and **zero** verified production retirements. Synthetic production receipts are
only temporary test fixtures, never evidence of a real cutover.

## Qualification status

Parent test qualification completed at source commit
`73872d83af405e0888468ee39e27a7225ab72d03`, after the corrected upstream full math
gate returned zero. `parent-full.log` and `parent-full.exit` record the integrated
suite returning zero. The converter suites returned RC=0; the math reference
suite executed 1,048/1,048 passing cases including nine Wolfram fixtures. Its
400 rational cases exercised each sign pair 100 times. All 57 explicit sign
fixtures, 28 whitespace probes, 69 installed command checks, seven new installed
regressions and 18 provenance checks passed. Compiled-mutant and malformed/recovery
suites are retained in the full component logs under `../native-commands/`.

A second source-only export of the exact committed tree, without build artifacts,
rebuilt the compiler, converter and math to byte-identical hashes. The seven
installed regressions passed again from an unrelated working directory with
isolated HOME/prefix, followed by uninstall. `replay/` contains those build and
installed-test logs. `binaries.sha256` identifies all three native executables.

Independent whole-command code review L528 remains pending; green tests are not
merge approval. The earlier milestone's logs remain historical evidence, not
substitutes for these new qualification logs.

This is AArch64 Linux software. Disclosed POSIX shell/Linux utilities orchestrate
the seed-born native computation; no first-party C/Rust launcher is substituted.
No actual user-account enrollment, runtime hooks, live service changes, GPU work,
full-system retirement or speed improvement is claimed.
