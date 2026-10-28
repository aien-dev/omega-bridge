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

The additive mode accepts at most 32 numeric literal constants, 512 functions,
six parameters per function, function names up to the frontend's 63-byte limit
(other names retain its limits), fixed view/edit shapes up to
16,777,216 elements, explicit `view`/`edit` call prefixes and bounded-loop
`break`. Seeded C also supports `continue` within a checked enclosing loop.
Default variable-loop and while guards are 16,777,216 iterations. Source and
emission storage are bounded at 1 MiB and 4 MiB; seeded local array storage is
bounded at 16 MiB, while the baseline local-storage refusal remains 32 KiB.
Checked arithmetic, bounds, alias refusals, call budget and no-heap restrictions
remain enforced. Text constants and external calls remain unsupported.
These are implementation bounds, not performance measurements.

Seeded C permits internal binary32 scalars for explicit `f32` literals,
`bitcast uint`/`bitcast f32`, `fabs`, multiplication and ordered `le`.
Decimal conversion reuses the pinned Omega e5b32567 implementation; storage is
canonical IEEE-754 bits and C arithmetic uses binary32 intermediates under the
host's default floating-point environment. Fast-math and incompatible binary32
implementations are refused at C compilation. Public floating-point
parameters/results, floating-point arrays, numeric float casts and other
float operators remain refused, as do all Python and baseline float inputs.
No implicit f64 or approximate integer substitute is emitted.

Function units export only their final function, using `omega_NAME`.
`h` validates every function body through the same emitter before emitting the
C declaration from checked signature metadata. Exported scalar value parameters
are volatile inside the checked setjmp wrapper; the public ABI is unchanged.
The result pointer comes first; scalars use canonical uint64_t bits; arrays
use address and element-count pairs. Counts must equal the declared fixed
shape. ABI statuses are 0 for completion, 1 through 14 for Omega traps, 32 for
invalid host arguments or overlapping arrays, and 33 for reentry. Views are
not written by Omega and use const-qualified C pointers. Generated C contains the implementation and checked
runtime, not a call into AArch64 machine code, and can be compiled on Linux
x86-64 with GNU C. Native call adapters remain a separate AArch64 path.
Literal-count loops do not emit an unused runtime guard counter. Seeded C
marks source scalar declarations as possibly unused, preserving evaluation of
their initializers, including calls with side effects. This is declaration
metadata, not a repository warning-flag change. The seeded strict-host test
compiles with `-Wall -Wextra -Werror` and includes an annotation-removal mutant.

Qualification is separate from implementation. Run the unchanged baseline
`tools/test.sh` first, then `python3 tests/seeded.py` with both pinned compilers
configured. The latter compares native Omega, generated C and Python,
executes generated x86-64 machine code through qemu-x86_64, checks the header
ABI, and includes wrong-seed and arithmetic-emitter negative controls.
No device qualification is implied.

`python3 tests/seeded_float.py` compares the seeded executable and generated C
byte-for-byte over zero, subnormal, normal, overflow, infinity and NaN inputs.
It includes baseline/Python, public-float, array, numeric-cast, unsupported-op,
header-validation and fast-math refusal controls. These are host results only.

## Portable import-free scalar profile

`tools/bridge-freest c|h SOURCE.om` is a separate, fail-closed profile. It
does not replace the hosted `tools/bridge-seeded c|python|h` roots. Its parser,
structural checks and emitter are implemented in `src/freest.om`, derived from
the baseline converter's lexer, signature tables and typed expression nodes.
The shell entrypoint only snapshots, checks compiler fingerprints, validates
with the seeded frontend, compiles the Omega converter and publishes its output
after success. It implements no source parser.

Use the same `OMEGA_SEED` baseline fingerprint and `OMEGA_SEEDED_OMC` frontend
fingerprint documented above. The wrapper validates and converts the identical
snapshot. No native x86 Omega compiler is required: portable C is compiled by the
consumer's C compiler. Both `c` and `h` traverse the complete source before
publishing bytes, including every unused helper. Headers cannot bypass profile
refusal. The input bounds and scalar type/name limits remain those of the
seeded frontend and converter tables.

The accepted subset is integer-only, stateless and nontrapping: scalar
signatures, literal constants, scalar locals, `if`/`else`, `ret`, and acyclic
function calls. Unsigned non-bool addition, subtraction, multiplication and
negation wrap at the declared width. Integer comparisons and bitwise operations
are supported, as are identity and same-signedness widening conversions
(including bool to a wider unsigned type). Signed arithmetic, division,
remainder, every shift, narrowing and signedness-changing conversions are
refused conservatively, even when a particular constant or path could be safe.
Loops, arrays, mutable globals, text, I/O, host words, `main`, recursion, floats,
explicit traps, contracts and OM-2 are outside this profile. Refusal applies to
the complete unit, not merely the exported root or reachable helpers. No
function-name whitelist is used.
Spell scalar types as `bool`, `uchar`, `ushort`, `uint`, `ulong`, `byte`,
`short`, `int` or `long`; short type aliases are outside this profile.

The final function is exported as `uint32_t omega_NAME(uint64_t *result, ...)`.
The result pointer is first. Arguments and results use canonical uint64_t
integer bits, including sign extension for signed values. Status 0 stores the
result; status 32 refuses null, misaligned or wrapping result addresses and
noncanonical scalar arguments before any store. As with other native pointer
ABIs, callers remain responsible for supplying valid writable storage; the
profile does not probe mapped-memory permissions. There are no runtime traps,
reentry state, TLS, setjmp/longjmp, libc calls or host imports in generated code.
The output includes only the standard integer type header and pure local
helpers; it is not a call into AArch64 machine code.

For independent integration, dispatch a future `bridge-seeded freest|freest-h`
mode directly to `tools/bridge-freest c|h` before its hosted-mode case. Keep
the hosted roots unchanged. `tests/freest.py` exercises both hosted and freest
revision/epoch roots, the result-first ABI and exhausted-generation boundaries,
arbitrary helpers, structural refusal controls and a wrong-result control.
It inspects O0/O2 freestanding objects and a `-r -nostdlib` link with `nm -u`
(requiring an empty set, not an import allowlist) and `readelf` (no TLS sections).
Run it after `tools/build.sh` with both pinned compilers configured. Set
`FREEST_CUDAPP_ROOT` to use a consumer checkout's actual revision/epoch sources
instead of the checked-in source-shape fixtures. For x86-64 execution from an
AArch64 host, set `CC=x86_64-linux-gnu-gcc` and
`FREEST_RUNNER='qemu-x86_64 -L /usr/x86_64-linux-gnu'`.
The default hosted optimization is O2; `HOSTED_OPT` selects an explicit
comparison build and is printed in the result. These are targeted host checks,
not device qualification.
