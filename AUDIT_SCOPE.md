# Audit scope

Written for an outside, independent security audit. Revision described:
`ed420fcbffa1ad83db78111deb836dd880ed891e` on `main`, 2026-10-28. Everything below is taken from
the repository's own files at that revision; items marked NOT_RUN were not executed while writing
this document.

## What this repository is

Omega Bridge is a compiler written in Omega that emits executable C (GNU C11, POSIX) and Python 3
from a checked, bounded subset of Omega (ABI v0). `src/native.om` generates C bindings so C, C++,
Python, Rust, Zig and Go can call machine code produced by the seeded Omega compiler (native call
ABI v1 for OM-1 units and ABI v2 for OM-2 units, `docs/NATIVE-ABI.md`). `tools/native
--freestanding` emits an AArch64 object for pure integer-scalar OM-1 units with no hosted runtime.
`tools/native --target x86linux` emits hosted x86-64 SysV Linux bindings from a separately pinned
x86 compiler; that path is EXERCISED under emulation only (`evidence/native-x86-62775d2a.json`)
and native x86-64 execution is NOT_RUN. `src/gpu_adapter.om` is an opt-in GPU adapter that
negotiates and admits artifacts; it opens no device and converts no host program. The default
target is Linux AArch64. There is no C or
Python input frontend. The Python under `tests/` and `conformance/` is test infrastructure and
does not ship. Status: local differential tests and caller demos; independent review required
before release.

## What to review, in priority order

1. `src/toc.om`. Lexer, type and name tables, typed expression nodes, and the C and Python
   emitters. Check that every runtime check in the source language (array bounds, signed
   overflow trap 1, division trap 2, shift trap 7, loop guards, 128-active-call limit) is emitted
   in both targets, that capacity exhaustion refuses with error 13, 14, 23 or 24 and writes no
   partial output, and that refused features (`docs/CAPABILITIES.md`) are refused.
2. `tools/bridge`. The shell entry point snapshots the input once, runs the pinned seed's
   whole-unit check, then generates from the same bytes, and refuses to run if
   `build/compiler.sha256` no longer matches. Check the snapshot cannot be swapped (time of check
   to time of use) and that output reaches stdout only after success.
3. `src/native.om` and `docs/NATIVE-ABI.md`. Generated C bindings for foreign callers: argument
   and length marshalling, aliasing of inputs and results, stack size requirement (eight MiB),
   BTI on C callers.
4. `src/gpu_adapter.om` and `docs/GPU-ADAPTER.md`. A `key=value` wire protocol on stdin/stdout.
   Check that unknown, duplicate or out-of-order keys are refused, that `REFUSE` is final, and
   that the adapter never returns a device pointer, address or handle.
5. `tools/bootstrap.sh`, `tools/build.sh`, `tools/build-gpu-adapter.sh`. Supply chain: fetch of
   the pinned Omega commit, seed growth, fixpoint check, and sha256 enforcement of `OMEGA_SEED`.
6. `tools/run-device-window.sh` and `conformance/`. Device-run wrapper (AGENTS.md: never resets
   the GPU, changes the driver or touches a serving process) and the Omega versus Modular MAX
   conformance test suite.
7. Test integrity: `tools/test.sh`, `tests/differential.py`, `tests/refusals.py`,
   `tests/attachments.py`, `tests/controls.py`, `tests/robustness.py`, `tests/native/run.sh`,
   `tests/native/v2/run.sh` (ABI v2 and freestanding), `tests/native/test_freestanding.py`,
   `tests/native/x86/run.sh` (x86linux, EMULATED), `tests/native/test_build_failures.sh`,
   `tests/gpu/test_gpu_adapter.py`.

`.github/workflows/ci.yml` (added by the audit-readiness change) replays the compiler from
source with `tools/bootstrap.sh` and runs `sh tools/test.sh` on a GitHub-hosted arm64 runner;
`tests/gpu` stays NOT_RUN there. A second job publishes an SPDX SBOM artifact. Every action is
pinned by commit sha and the token is read-only.

## Trust boundaries

- Untrusted input: the `.om` source given to `tools/bridge` (below 65,536 bytes), requests on the
  GPU adapter's stdin, and arguments passed by foreign callers to generated bindings.
- Trusted: the pinned seed compiler (sha256 enforced) and the Omega source commit it grows from;
  the C compiler and Python interpreter that consume generated output.
- The README tells users to inspect generated output before linking or importing it. Conversion
  writes isolated temporary build files and never installs or replaces an application.
- Isolated: the GPU adapter has no daemon, no environment hook, no network, no telemetry and no
  install path.

## Threat model summary

- Assets: the safety properties of the Omega source (bounds, overflow, loop guards) carried into
  generated C and Python; the integrity of the compiler chain; callers' memory.
- Attackers considered: a hostile or malformed `.om` input; a hostile GPU adapter request; a
  substituted seed compiler; byte-prefix truncations and capacity-exhausting sources (225 cases in
  `tests/robustness.py` per `evidence/README.md`).
- Defended: whole-unit validation before either backend; refusal instead of partial output;
  pinned compiler digests; checked bounds in generated code; differential testing of native vs C
  (UBSan) vs Python, with AddressSanitizer on bounds mutants.
- Not defended / explicitly out of scope (from the repository's own text): no independent
  checker2 receipt, independent compiler audit, diverse double compilation, cross-architecture
  verification, installer or public-release qualification; the bootstrap fixpoint is not DDC;
  native and generated stack exhaustion thresholds differ; Python uses its host heap; no speedup
  claim; GPU hardware execution NOT_RUN.

## Build from source at a pin

Needs Linux AArch64, `git`, `sh`, `file`, `sha256sum`, `gcc` and `python3`. The bootstrap uses no
C compiler, assembler or linker.

- Omega source commit (`docs/PROVENANCE.md`): `29b12760f4c962606411d6bf25032aedef063301`.
- Bootstrap seed `build/bootstrap/omc` sha256:
  `191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9`.
- Seeded compiler for native call tests (`OMEGA_NATIVE_OMC`, omega-mv `seed/out/omc`) sha256:
  `734f0a39319fbfa930bcc62cb30dbf06d47d78e126372b74f5baf478e6126b61`.

```sh
sh tools/bootstrap.sh     # ends with: bootstrap fixpoint RC=0
tools/build.sh            # builds build/bridge from src/toc.om
```

`OMEGA_SOURCE` may point at an existing Omega checkout (read only); otherwise the bootstrap needs
network access to the upstream repository. On a shared build host the README prefixes commands
with `quiet-build`; without it, run the scripts directly.

## Run every test

```sh
tools/test.sh
python3 tests/attachments.py
OMEGA_NATIVE_OMC=/path/to/omega-mv/seed/out/omc sh tests/native/run.sh
OMEGA_NATIVE_OMC=/path/to/omega-mv/seed/out/omc sh tests/native/v2/run.sh
OMEGA_NATIVE_X86_OMC=/path/to/x86/omc sh tests/native/x86/run.sh
sh tests/native/test_build_failures.sh
OMEGA_SEED=build/bootstrap/omc sh tools/build-gpu-adapter.sh
python3 tests/gpu/test_gpu_adapter.py
MAXPY=/path/to/venv/bin/python conformance/run.sh
conformance/run.sh --device
tools/run-device-window.sh --ledger <ID>
```

- `tools/test.sh`: build plus differential, refusals, attachments, controls and robustness; ends
  with `ALL SUITES RC=0`. `evidence/README.md` records 397 cases, 0 failures. NOT_RUN here.
- `tests/native/run.sh`: prints `NATIVE-CALL PASS` only after all seven required callers build
  and run; missing toolchains print NOT_RUN and exit nonzero. NOT_RUN here.
- `tests/native/v2/run.sh`: ABI v2 (OM-2) bindings and the `--freestanding` object. NOT_RUN here.
- `tests/native/x86/run.sh`: x86linux bindings under a QEMU user-mode oracle (`QEMU_X86_64`);
  EMULATED only, physical x86-64 NOT_RUN. NOT_RUN here.
- `tests/gpu/test_gpu_adapter.py`: 47 checks, no device. NOT_RUN here.
- `conformance/run.sh` needs a Modular MAX 26.7 venv (`modular==26.7.0`); CPU only without
  `--device`. NOT_RUN here.
- `conformance/run.sh --device` and `tools/run-device-window.sh` need the NVIDIA GB10 on a DGX
  Spark inside an authorized window plus a sibling CUDApp build. NOT_RUN on a plain host.

## Known limitations and NOT_RUN

- Capacity limits: 32 functions, four parameters, eight globals, eight-character names, 262,144
  bytes of output, 32 KiB local arrays per function.
- Text constants, floats, heap, concurrency, external calls and other targets are refused.
- Native differential tests share the seed's checker; they are not independent frontends
  (`docs/PROVENANCE.md`).
- Intermediate red logs in `evidence/` are development traces; the final qualification is the
  final manifest plus final gate output.
- GPU hardware load and execution: NOT_RUN (`docs/GPU-SUPPORT-MATRIX.md`).

## Dependencies and provenance

- No lockfile. No compiler binary is committed; the bootstrap rebuilds it from source.
- `src/toc.om` was recovered from omega `seed/toc/toc.om` at the pinned commit; original digest in
  `docs/RECOVERY.json`. Inherited fixtures come from omega `seed/rung4/tests/` at the same commit.
- Test oracles: GCC with UBSan and ASan, Python 3, and Modular MAX for conformance. They do not
  ship.
- External services: GitHub fetch of the pinned Omega commit at bootstrap; Python package index
  for the MAX venv, if built.

## Evidence

Raw logs and manifests live in `evidence/` (numbered red and green logs, `manifest.json`,
`differential-results.json`, `control-results.json`, `files.sha256`, `native-call-v1/`,
`MAX-INTEROP/`). AGENTS.md: keep the failing log beside the passing one, and never rewrite an
existing evidence log. Cross-repository receipts, where filed, belong under
`aien-dev/aien-receipts` `omega-bridge/<sha>/`; whether any exist is unknown from the repository.
Receipts are append-only and never edited.
