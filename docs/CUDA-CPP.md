# Experimental CUDA C++ input for om

This candidate adds a **bounded CUDA C++17 kernel frontend**, handwritten in
seeded Omega. It does not finish CUDA C++ support. Its execution target is an
explicit CPU simulator, **not the GPU**, PTX, cubin, or the CUDA host/runtime ABI.
An additional [offline sm121 lab backend](CUDA-CPP-GPU.md) emits actual GPU code data but is not qualified for launch. There is no nvcc, Clang, C++ parser, C library, or CUDA runtime in its construction
or execution path. The existing POSIX shell dispatcher handles arguments, source
snapshots, process launch and atomic output publication; it is not native Omega.

## Build and use the candidate

On Linux AArch64, from this source checkout:

```sh
tools/install.sh --offline --prefix "$HOME/cuda-cpp-candidate"
OM="$HOME/cuda-cpp-candidate/bin/om"
"$OM" check --from cuda-cpp tests/cuda-cpp/vector.cu
"$OM" build --from cuda-cpp --target cpu-sim tests/cuda-cpp/vector.cu -o vector-sim
# Binary stdin framing described below:
"$OM" run --from cuda-cpp --target cpu-sim tests/cuda-cpp/vector.cu < request.bin > result.bin
```

The prefix's parent must already exist. This is a source-build candidate, not a
published release or a globally installed update. `omg` is the same implementation.
`check` compiles through both frontend and omc but never runs the result. Build and
run require an explicit target. Execution currently requires `--target cpu-sim`; an offline build may select `sm_121-lab`. Omission, `sm_121`, `cuda` and `gpu` refuse rather
than silently falling back to CPU execution. Ordinary Omega commands are unchanged.
A `.cu` extension alone does not select this frontend: `--from cuda-cpp` is explicit.

## Source profile

The executable example in `tests/cuda-cpp/vector.cu` uses this shape:

```cpp
__global__ void vector_add(unsigned int *out,
                          const unsigned int *left,
                          const unsigned int *right,
                          unsigned int count) {
    unsigned int index = blockIdx.x * blockDim.x + threadIdx.x;
    if (index < count) {
        out[index] = left[index] + right[index];
    }
}
```

The kernel, pointer, length and index identifiers may be renamed independently.
Exactly one writable output pointer, one to four const input pointers and a final
unsigned-int length are required. All declared names must be distinct ASCII C++
identifiers, at most 63 bytes, not keywords or CUDA builtin names. No extra function
or declaration is accepted. Source names are resolved to generated internal names,
never interpolated into emitted Omega source.

The index initializer and guarded-store skeleton must have exactly the structure
shown. Expressions admit const input elements at that index, the length parameter,
decimal unsigned-32 literals with `U` or `u` suffix, parentheses and binary
`+ - * & ^ |`. C++ precedence and left associativity are retained; every operation
wraps at 32 bits. Constants above UINT32_MAX, octal and hexadecimal spellings,
unsuffixed literals, signed arithmetic, casts, calls, pointer arithmetic and reads
from the writable output refuse. There are no side effects within expressions.
The inputs and output are disjoint, length-carried simulator buffers, not arbitrary
C++ pointers. The external oracle uses 32-bit unsigned int; other C++ integer
models are not qualified.

Spaces, tabs, LF, CR, line comments and block comments are accepted. NUL and
backslashes are refused before comment processing to avoid C++ translation-phase
splicing. Double-question-mark sequences with a following byte are conservatively
refused, including all trigraph spellings. Non-ASCII code cannot form a valid token;
comment bytes may be non-ASCII. No preprocessor, include, macro, template, namespace,
class, loop, host CUDA API, launch syntax, float, shared memory, synchronization,
atomic, multidimensional grid or general C++ feature is supported.

Limits: 16,384 source bytes, 128 AST nodes (a binary tree can have 127), expression
parser recursion at most 16 active calls. Fifteen nested parentheses around a
literal are tested; deeper operator combinations consume the same bound. Lowering
uses an internal bounded SSA temporary array, so a valid long expression does not
exhaust omc's 16-register-per-function limit. This is finite test evidence, not a
formal proof of C++ equivalence.

## Simulator framing and semantics

All words are little-endian unsigned 32-bit. Stdin contains:

1. `blocks`, `threads`, `length`.
2. The initial writable output, `length` words.
3. Each const input, `length` words, in signature order.
4. EOF, with no trailing bytes.

Both grid dimensions are in 1..4096, their product at most 4096, length in 0..4096.
The executable computes each covered index `i < length` and `i < blocks*threads`.
Uncovered output retains its supplied value. Stdout is exactly `length` words of
output. All input is validated before stdout; truncated, excessive or malformed
frames exit 77 with no output. A zero-length frame succeeds with empty output.
This protocol is a test interface, not a CUDA executable ABI, stream or launch API.
Native execution is explicit and is not an OS sandbox.

Frontend refusals return 65, capacity refusals 67 and frontend I/O errors 77 with
named stderr diagnostics and no generated source. Compiler errors return command
refusal 65. OS write failures may interrupt output; signal handling is inherited.
Build destination publication preserves the existing command's safety: snapshots,
static AArch64 ELF validation, same-inode refusal, symlink refusal, private mode,
and same-directory atomic rename. Failed source/target/build stages preserve an
existing destination. The frontend is included in installation integrity checks
and fixed uninstall ownership; no model, service, GPU module or global command is
changed by testing this candidate.

## Verification

```sh
tools/test-native.sh
# Focused native checks after tools/build-native.sh:
python3 tests/cuda-cpp/gate.py
python3 tests/cuda-cpp/commands.py
```

The native gate compiles original CUDA source with a test-only C++ host shim for
CUDA builtins, then compares exact output with the seeded-Omega-built simulator.
That shim is an external oracle only, never a product fallback. Python prepares
test frames and compares raw bytes, not production parsing or computation.
C++ warning exceptions for parenthesis suggestions and unused parameters retain
those diagnostics: both are valid source cases in this profile. Other warnings
remain errors. Original oracle-harness construction errors and semantic RED records
are retained in `evidence/cuda-cpp/development/` rather than counted as passes.
The gate also requires actual compiled, executable behavioral mutants to disagree
with the independent C++ oracle. Installed tests cover both aliases, caller stdin,
explicit target refusal, source/destination safety, integrity and uninstall.

## Remaining work toward the user's full request

Real GPU lowering must attach to the qualified seed-native GPU/IR compiler owned
by L408; no unqualified mutable compiler or generated-C bridge is substituted.
GPU code generation, launch/runtime integration, real-chip equivalence and recovery
remain NOT_RUN. General C++ syntax/types, functions/templates, floats and broader
CUDA semantics are absent. This first frontend slice neither completes CUDA C++
support nor retires any running GPU/runtime component. Further extensions must add
valid-source differential fixtures and retain unsupported/malformed refusals.
