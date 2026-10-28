# Bridge v0 capability contract

Input is the pinned seed's Omega program/function language, further bounded below. The shell entry point snapshots the source, asks the pinned Omega compiler to check the entire unit, then sends the same bytes to the Omega target compiler. Both targets consume the same typed nodes. The private build/bridge executable is an internal emitter, not a standalone validation API. Use tools/bridge.

| Feature | C output | Python output |
|---|---|---|
| bool; unsigned/signed 8, 16, 32, 64-bit scalars | supported | supported using canonical 64-bit bits |
| explicit checked numeric conversions | supported | supported |
| unsigned arithmetic | wraps at declared width | same |
| signed add/sub/mul/neg/shl overflow | trap 1 | same |
| div/rem | truncation toward zero, zero divisor trap 2; min/-1 division trap 1; remainder zero | same |
| shifts | arithmetic signed right shift; invalid amount trap 7 | same |
| eager left-to-right operands/call arguments | sequenced GNU statement expressions | Python argument order |
| if/else, bounded while, for | supported | supported |
| forward/mutual calls and recursion in programs | supported within resource budget | same |
| new arrays, global pools, view/edit parameters, get/put/len | checked; actual element widths | bytearray for uchar, list for other widths |
| read/write/exit in programs | POSIX, negative errno returned in long bits | os read/write, same errno mapping |
| callable function units without main | generated checked C ABI wrappers | generated checked module functions |
| text literals, text constants | refused, error 24 | refused, error 24 |
| floating point, heap, free, own, reflection, concurrency, GPU, external calls | refused by seed or bridge | same |
| arbitrary C/Python input | no frontend | no frontend |

Capacity limits: input including the target selector is below 65,536 bytes, output at most 262,144 bytes, 32 functions, four parameters per function (arrays expand to address/length), eight globals, 32 live locals, 32 block levels including the function, 1,024 expression nodes per statement, eight-character names. Global arrays have at most 524,288 elements. Local arrays total at most 32,768 bytes per function. Capacity exhaustion is a compile refusal (14, 23 or 24), never a partial generated file. The seed has further checked register and grammar limits.

Resource boundary: generated execution has a 128-active-call limit, reported as trap 6. Native Omega instead checks its eight-MiB machine stack. Their exhaustion thresholds differ. Only executions within the bridge budget are claimed equivalent; t_stack verifies the eventual trap code only. C hosts must provide an eight-MiB stack. Resource consumption, allocation failure and OS signal/restart behavior are not cross-runtime equivalence claims. Python uses its host heap for fixed-size arrays and interpreter state; the Omega source language has no heap operations. This is not a no-allocation Python runtime.

For loops evaluate a compound count once; a variable count is read each iteration. Variable-count for loops and while loops have a default one-million-iteration guard. Explicit while bounds retain the seed's allowed range. Arrays are never returned, transferred or stored as references. View writes, shape mismatches and overlapping array arguments inside Omega are refused by the shared frontend. Runtime bounds are always enabled.

Full-program results are compared byte-for-byte on stdout/stderr and process status. Trap exits are 100 + code; explicit exit and main return use the low eight bits. I/O tests use ordinary pipes/files with no asynchronous signals. Neither backend optimizes away checks.

Other conversion targets need a real emitter, capability checks, reference executor, differential corpus and an attachment gate; no language other than C and Python has a converter. Calling a compiled Omega function in place from C, C++, Python, Rust, Zig or Go is the native call adapter (docs/NATIVE-ABI.md): `tools/native` builds the library and writes each language's declarations from the Omega signatures. That is a call into Omega's machine code, a separate claim from conversion. JavaScript, Java, C#, Fortran and other languages have no implemented or tested adapter here.

The seed's optional grouped-expression syntax and explicit `view A` argument prefix are not lowered by this bridge; use ordinary prefix expressions and view-typed parameters. Source constructs beyond the table may be accepted by the seed and then refused by the target compiler. Error 24 includes an unsupported-capability diagnostic; errors 13/14/23 identify name, table/output or storage limits. No target output is published on these failures.

## Additive seeded frontend

`tools/bridge-seeded c|python|h SOURCE.om` is an explicit frontend mode for
omega-mv `e5b32567`, requiring `OMEGA_SEEDED_OMC` with sha256
`2c82480596bbdc50cda9626866209ef662d5834f278f839ff4ce0250c495029f`.
The source snapshot is checked by that exact compiler before conversion. A
different compiler fingerprint refuses with status 65 and no target output.
This mode does not change `tools/bridge`, its baseline seed
`191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9`,
or the required `tools/test.sh` suite.

The additive mode accepts at most 32 numeric literal constants, 64 functions,
six parameters per function, function names up to the frontend's 63-byte limit
(other names retain its limits), fixed view/edit shapes up to
16,777,216 elements, explicit `view`/`edit` call prefixes and bounded-loop
`break`. Default variable-loop and while guards are 16,777,216 iterations.
Global/local allocation limits, checked arithmetic, bounds, alias refusals,
call budget, no-heap language restriction and unsupported-feature refusals
remain unchanged. Text constants, floating point and external calls remain
unsupported. These are implementation bounds, not performance measurements.

Function units export only their final function, using `omega_NAME`.
`h` emits that C declaration from the same checked signature metadata as `c`.
The result pointer comes first; scalars use canonical uint64_t bits; arrays
use address and element-count pairs. Counts must equal the declared fixed
shape. ABI statuses are 0 for completion, 1 through 14 for Omega traps, 32 for
invalid host arguments or overlapping arrays, and 33 for reentry. Views are
not written by Omega and use const-qualified C pointers. Generated C contains the implementation and checked
runtime, not a call into AArch64 machine code, and can be compiled on Linux
x86-64 with GNU C. Native call adapters remain a separate AArch64 path.

Qualification is separate from implementation. Run the unchanged baseline
`tools/test.sh` first, then `python3 tests/seeded.py` with both pinned compilers
configured. The latter compares native Omega, generated C and Python,
executes generated x86-64 machine code through qemu-x86_64, checks the header
ABI, and includes wrong-seed and arithmetic-emitter negative controls.
No device qualification is implied.
