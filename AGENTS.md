# Omega Bridge (an Omega-written compiler from a checked Omega subset to C and Python, plus a native call boundary and an accept/refuse-only GPU adapter)

> `src/toc.om` is an Omega program, built by the pinned seeded Omega compiler, that emits executable C and Python from a checked, bounded Omega subset (ABI v0). `src/native.om` generates a C binding so C, C++, Python, Rust, Zig and Go call the machine code the seeded compiler produced (native call ABI v1). `src/gpu_adapter.om`, the "GPU adapter", is accept/refuse only: it reads a request on stdin and writes `ACCEPT` or `REFUSE` on stdout. It has no GPU contact: it opens no device, loads nothing and runs nothing on a GPU, and it converts no host program. Linux AArch64 only. Independent review remains required before release; no universal conversion or speedup is claimed.

Shared rules: read https://www.aienos.com/agents/RULES.md first. This file adds what is specific to this repository; where the two differ, this file wins here.

## Scope

- Applies to the whole repository.
- `src/`: all conversion logic and both runtime emitters (`toc.om`), the native binding generator (`native.om`) and the GPU adapter (`gpu_adapter.om`). These are Omega source; keep them Omega.
- `tools/`: shell entry points (`bootstrap.sh`, `build.sh`, `test.sh`, `bridge`, `build-gpu-adapter.sh`, `run-device-window.sh`).
- `tests/`: Python test harness (infrastructure only), fixtures, refusal cases, native callers in six languages, GPU adapter protocol tests.
- `conformance/`: separate-process Omega versus Modular MAX harness. `evidence/`: raw logs and result manifests.
- No compiler binary is stored here. Python/C input conversion is not implemented. Text constants, floats, heap operations and other target languages are refused by the C/Python converters.

## Installation

Needs Linux AArch64, `git`, `sh`, `file`, `sha256sum`, `gcc` and `python3`. The bootstrap uses no C compiler, assembler or linker.

```sh
git clone https://github.com/aien-dev/omega-bridge.git
cd omega-bridge
sh tools/bootstrap.sh   # fetches the pinned Omega source commit, grows omc from the seed, checks the fixpoint
tools/build.sh          # builds build/bridge from src/toc.om with the pinned seed
```

The bootstrap fetches the Omega source commit recorded in `docs/PROVENANCE.md` (`29b12760f4c962606411d6bf25032aedef063301`), so it needs access to the upstream repository. It ends with `bootstrap fixpoint RC=0` and leaves the seed at `build/bootstrap/omc` (sha256 `191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9`).

## Configuration

- `OMEGA_SOURCE`: an existing Omega checkout to read the pinned commit from instead of fetching it (read only).
- `OMEGA_SEED`: an already qualified seed compiler; its sha256 must be the pinned one above.
- `OMEGA_NATIVE_OMC`: the seeded compiler for the native call tests, the omega-mv `seed/out/omc` (sha256 `734f0a39319fbfa930bcc62cb30dbf06d47d78e126372b74f5baf478e6126b61`, omega-mv PR #696).
- `MAXPY`: Python interpreter of a venv with `modular==26.7.0`, used by `conformance/run.sh`.
- On a shared build host, prefix the build and test commands with `quiet-build`, as the README does. Without it, run the scripts directly.

## Usage

```sh
# Full local suite: build, differential (native vs C vs Python), refusals, callers, controls, robustness
tools/test.sh

# Convert and run an example
tools/bridge c tests/fixtures/fib.om > build/fib.c
gcc -std=gnu11 -O2 build/fib.c -o build/fib
build/fib
tools/bridge python tests/fixtures/fib.om > build/fib.py
python3 build/fib.py

# Real C and Python application callers of a generated library
python3 tests/attachments.py

# Native call ABI v1: one compiled Omega function called from C, C++, Python, Rust, Zig, Go
OMEGA_NATIVE_OMC=/path/to/omega-mv/seed/out/omc sh tests/native/run.sh

# GPU adapter protocol (no device is opened)
OMEGA_SEED=build/bootstrap/omc sh tools/build-gpu-adapter.sh
python3 tests/gpu/test_gpu_adapter.py
```

`tools/test.sh` ends with `ALL SUITES RC=0`. `tests/native/run.sh` emits `NATIVE-CALL PASS` only after all seven required callers (including C with BTI) have built and executed successfully. Missing language toolchains emit NOT_RUN and exit nonzero; present toolchains whose builds fail emit FAIL and exit nonzero. `tests/native/test_build_failures.sh` exercises both refusal paths with failing-toolchain controls, then runs the real Zig and Go callers. `tools/bridge` writes to stdout only after the whole conversion succeeds and refuses to run if `build/compiler.sha256` no longer matches (rebuild with `tools/build.sh`).

`conformance/run.sh` needs `MAXPY` (a Modular MAX 26.7 venv); without `--device` it runs on CPU only. `conformance/run.sh --device` and `tools/run-device-window.sh --ledger <ID>` need the NVIDIA GB10 on a DGX Spark inside an authorized `spark-window`, plus a sibling CUDApp build. Do not run them anywhere else.

## Conventions

- All conversion logic stays in `src/*.om`. The Python under `tests/` and `conformance/` is test infrastructure, not part of the bridge.
- Every compiler input is pinned by sha256. Never commit a compiler binary; the bootstrap rebuilds it from source.
- The seed checks the whole unit before either backend runs; `tools/bridge` snapshots the input once so validation and generation read identical bytes. Keep that order.
- A refusal is a result: capacity exhaustion or an unsupported feature exits with a code and writes no partial output. Do not add silent fallbacks.
- Keep red before green: add the failing log beside the passing one in `evidence/` when you fix a defect. Never rewrite an existing evidence log.
- Sealed files: the newest `evidence/seal-*/files.sha256` must match the tree, and CI (`.github/workflows/ci.yml`) checks it. Editing a sealed file means adding a new `evidence/seal-<date>/` with `files.sha256` and a `NOTE.md` that lists what changed and why. Never edit an older seal, including the original `evidence/files.sha256`.
- Generated C targets GNU C11 and POSIX; generated Python targets Python 3. Callers must supply an eight-MiB stack (see `docs/CAPABILITIES.md`).

## Safety and approvals

- Conversion creates isolated temporary build files and never installs or replaces an application. Keep it that way; do not add install steps.
- The GPU adapter is disabled by default: no daemon, no environment hook, no automatic attachment. A caller proceeds only on `ACCEPT`; `REFUSE` is final. Ask before changing that contract or the wire format in `docs/GPU-ADAPTER.md`.
- Device runs happen only in an authorized GB10 window. `tools/run-device-window.sh` never resets the GPU, changes the driver or touches a serving process; keep it that way.
- Ask before changing any pinned commit or fingerprint (`tools/bootstrap.sh`, `tools/build.sh`, `tools/bridge`, `tests/native/run.sh`).

## Further reading

- `README.md`: build, convert and caller quick start.
- `docs/CAPABILITIES.md`: supported features, limits and trap codes.
- `docs/ABI.md` (ABI v0), `docs/NATIVE-ABI.md` (native call ABI v1).
- `docs/GPU-ADAPTER.md`, `docs/GPU-SUPPORT-MATRIX.md`, `docs/MAX-INTEGRATION.md`: the GPU and MAX boundary.
- `docs/DESIGN.md`, `docs/PROVENANCE.md`, `docs/REPRODUCE.md`: design decisions, source pins, reproduction steps.
- `evidence/README.md`: what the local qualification ran.
