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
| top-level text constants, get/len/write, read-only view calls | const uchar arrays with carried byte length | immutable bytes with carried byte length |
| inline quoted expressions; text put/read/edit destinations | refused by seed (16/20) | same |
| floating point, heap, free, own, reflection, concurrency, GPU, external calls | refused by seed or bridge | same |
| arbitrary C/Python input | no frontend | no frontend |

Capacity limits: input including the target selector is below 65,536 bytes, output at most 262,144 bytes, 32 functions, four parameters per function (arrays expand to address/length), eight globals/texts combined, 32,768 decoded text bytes total, 32 live locals, 32 block levels including the function, 1,024 expression nodes per statement, eight-character names. Global arrays have at most 524,288 elements. Local arrays total at most 32,768 bytes per function. Capacity exhaustion is a compile refusal (14, 23 or 24), never a partial generated file. The seed has further checked register and grammar limits.

Resource boundary: generated execution has a 128-active-call limit, reported as trap 6. Native Omega instead checks its eight-MiB machine stack. Their exhaustion thresholds differ. Only executions within the bridge budget are claimed equivalent; t_stack verifies the eventual trap code only. C hosts must provide an eight-MiB stack. Resource consumption, allocation failure and OS signal/restart behavior are not cross-runtime equivalence claims. Python uses its host heap for fixed-size arrays and interpreter state; the Omega source language has no heap operations. This is not a no-allocation Python runtime.

For loops evaluate a compound count once; a variable count is read each iteration. Variable-count for loops and while loops have a default one-million-iteration guard. Explicit while bounds retain the seed's allowed range. Arrays are never returned, transferred or stored as references. View writes, shape mismatches and overlapping array arguments inside Omega are refused by the shared frontend. Runtime bounds are always enabled.

Full-program results are compared byte-for-byte on stdout/stderr and process status. Trap exits are 100 + code; explicit exit and main return use the low eight bits. I/O tests use ordinary pipes/files with no asynchronous signals. Neither backend optimizes away checks.

Other targets need a real emitter, capability checks, reference executor, differential corpus and an attachment gate. Rust, JavaScript, Go, Java, C#, Fortran and other languages have no implemented or tested adapter here. Their possible use of the C ABI is not a support claim.

The seed's optional grouped-expression syntax and explicit `view A` argument prefix are not lowered by this bridge; use ordinary prefix expressions and view-typed parameters. Source constructs beyond the table may be accepted by the seed and then refused by the target compiler. Error 24 includes an unsupported-capability diagnostic; errors 13/14/23 identify name, table/output or storage limits. No target output is published on these failures.

Text uses the seeded grammar: only `\n`, `\t`, `\\` and `\"` escapes.
Raw zero, CR and UTF-8/high bytes inside quotes are preserved; raw LF and
unknown escapes refuse with 22. Length counts decoded bytes, including zeros;
there is no terminator or Unicode character counting. Empty text has length zero.
Zero-length view parameter shapes remain seed refusal 8. C uses decimal byte
initializers and a storage placeholder for empty text with no addressable elements;
Python uses bytes from numeric tuples. Text pool/table exhaustion refuses with 14.
Text names and mutable globals share one table, retaining exact name matching.
See [L551 design](TEXT-CONVERSION.md) and evidence/text-native for actual gates.
