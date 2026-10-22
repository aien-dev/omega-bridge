# Native developer command evidence (L543)

Parent-authored follow-on to qualified795009f. Same om implementation/omg alias;
no imported seed/math/converter source or provenance-lock changes.

## Red/green

- `baseline.log`: entire previous tools/test-native.sh passed before changes.
- `red-final.{json,log,exit}`: corrected installed baseline36 checks,5pass31fail,
  exit1 before production changes. New command successes fail as unknown-command64.
  The literal filename- converter regression separately demonstrates old code
  compiling caller stdin rather than the named file.
- `red-expanded.*` is an earlier test-construction attempt: its conversion fixture
  used native text syntax outside the bridge subset. It is retained as history,
  not treated as valid proof for that conversion case. `red-final` uses the already
  qualified fib conversion fixture and isolates the real stdin/source confusion.
- `green.{json,log,exit}`: first36 installed checks pass after implementation.
- `source-collision-red.*`: an additional same-source/output case fails correctly,
 36pass1fail, before the inode guard. Synthetic source bytes were actually replaced.
- `green-final.{json,log}`: all37 installed checks pass with source preservation.
- `full.{log,exit}`: complete extended tools/test-native.sh returned0, including
  original converter/math, command69+7, provenance18 and filesystem57 checks,
  plus the new37developer checks. No failure or fixture was skipped to pass.

The tests install into isolated HOME/prefix, invoke both aliases from an unrelated
working directory and uninstall. Real native programs produce NATIVE output with
status23; another preserves binary stdin across multiple reads. check/build remain
silent, so accidentally executing source fails their assertions. Bad-ELF controls
replace the compiler with an existing valid native math executable; a nonempty
non-ELF response cannot be accepted or published as a program. This is not a
compiler-error-counted-as-caught control. run-exec.trace checks actual child execs
for absence of foreign compiler/interpreter fallback.

## Committed source-only replay

The parent exported exact committed source51bb72a into a fresh directory with no
build artifacts, reconstructed the seed/compiler and rebuilt native compiler,
converter and math. All3 binary hashes matched the separately built artifacts.
The full37 installed developer regressions passed again from an unrelated working
directory with isolated HOME/prefix, including raw program input, actual native
execution/status, alias behavior, file safety and uninstall. `replay/` contains
those logs, the machine-readable37/37/0 result and exit0 receipt.

Independent whole-feature review L548 remains pending at this checkpoint; test
success is not merge approval. Host shell/GNU readelf orchestration is disclosed,
run is not a sandbox, no program argv/process-control extension is claimed, and
production retirement remains0.
