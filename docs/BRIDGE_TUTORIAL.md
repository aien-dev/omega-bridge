# One real conversion and its ABI boundary

This is a lesson for **pending branch** `feat/c-python-bridge` at exact commit `77376b1941a020dba441a14fce8eaadea692a5b7`, not a claim that its implementation has merged into `main`. The recovered-source check in the front page covers a different, older main revision. No implementation was copied or rewritten merely to create this tutorial.

## What actually happens

The [Omega-written converter](https://github.com/aien-dev/omega-bridge/blob/77376b1941a020dba441a14fce8eaadea692a5b7/src/toc.om) emits C or Python from a checked, bounded Omega subset. It is not a C/Python-to-Omega translator or a universal application converter. The [CLI boundary](https://github.com/aien-dev/omega-bridge/blob/77376b1941a020dba441a14fce8eaadea692a5b7/tools/bridge):

1. Verifies the source/compiler manifest and exact seed fingerprint.
2. Snapshots the input once so checking and generation consume identical bytes.
3. Calls the pinned Omega seed compiler to check the complete unit.
4. Runs the Omega-written backend with the selected C or Python mode. Output is released only after conversion succeeds.

The [source-only bootstrap](https://github.com/aien-dev/omega-bridge/blob/77376b1941a020dba441a14fce8eaadea692a5b7/tools/bootstrap.sh) reconstructs the compiler through the recorded seed chain at Omega `29b12760f4c962606411d6bf25032aedef063301`, compares three compiler stages, and enforces final compiler SHA-256 `191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9`. A fixpoint is not diverse double compilation or independent frontend verification. The [retained qualification](https://github.com/aien-dev/omega-bridge/blob/77376b1941a020dba441a14fce8eaadea692a5b7/evidence/README.md) includes earlier failed recovered-compiler runs; those failures are not erased by a later passing candidate.

## Fresh-checkout exercise

Prerequisites: Linux **AArch64**, Git, POSIX shell/core utilities (`file`, `sha256sum`, `cmp`, `realpath`, `tar`), GNU C11-compatible GCC, Python 3, HTTPS access to the pinned Omega source, and read permission for this private repository. No GPU, model, root account or application installation. Compiler bootstrap itself does not invoke a C compiler, assembler or linker; GCC is used later for the emitted C target. Python is a target/harness dependency, not part of the seed's birth.

```sh
set -eu
: "${TMPDIR:?set TMPDIR to a writable scratch directory}"
work=$(mktemp -d "$TMPDIR/bridge-lesson.XXXXXX")
git clone --quiet --branch feat/c-python-bridge https://github.com/aien-dev/omega-bridge.git "$work/tree"
cd "$work/tree"
git checkout --quiet --detach 77376b1941a020dba441a14fce8eaadea692a5b7
tools/bootstrap.sh
tools/build.sh
build/bootstrap/omc < tests/fixtures/fib.om > build/fib.native
chmod +x build/fib.native
build/fib.native > build/native.txt
tools/bridge c tests/fixtures/fib.om > build/fib.c
gcc -std=gnu11 -O2 build/fib.c -o build/fib
build/fib > build/c.txt
tools/bridge python tests/fixtures/fib.om > build/fib.py
python3 build/fib.py > build/python.txt
cmp build/native.txt build/c.txt
cmp build/native.txt build/python.txt
wc -l < build/native.txt
cat build/native.txt
set +e
tools/bridge c tests/unsupported/text.om > build/refused.c 2>build/refusal.txt
rc=$?
set -e
test "$rc" -eq 24
test ! -s build/refused.c
cat build/refusal.txt
python3 tests/attachments.py
```

Expected overall exit **0**. The source bootstrap prints `bootstrap fixpoint RC=0`; both `cmp` calls succeed. The Fibonacci fixture prints **26 lines**, beginning `0`, `1`, `1`, `2` and ending `75025`. This is observed program output, not a performance claim. The unsupported text fixture must return **24**, leave its output empty and report `unsupported bridge capability`. The two real caller tests must report `attachment cases=2 failures=0 RC=0`.

The parent replay used a new temporary checkout of that exact source and the same commands, with `quiet-build` around CPU-heavy stages to cooperate with the Spark. That wrapper changes scheduling, not the assertions. [Observed output and scope](pending-bridge-replay.txt). This bounded replay does not rerun or certify every one of the branch author's 397 qualification checks.

## Calling from C and Python

[Experimental ABI v0](https://github.com/aien-dev/omega-bridge/blob/77376b1941a020dba441a14fce8eaadea692a5b7/docs/ABI.md) and the [actual C caller](https://github.com/aien-dev/omega-bridge/blob/77376b1941a020dba441a14fce8eaadea692a5b7/examples/caller.c) define the interface, not a stable ABI promise:

- C exports are named `omega_<source-name>`, return a `uint32_t` status and take a first `uint64_t *result` argument. Arrays cross as pointer plus element count. Signed scalar arguments use canonical bit representations.
- Python exports return `(status, value)`, with `None` on failure. Supported byte arrays are `bytearray`; supported unsigned-word arrays are plain lists with valid element values.
- Caller buffers are borrowed synchronously. Writes before a trap remain visible; there is no transactional rollback. The C wrapper checks several shape/overlap conditions but cannot prove that a foreign pointer actually names sufficient live storage.
- Invalid arguments and reentry have explicit statuses. Threads, callbacks, strided arrays, DLPack and arbitrary host object protocols are outside this ABI. Read the exact generated declarations and the pinned ABI document before linking.

The caller tests exercise valid values, borrowed-buffer mutation, traps, invalid lengths/null, result overlap and a successful later call. They neither install an adapter into a real application nor qualify arbitrary foreign callers. Reversal means stop importing/linking the generated module and keep the original application implementation; no automatic system hook was installed by this exercise.

## What remains outside this result

Text constants, floating point, GPU execution and other target languages are unsupported in this branch. Generated C depends on the platform C runtime; generated Python depends on Python. These outputs are not a dependency-free native Omega replacement for every production path. No acceleration is claimed: the existing branch measurements include regressions. Independent code review, cross-architecture qualification, installer/enrollment integration and a public release remain separate work.
