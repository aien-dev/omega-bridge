# Placement primitive evidence

This is HOST_REFERENCE_ONLY evidence, not native seed, GGML integration, GPU,
model or hardware qualification. See docs/GGML-PLACEMENT.md for the trust boundary.

Recorded on x86_64 Linux with cc (Debian 14.2.0-19) 14.2.0. Reference source is
Omega commit 697539a577ee7594ba12d905062f2e09cb9cc77c, materialized separately from
its exact Git archive. tests/ggml/reference-source.sha256 pins every required
reference C/header input. No downloaded executable, package, emulator, seed or
hardware command was used. Shell/C code here is test coordination/reference
invocation only; production policy and assertions are handwritten .om.

Commands (from repository root):

- `OMEGA_REFERENCE_SOURCE=<pinned source> sh tests/ggml/run-reference.sh`
  - Node RED: both production units were accepting stubs (`ret 0`), result=2,
    exit 1: forbidden CPU internal GET_ROWS was admitted.
  - Snapshot RED: real node policy plus accepting snapshot stub, result=41,
    exit 1: empty snapshot was admitted.
  - GREEN: real units and the same assertions, trap=0 result=0, exit 0.
- `OMEGA_REFERENCE_SOURCE=<pinned source> sh tests/ggml/run-controls.sh`
  - Final gate includes 2/2 source-provenance controls before compilation, then
    host assertions pass; 8/8 mutants caught by exact expected assertion
    IDs with trap=0 and exit 1, not arbitrary process/compiler failures.
- `OMEGA_REFERENCE_SOURCE=<copied source with one comment appended to osc_interp.c> sh tests/ggml/run-reference.sh`
  - Source-pin control: exit 1 before compilation; exact changed file FAILED.
    The modified copy is a controlled test input, not a new trusted reference.
- `sh tests/ggml/run-native.sh`
  - Exit 77, NOT_RUN: this host is not Linux AArch64. No native fallback.
- `sh tools/test.sh`
  - Exit 1 before original suites: build/bootstrap/omc missing, fingerprint
    mismatch. Original aggregate suite is NOT_RUN, not a policy regression PASS.
- `sh tests/native/run.sh`
  - Exit 2 before execution: required OMEGA_NATIVE_OMC absent. Inherited native
    ABI qualification is NOT_RUN, not rerun or inherited from author evidence.
- `sh -n tests/ggml/*.sh` and `git diff --check`: exit 0.

The original untyped `allowed = false` spelling was initially refused by the
bounded reference frontend (line 5, type unknown); `bool false` fixes that
reference parsing issue. It is not counted as a semantic test failure or PASS.

Raw output logs and identity.txt record the actual stages. files.sha256 binds
this increment's source/docs/test inputs and evidence; it excludes itself.

Independent parent review remains pending. No push, PR, merge, installation,
service modification or issue closure is claimed. Publication goes through the
existing desk, not directly from this implementation task.

## Independent review correction

The original 30-entry reference manifest omitted transitive
src/compiler/model/osc_model.h (included by osc_check.h). The source bytes
matched the pinned repository; this was incomplete reusable gate coverage,
not evidence of tampering. Before the fix, appending a harmless comment to
that header still allowed the reference suite to PASS. A new regression
control also reached the forbidden compiler marker (exit 99), so arbitrary
build failure was not mistaken for a caught tampered-header input.

The final 31-entry manifest pins that header at SHA-256
4b59786ec57a7cd9ffa6d99845158d4593ed07c95cdc6be04e6b57143d7920c8.
Dependency-only cc -MM output confirms 31/31 local C/header inputs, no missing
or extra files. run-controls.sh now includes run-source-controls.sh: tampered
interpreter source AND tampered transitive header each must produce the exact
failed-file hash diagnostic, exit 1 and no compiler invocation. The final
host-reference.log records 2/2 provenance controls plus the unchanged 59 .om
assertions and 8/8 policy mutants. Historical red logs remain separate.
No production .om semantics changed in this correction.
