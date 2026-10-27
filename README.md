# Omega Bridge

Omega's compatibility gateway. `src/toc.om` is an Omega program that converts a checked, bounded Omega subset into executable C and Python; `src/native.om` generates bindings so existing C, C++, Python, Rust, Zig and Go code calls compiled Omega; `src/gpu_adapter.om` negotiates and admits GPU artifacts and runs no kernel. Apache-2.0 WITH LLVM-exception.

Ownership rule ([ARCH-0042](https://github.com/aien-dev/aien-architecture-mv/pull/342), PROPOSED): Omega owns computation, CUDA++ owns GPU execution, Omega Bridge owns compatibility.

- **Omega Bridge (this repository)** owns compatibility: conversion to C and Python, native-call bindings, framework attachments (PyTorch, llama.cpp/GGML, MAX) and GPU artifact negotiation. It exists so existing ecosystems can adopt Omega without rewriting; it makes them optional and does not constrain Omega to them.
- **[Omega](https://github.com/aien-dev/omega-mv)** owns computation: the language and its semantics, the seeded compiler and its pin. This repository builds with that compiler; it is not a second Omega compiler. Today `tools/bootstrap.sh` replays the seed itself and `src/toc.om` keeps its own front end; both stay as they are, and new compiler work goes to Omega ([omega-mv#870](https://github.com/aien-dev/omega-mv/issues/870), [omega-mv#871](https://github.com/aien-dev/omega-mv/issues/871)).
- **[CUDA++](https://github.com/aien-dev/CUDApp)** owns GPU execution: encoder, GPU code generation, cubin writer, artifact admission, driver client and runtime. Omega device runs here go through CUDA++ (`conformance/omega_runner.c` links its `libomega_gpu.a`; `tools/run-device-window.sh` calls its `cubin_probe`).

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

## License

First-party material is licensed under the Apache License, Version 2.0 with LLVM
Exceptions (`Apache-2.0 WITH LLVM-exception`). See [LICENSE](LICENSE) and
[NOTICE](NOTICE). The LLVM exception permits compiled object code derived from
this software to be redistributed under terms of the recipient's choosing.
Third-party components keep their own notices.
