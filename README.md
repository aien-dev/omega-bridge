# Omega Bridge

An Omega-written compiler that emits executable C and Python from a checked, bounded Omega subset. Existing C and Python applications can also call generated library functions. Apache-2.0 WITH LLVM-exception.

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

See [supported features and limits](docs/CAPABILITIES.md), [caller ABI and ownership](docs/ABI.md), [design and study decisions](docs/DESIGN.md), and [provenance](docs/PROVENANCE.md). Text constants, floats, heap operations and other target languages are explicitly unsupported by the C/Python converters. The "GPU adapter" is accept/refuse only: it reads a request on stdin and answers `ACCEPT` or `REFUSE` on stdout. It has no GPU contact (it opens no device, loads nothing and runs nothing on a GPU) and converts no host program; see [GPU adapter](docs/GPU-ADAPTER.md) and the [support matrix](docs/GPU-SUPPORT-MATRIX.md). Python/C input conversion is not implemented. The Python test harness is infrastructure; all conversion logic and both runtime emitters are in [src/toc.om](src/toc.om).

## License

First-party material is licensed under the Apache License, Version 2.0 with LLVM
Exceptions (`Apache-2.0 WITH LLVM-exception`). See [LICENSE](LICENSE) and
[NOTICE](NOTICE). The LLVM exception permits compiled object code derived from
this software to be redistributed under terms of the recipient's choosing.
Third-party components keep their own notices.
