# Omega Bridge

An Omega-written compiler that emits executable C and Python from a checked, bounded Omega subset. Existing C and Python applications can also call generated library functions, and compiled Omega functions can be called in place from C, C++, Python, Rust, Zig and Go through the native call adapter. Apache-2.0 WITH LLVM-exception.

The source-only compiler bootstrap currently requires Linux AArch64. Generated C uses GNU C11 and POSIX; generated Python uses Python 3. This branch has local differential tests and caller demos; independent review remains required before release. No universal conversion or performance improvement is claimed.

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

## Pending Linux kernel-leaf envelope experiment

[`src/kernel_leaf.om`](src/kernel_leaf.om) emits a fixed-symbol AArch64 assembly
envelope for the companion restricted `kleaf` compiler experiment. It matches
the inspected Linux `7.0.0-1019-nvidia` leaf tracing/PAC metadata, not an arbitrary
kernel ABI. It requires trusted compiler/source custody: framing checks are not
a general machine-code verifier. It does not implement driver policy, Linux
effects, a module loader or the userspace native trampoline.

This source-only experiment is not integrated into `tools/native`, does not
change any compiler fingerprint or production admission path, and is not a
kernel/GPU qualification claim. The compiler-side
`seed/omc/kernel-leaf-experiment.py` is its host oracle and exact kbuild-object
comparison. GNU assembly/object tooling remains a disclosed build dependency.

## License

First-party material is licensed under the Apache License, Version 2.0 with LLVM
Exceptions (`Apache-2.0 WITH LLVM-exception`). See [LICENSE](LICENSE) and
[NOTICE](NOTICE). The LLVM exception permits compiled object code derived from
this software to be redistributed under terms of the recipient's choosing.
Third-party components keep their own notices.
