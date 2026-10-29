# Omega Bridge (an Omega-written compiler from a checked Omega subset to C and Python, plus native call and GPU adapter boundaries)

> `src/toc.om` is an Omega program, built by the pinned seeded Omega compiler, that emits executable C and Python from a checked, bounded Omega subset (ABI v0). `src/native.om` generates a C binding so C, C++, Python, Rust, Zig and Go call the machine code the seeded compiler produced (native call ABI v1/v2). `src/gpu_adapter.om` is an opt-in GPU adapter boundary that negotiates and admits artifacts; it converts no host program. The bootstrap and generators require Linux AArch64; hosted native output also has explicit x86-64 SysV Linux selection, exercised under QEMU 10.0.14 (physical x86 NOT_RUN). Independent review remains required before release; no universal conversion or speedup is claimed.

Shared rules: read https://www.aienos.com/agents/RULES.md first. This file adds what is specific to this repository; where the two differ, this file wins here.

## Scope

- Applies to the whole repository.
- `src/`: all conversion logic and both runtime emitters (`toc.om`), the native binding generator (`native.om`) and the GPU adapter (`gpu_adapter.om`). These are Omega source; keep them Omega.
- `tools/`: shell entry points (`bootstrap.sh`, `build.sh`, `test.sh`, `bridge`, `native`, `build-gpu-adapter.sh`, `run-device-window.sh`).
- `tests/`: Python test harness (infrastructure only), fixtures, refusal cases, native callers in six languages, GPU adapter protocol tests.
- `conformance/`: separate-process Omega versus Modular MAX harness. `evidence/`: raw logs and result manifests.
- No compiler binary is stored here. Python/C input conversion is not implemented. Text constants, floats, heap operations and other target languages are refused by the C/Python converters.

## Installation

Needs a Linux AArch64 build host, `git`, `sh`, `file`, `sha256sum`, `gcc` and `python3`. The bootstrap uses no C compiler, assembler or linker. Cross-building hosted x86 native libraries additionally needs an x86-targeting `CC`; it does not make the bootstrap or generator runnable on x86.

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
- `OMEGA_NATIVE_OMC`: mandatory baseline compiler for building the native generator and compiling AArch64 OM-1 units, sha256 `734f0a39319fbfa930bcc62cb30dbf06d47d78e126372b74f5baf478e6126b61` (omega-mv PR #696). Do not replace this pin with the x86 compiler.
- `OMEGA_NATIVE_OMC2`: compiler for AArch64 OM-2 units; its digest is recorded in their identities.
- `OMEGA_NATIVE_X86_OMC`: separate compiler for both OM-1 and OM-2 units under `tools/native --target x86linux`, sha256 `badedbb0c6287887641fcd7e97301b43b5f82f2d7a2838bbe0d17547873108be`. `OMEGA_NATIVE_OMC2` is unused for this target.
- `CC`: native library C compiler, for example `x86_64-linux-gnu-gcc` with `--target x86linux`; no host-architecture inference changes the requested target. `OMEGA_NATIVE_CFLAGS` supplies extra C flags.
- `QEMU_X86_64`: emulator command for `tests/native/x86/run.sh`. Use the unpatched QEMU 10.0.14 oracle documented in `docs/NATIVE-ABI.md`; integration observed signal and `/proc/self/maps` failures with 8.2.2. This is verification infrastructure, not a production dependency. At the current x86 compiler pin, full-suite, mismatched-pin and failed/missing-toolchain controls passed EMULATED; physical x86 execution remains NOT_RUN. Receipts: `evidence/native-x86-badedbb0/`; earlier pins' receipts remain in `evidence/native-x86-f7752bc5/` and `evidence/native-x86/`.
- `OMEGA_NATIVE_X86_PYTHON`, `OMEGA_NATIVE_X86_SYSROOT`, `OMEGA_NATIVE_X86_LIBPATH`: guest Python executable, loader sysroot and optional guest library path for the x86 emulator suite. The Python must be x86 Linux, not the host interpreter.
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

# Hosted x86 native output (cross-build only; this command does not execute callers)
OMEGA_NATIVE_OMC=/path/to/baseline/omc OMEGA_NATIVE_X86_OMC=/path/to/x86/omc \
  CC=x86_64-linux-gnu-gcc tools/native --target x86linux build/native-x86 tests/native/madd.om

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
- Generated C targets GNU C11 and POSIX; generated Python targets Python 3. Callers must supply an eight-MiB stack (see `docs/CAPABILITIES.md`).
- Native output defaults to `aarch64linux`; keep its compiler inputs and `native-gen OUTPUT` calls unchanged. For x86, compile `target x86linux\n` plus the source snapshot and invoke `native-gen OUTPUT x86linux`. Never put the prefix into framed source or source identity. X86 OM-2 export entries occupy six bytes, not AArch64's four-byte words.
- `tools/native --freestanding` remains AArch64-only; x86 freestanding output refuses before creating OUTDIR. Cross-builds and QEMU runs do not qualify native x86 execution: label emulator evidence explicitly and unexecuted native callers NOT_RUN. Do not run the AArch64 BTI-specific caller as an x86 qualification requirement.

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
