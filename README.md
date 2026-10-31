# Omega Bridge

Omega's compatibility gateway. `src/toc.om` is an Omega program that converts a checked, bounded Omega subset into executable C and Python; `src/native.om` generates bindings so existing C, C++, Python, Rust, Zig and Go code calls compiled Omega; `src/gpu_adapter.om` negotiates and admits GPU artifacts and runs no kernel. Apache-2.0 WITH LLVM-exception.

Ownership rule ([ARCH-0042](https://github.com/aien-dev/aien-architecture-mv/pull/342), Accepted (Drake, 2026-10-30)): Omega owns computation, CUDA++ owns GPU execution, Omega Bridge owns compatibility.

- **Omega Bridge (this repository)** owns compatibility: conversion to C and Python, native-call bindings, framework attachments (MAX conformance; PyTorch and GGML pending (#23/#30, ggml-omega#1/#2)) and GPU artifact negotiation. It exists so existing ecosystems can adopt Omega without rewriting; it makes them optional and does not constrain Omega to them.
- **[Omega](https://github.com/aien-dev/omega-mv)** owns computation: the language and its semantics, the seeded compiler and its pin. This repository builds with that compiler; it is not a second Omega compiler. Today `tools/bootstrap.sh` replays the seed itself and `src/toc.om` keeps its own front end; both stay as they are, and new compiler work goes to Omega ([omega-mv#870](https://github.com/aien-dev/omega-mv/issues/870), [omega-mv#871](https://github.com/aien-dev/omega-mv/issues/871)).
- **[CUDA++](https://github.com/aien-dev/CUDApp)** owns GPU execution: encoder, GPU code generation, cubin writer, artifact admission, driver client and runtime. Omega device runs here go through CUDA++ (`conformance/build.sh` links `conformance/omega_runner.c` against its `libomega_gpu.a`; `tools/run-device-window.sh` calls its `cubin_probe`).

The source-only bootstrap of the pinned Omega compiler currently requires Linux AArch64. Generated C uses GNU C11 and POSIX; generated Python uses Python 3. This branch has local differential tests and caller demos; independent review remains required before release. No universal conversion or performance improvement is claimed.

Build from exact pinned source:

```sh
quiet-build tools/bootstrap.sh
quiet-build tools/build.sh
quiet-build tools/test.sh
```

On a host without quiet-build, run those scripts directly. The bootstrap fetches the exact Omega source commit recorded in docs/PROVENANCE.md. Access to the upstream repository is required. An existing checkout can supply it through OMEGA_SOURCE; it is read only. No compiler binary is stored in this repository. If you already have the qualified seed, OMEGA_SEED can name it; its fingerprint is enforced.

Convert and run an example:

```sh
tools/bridge c tests/fixtures/fib.om > build/fib.c
gcc -std=gnu11 -O2 build/fib.c -o build/fib
build/fib
tools/bridge python tests/fixtures/fib.om > build/fib.py
python3 build/fib.py
```

Output goes to stdout only after the complete conversion succeeds. Source validation is mandatory. Conversion creates isolated temporary build files and never installs or replaces an application. Inspect generated output before opting to link or import it.

Run real C and Python application callers:

```sh
quiet-build python3 tests/attachments.py
```

See [supported features and limits](docs/CAPABILITIES.md), [caller ABI and ownership](docs/ABI.md), [design and study decisions](docs/DESIGN.md), and [provenance](docs/PROVENANCE.md). Text constants, floats, heap operations and other target languages are explicitly unsupported by the C/Python converters. GPU interoperability is a separate, opt-in adapter boundary (it converts no host program): see [GPU adapter](docs/GPU-ADAPTER.md) and the [support matrix](docs/GPU-SUPPORT-MATRIX.md). Python/C input conversion is not implemented. The Python test harness is infrastructure; all conversion logic and both runtime emitters are in [src/toc.om](src/toc.om).

Call compiled Omega in place from six languages (the native call adapter, a separate claim from conversion: it runs Omega's own machine code, it does not turn Omega into another language):

```sh
OMEGA_NATIVE_OMC=<seeded omc> tools/native build/native tests/native/madd.om
```

That writes `libomega_native.so` and, from the same Omega signatures, `omega_native.h` (C and C++), `omega_native.py`, `omega_native.rs`, `omega_native.zig` and `omega_native.go`; a program includes or imports its file and calls `omega_madd`, nothing is declared by hand. One generator, [src/native.om](src/native.om), writes all six. Contract, limits and the qualification run: [native call ABI](docs/NATIVE-ABI.md).

`f32` and `ushort` array kinds (4-byte and 2-byte elements) are qualified by `OMEGA_NATIVE_OMC=<seeded omc> sh tests/native/kinds.sh`. The contract is in [native call ABI](docs/NATIVE-ABI.md).

The native target defaults to `aarch64linux`. Hosted x86-64 SysV Linux bindings
are selected explicitly; there is no build-host architecture inference:

```sh
OMEGA_NATIVE_OMC=/path/to/baseline/omc \
OMEGA_NATIVE_X86_OMC=/path/to/x86/omc \
CC=x86_64-linux-gnu-gcc \
tools/native --target x86linux build/native-x86 tests/native/madd.om
```

The existing pinned `OMEGA_NATIVE_OMC` remains required to build the generator.
The separately pinned `OMEGA_NATIVE_X86_OMC` compiles both OM-1 and OM-2 inputs;
its target directive is not added to the source identity. Pins and the exact
generator contract are in [native call ABI](docs/NATIVE-ABI.md#target-selection-and-compiler-custody).
`--freestanding` remains AArch64-only and refuses x86. Cross-building a library
does not execute its callers. QEMU results are emulator evidence, not native
x86-64 qualification; native execution is NOT_RUN until exercised on an x86-64
host. The historical AArch64 evidence does not qualify this x86 integration.
The x86 emulator suite selects its oracle with `QEMU_X86_64`; use the unpatched
QEMU 10.0.14 oracle and guest Python setup documented in
[native call ABI](docs/NATIVE-ABI.md#x86-emulator-runner-and-qemu-oracle).
QEMU 8.2.2 has observed signal and `/proc/self/maps` limitations for these
callers. At the current x86 compiler pin, the full suite plus mismatched-pin and
failed/missing-toolchain controls passed EMULATED; see
[the pinned receipts](evidence/native-x86-62775d2a.json). Earlier
pins' receipts remain in `evidence/native-x86-badedbb0/`, `evidence/native-x86-f7752bc5/` and `evidence/native-x86/`. Physical x86
execution remains NOT_RUN.
## Human-Directed Agentic Engineering

Development follows Human-Directed Agentic Engineering (HDAE): humans define goals, architecture, constraints, acceptance criteria, and stopping points; agents implement, execute checks, diagnose failures, and revise within those boundaries. Human review retains responsibility for claims, acceptance, and release decisions.

For the documented method and a systems-software case study, see Gregory M. Kurtzer, [*Ginux: Building an Independent Kernel That Runs Linux Userspace through Human-Directed Agentic Engineering* (2026)](https://doi.org/10.5281/zenodo.23682548). This method citation does not widen the checked conversion subset or replace independent review.

## License

First-party material is licensed under the Apache License, Version 2.0 with LLVM
Exceptions (`Apache-2.0 WITH LLVM-exception`). See [LICENSE](LICENSE) and
[NOTICE](NOTICE). The LLVM exception permits compiled object code derived from
this software to be redistributed under terms of the recipient's choosing.
Third-party components keep their own notices.
