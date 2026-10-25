# Native call ABI v1 and v2

ABI v0 (docs/ABI.md) translates Omega source into C or Python source. ABI v1 calls the machine code
the seeded Omega compiler itself produced. Nothing is translated: each foreign language calls the same
compiled Omega function. Omega's language and its internal calling rules are unchanged; the bridge
adapts the foreign side to them.

## What Omega produces

A unit with no `fn main` is compiled by the seeded compiler (`seed/out/omc`) in function mode: raw
AArch64 words, entry at word 0 (`docs/one_layer/OMEGESE.md` 9.1). Its rules (`docs/osc/OSC-1-DESIGN.md`
section 7): parameters in x0..x5 (an `edit`/`view` array arrives as its address; its length is part of
its type), result in x0, the runtime table pointer in x7. A trap loads its code into x1, the table into
x0 and branches to the table entry at offset 16; it never returns. `madd` below compiles to three
instructions (`mul x3, x0, x1; add x0, x3, x2; ret`).

```
fn madd a ulong b ulong c ulong to ulong
p = mul a b
ret add p c
end
```

## The binding

`src/native.om` is an Omega program. It reads units (the unit's source, a 0 byte, the code length as 8
decimal digits, the code) and one argument naming the output: `c` is the library source, one C file;
`h`, `python`, `rust`, `zig` and `go` are that library's declarations for those languages (next
section), written from the same parsed signatures. Output appears only after every unit is accepted;
anything outside the supported signature set, and a missing or unknown output word, is refused (exit
110, no output). The C file:

- embeds each unit's code byte for byte (tests/native/run.sh compares the bytes inside the built
  library with the compiler's output);
- enters the code through a small trampoline that saves the callee-saved registers x19..x28 and
  d8..d15 on the caller's stack, keeps the caller's stack pointer in x19, sets x7, loads the arguments and
  runs the code on the binding's own stack (below);
- gives the code a read-only 32-entry runtime table whose trap entry restores the caller's stack pointer from x19
  and returns the trap code from the exported function (no setjmp/longjmp, nothing crosses the caller's
  frame) and whose other entries refuse with status 34, since function-mode units of this ABI use none
  of them. This relies on the seeded compiler never writing x19..x28 (OSC-1 uses x0..x16, x29, x30);
- reaches each unit through a two-instruction stub (`bti c`, branch) so the code runs under branch
  target identification (BTI) without changing the compiler's bytes;
- exports, per unit, `uint32_t omega_<name>(uint64_t *result, ...)`.

Names must be C identifiers, a parameter name may not end in `_len` (the binding names a length
`o_<name>_len`), and each unit name appears once; anything else is refused before any C is written.

Supported signatures: up to 6 parameters, each `ulong`, `long`, or `edit`/`view` of `ulong` or `uchar`
with a fixed length; result `ulong`, `long` or `void`. A unit may hold several functions: the seeded
compiler enters function-mode code at the unit's last function (word 0 is a branch to it), so the
binding exports that one and the earlier functions stay private helpers, called directly inside the
embedded code, with any Omega types. Only the last function's signature must be supported
(`tests/native/hsum.om`: two helpers, one of which traps).

## The declarations for each language (`tools/native`)

`OMEGA_NATIVE_OMC=<seed omc> tools/native OUTDIR unit.om...` compiles the units with the pinned
compiler, runs the generator once per output word and installs, into OUTDIR:

| file | for | how a program uses it |
|---|---|---|
| `omega_native.c` | the library source | built into `libomega_native.so` by the same command |
| `omega_native.h` | C and C++ | `#include "omega_native.h"` (`extern "C"` inside for C++) |
| `omega_native.py` | Python 3 (ctypes) | `import omega_native`; loads `libomega_native.so` from beside itself |
| `omega_native.rs` | Rust 1.82 or later, edition 2021 or 2024 | `mod omega_native;` beside the crate root; link with `-L OUTDIR` |
| `omega_native.zig` | Zig 0.13 | `@import("omega_native.zig")`; build with `-L OUTDIR -lomega_native -lc` |
| `omega_native.go` | Go (cgo) | package `omeganative`: a folder of that name holding the file, `omega_native.h` and the library |
| `work/` | the test driver | the generator and each unit's compiled code; not an interface |

Every file carries the unit's Omega signature line as a comment above its declaration, the five status
constants (0, 32, 33, 34, 35) and the parameter names prefixed `o_` (so no language's reserved words
collide). The scalar type is the language's unsigned 64-bit integer, an array is a pointer then a
`uint64_t` count, the status is unsigned 32-bit: C `uint64_t` / `void *` / `const void *`; Rust `u64` /
`*mut u64`, `*mut u8`, `*const u64`, `*const u8` (declared in an `unsafe extern "C"` block); Zig `u64` /
`?[*]u64`, `?[*]u8`, `?[*]const u64`, `?[*]const u8`; Go `uint64` / `unsafe.Pointer` to memory holding
no Go pointers. Python checks instead of trusting: a scalar is an `int` in 0 .. 2^64-1 (a `long` is
passed as its two's-complement bits) and anything else, including a negative or an out-of-range value,
raises `ctypes.ArgumentError` rather than being truncated; an array is a ctypes array of its element type
(`POINTER(c_uint64)` for `edit`/`view ulong`, `POINTER(c_ubyte)` for `edit uchar`, `c_char_p` for `view
uchar`, which also takes `bytes`), and an `edit` array must be writable, so `bytes` are refused there. The
result pointer is `uint64_t *`, `ctypes.POINTER(c_uint64)` (pass `ctypes.byref`), `*mut u64`, `?*u64`,
`*uint64`. The Go file wraps each C function as `Omega_<name>` so the caller needs no cgo of its own; its
preamble includes the generated header (so the Go side and the C side cannot disagree) and bakes in no
run-time path: the program's build names the folder (`CGO_LDFLAGS=-Wl,-rpath,<folder>`) or
`LD_LIBRARY_PATH` does.

Everything is produced in a scratch folder and installed together after the library compiles. A unit
outside the subset, or a name the binding cannot carry, is refused by name (exit 110): nothing is
installed and a previous run's outputs in OUTDIR stay as they were. The library is compiled with its own
header included (`-include omega_native.h`): a declaration that disagrees with a definition fails that
build, so the C file and the header cannot drift apart. The other four files are checked by the
qualification below, where each language builds its caller against its generated file only and a
one-word type change in the generator must make that build or run fail for the stated reason.

## Contract

| | |
|---|---|
| scalar argument | `uint64_t`, the canonical bits of its type; a `long` is its two's-complement bits (-3 is 18446744073709551613) |
| array argument | `void *` (`const void *` for `view`) then `uint64_t` element count, which must equal the declared length |
| result | written only on status 0; a `void` function writes 0 |
| status 0 | success |
| status 1..14 | the Omega trap code (1 overflow, 2 divide by zero, 3 bounds, 4 loop bound, 5 conversion, 6 resource, 7 shift, or a `trap N` code) |
| status 32 | foreign argument refused: null pointer, wrong length, misaligned, address overflow, a writable array overlapping any other array or the result |
| status 33 | reentry on the same thread (for example from a signal handler during a call) |
| status 34 | the code reached a runtime entry this ABI does not provide |
| status 35 | the binding could not map its stack for this thread |

Buffers stay owned by the caller and are borrowed for the call only; Omega keeps no address after it
returns. Writes made before a trap stay visible (no rollback). Calls on different threads are independent. The runtime table is one read-only table shared by
every call and thread (the code only reads it); a write to it would fault.

Stack: on its first call from a thread the binding maps 8 MiB of stack for that thread above an 8 MiB
no-access guard, and frees both when the thread exits. The caller's own stack size does not matter (a
4,000,000-byte local array runs from a 256 KiB C thread and a default 2 MiB Rust thread). A function-mode
unit has no call cycles and at most 4 MiB of local arrays per function, so a frame that would pass the
bottom starts inside the guard and the process faults there; memory below the guard is never written.
That fault is a crash, not a status: in function mode the seeded compiler does not check the stack
floor before reserving a frame (program mode traps 6 instead). A clean status needs that check in the
compiler; it is a compiler gap, not something the binding can add around the code.

Host words: a function-mode unit may use Omega host words (`read`, `write`, ...). They compile to Linux
system calls made directly by the code, on the calling process and its open descriptors.

Signals: a call from a signal handler while a call is running on the same thread returns 33. A handler
that leaves Omega code with `siglongjmp` abandons the call; every later call on that thread returns 33.

## Qualification (`OMEGA_NATIVE_OMC=<seed omc> sh tests/native/run.sh`)

The compiler is pinned by sha256 (`734f0a39319fbfa930bcc62cb30dbf06d47d78e126372b74f5baf478e6126b61`,
omega-mv PR #696). Expected values come from receipts, not from Omega:
(2^64-1)*2+5 mod 2^64 = 3 (calc:93e7b00a); 1311768467463790320*18364758544493064720+1085102592571150095
mod 2^64 = 3637949782307626511 (calc:9bf5b67e, Wolfram agrees); -13 as 64-bit bits = 18446744073709551603
(calc:cbb0735b); 0+1+...+999999 = 499999500000 (calc:3f197279).

The six callers (C, C++, Python, Rust, Zig, Go) take every Omega declaration from their generated file
(the run fails if any caller source declares an `omega_` function, sets ctypes `argtypes`, loads the
library itself or carries its own cgo). All six check values, wrap-around, signed bits, a signed overflow
trap with the result left unchanged, a trap after two buffer writes (writes visible, result unchanged), a
successful buffer call, a refused null result (C++: a wrong length) and the six-parameter unit `mix`
(`view`/`edit` `uchar` and `ulong` arrays, no result: success with the void result written as 0, a `trap
9` after two writes with the result unchanged, a conversion trap 5 after one write). The Python caller
also checks that the binding refuses 2^64+3, -1 and 2.0 as scalars and `bytes` for an `edit` array, and
that a call works after those refusals. The C caller also checks a null buffer, a wrong length,
misalignment, result/buffer overlap, a view overlapping an edit array, a call after traps, reentry from a
signal handler (status 33), a trap from a frame holding a 4,000,000-byte local array, that array on a
256 KiB thread, and that x19..x28 and d8..d15 keep the caller's values across a normal return and a trap.
The Rust caller runs the array on a default thread and is built twice, under edition 2021 and edition
2024, with warnings as errors. The C caller runs a second time against a library built with BTI enforced.
`tests/native/reference.c`, prototypes for the seven test units (with `hsum`, bound at its last function)
written by hand from this contract, is compiled with the generated header included: a disagreement is a
conflicting-types error. The generator
is shown to refuse a non-C unit name, a parameter ending in `_len` and a repeated unit name, and to accept
the same unit once; `tools/native` is shown to refuse a unit with a `uchar` result by name, with exit 110,
leaving a previous run's outputs untouched. Not exercised: status 34 and 35 (no supported unit reaches
another runtime entry; mapping failure is not induced).

Red before green (this change): with the generator of commit e7777ca, the C caller dies with SIGILL
under BTI, and the 4,000,000-byte array on a 2 MiB thread dies with SIGSEGV; with this generator both
pass. Extra receipts: 5+20+7 = 32 (calc:08302bc4), (7+1)+7 = 15 (calc:e44bce3f), 5+20+300 exceeds 255
by 70 (calc:a6a8bb76), 4,000,000 bytes is 0.954 of 4 MiB (calc:ffff21b2). Negative control: madd's `add` changed to
`sub` in the code must make the C caller fail.

Separate claims, not made here: source translation (ABI v0) and GPU execution are qualified on their
own. Only AArch64 Linux is supported.

Zig and Go: run with Zig 0.13.0 and Go 1.27.3 (official aarch64 archives, checksums from
ziglang.org/download/index.json and go.dev/dl, unpacked in the user's ~/.local/opt). Both callers pass
their checks (12 each in this change). The library is linked with `-soname libomega_native.so`: without that name, Zig records the
library as `./libomega_native.so` and the caller fails to load outside the build folder (red: dd8b9a9;
green: 1e40844). The embedded code is unchanged by the name.

Generated declarations (this change): before it, each caller typed its own prototypes and a wrong
type there was the caller's mistake to find. Now `tools/native` builds everything and the generator
writes the six files above from the parsed signatures; the C output is byte for byte what the previous
generator wrote. The run adds: the no-hand-declaration check; the hand-written reference prototypes;
the `tools/native` refusal; refusals of a missing and of an unknown output word; and five generator
mutants, one per binding, each changing one scalar type word on the generator's text line (`uint64_t`
to `uint32_t`, `c_uint64` to `c_uint32`, `u64` to `u32` twice, `uint64` to `uint32`). The run checks
that each mutant changes exactly one generator line and is caught for the stated reason: the header
mutant by the library build (`conflicting types for omega_madd`), the Python mutant by wrong results
(seven of the eighteen checks fail: the scalar is truncated to 32 bits), the Rust mutant by `mismatched
types`, the Zig mutant by `type 'u32' cannot represent integer value`, the Go mutant by `cannot use ...
as uint32 value`. Found by reading the output before the run, not by a test: the first Go wrapper
called `C.omega_(` with no name; the test that would have caught it is the Go build, which this
change runs. Review of the first version of this change led to: the Rust block declared `unsafe
extern` (edition 2024 rejects a plain `extern` block); Python scalars range-checked and arrays typed
per kind instead of `c_void_p` (which took `bytes` for a writable array and truncated scalars
silently); the Go preamble including the header instead of repeating prototypes, with no baked
run-time path; `tools/native` producing in a scratch folder, installing together, and naming the
refused unit.

## G1 sample (`OMEGA_NATIVE_OMC=<seed omc> sh tests/native/g1/run.sh`)

omega-mv #624 milestone G1: `fn calc i0 ulong i1 ulong to ulong` computing `(i0 + i1) * (i0 - i1)` modulo
2^64 with a `new ulong` SSA array in the lowering form of `spec/universal/translation-v1.md` section 5.
`OMEGA_G1_UNIT` names the unit: by default `tests/native/g1/calc.om` (hand-written, no semantic `note`
line); `tests/native/g1/calc.lowered.om` is the unit the omega-mv pipeline generated from C
(`c-import | lower`, producing command and commit in `tests/native/g1/README.md`). The bound function's
name and arity come from the unit's last `fn` line and must be `calc` with two inputs (what the callers
and the reference implement). `tools/native` builds it; the C, C++, Python, Rust, Zig and Go callers read
`i0 i1` lines and print `i0 i1 status result`, and each output must equal, line for line, the Python
bigint reference (`tests/native/g1/reference.py`) on 81 vectors: every ordered pair of 0, 1, 2, 2^32,
2^63-1, 2^63, 2^63+1, 2^64-2, 2^64-1. Negative control: the unit with its first `sub` changed to `add`
must disagree. The run writes `build/g1/manifest.json`: the unit, its function and arity; the source
identity (sha256 of the `.om` bytes); the semantic identity (section 4) when the unit's first line is
`note omega.universal.lower.v1 semantic <hex>`, else null; the omc, `src/native.om` and `tools/native`
sha256; the code, library and binding sha256; ISA aarch64, the ELF class and machine from `readelf -h`,
ABI `omega-native-v1`, OS Linux; and each caller's status (PASS, FAIL or NOT_RUN for a missing
toolchain) with its vector count and toolchain path.

## ABI v2: OM-2 units (omega-mv #747, contract `spec/omegese-om2.md` section 6, errata E1 and E5)

ABI v2 adds to every v1 rule and check above; nothing in v1 changes. An OM-2 unit is one whose first
line that is not a note (a line whose first word is `note`) is exactly `om2`; a first such line that
starts with the word `om2` but is not exactly `om2` (`om2 diag`, `om2 fmt`) is refused. Every other
unit is OM-1 and gets the v1 binding, byte for byte what the generator of 3f05908 writes (checked on
every unit in `tests/native` and `tests/native/g1`, alone and as the v1 suite's set, in all six outputs).

**Symbols.** Every OM-2 unit is bound as v2, whatever its parameter kinds (erratum E1): each
`export fn NAME` (source order) gets `uint32_t omega2_NAME(uint64_t *result, ...)`; without any
`export`, the last `fn` is bound (the v1 rule). No `omega_NAME` is emitted for an OM-2 unit, so a caller
built from v1 declarations fails to link (the explicit refusal), and every binding names the v2 symbol.
Functions that are not exported stay private: no symbol. All exports of a unit share its embedded code
and the library's one runtime (stack, table, reentry flag). Bound names (v1 unit names and v2 exports)
share one table: a repeat is refused.

**Calling convention** (agreed with the OM-2 compiler lane, omega-mv S4, ledger L834). Parameters go to
x0..x5 in order, result in x0, runtime table in x7, trap through entry 2 with its code in x1 (as v1):

| Omega parameter | slots | C argument(s) | checks before any Omega code runs (status 32) |
|---|---|---|---|
| `x ulong`, `x long` | 1 | `uint64_t o_x` (a long is its two's-complement bits) | none |
| `a view T *`, `a edit T *` (unsized) | 2: pointer, then the element count | `const T *o_a` (`T *o_a` for edit), `uint64_t o_a_len` | if `len > 0`: not NULL; aligned to sizeof(T); `len * sizeof(T)` fits in 64 bits; `ptr + len*sizeof(T)` does not wrap (the end may be at most 2^64-1). `len == 0` is the empty view with any pointer, NULL included, and adds no range |
| `a view T N`, `a edit T N` (sized) | 1 | `const T *o_a` / `T *o_a`, `uint64_t o_a_len` | the v1 checks: not NULL, count == N, aligned, no wrap |
| `c view L`, `c edit L` (layout `L` of SIZE bytes) | 1 | `const uint8_t *o_c` / `uint8_t *o_c` | not NULL; no wrap (alignment 1) |
| `o out T N` | 1 | `T *o_o` (no count; erratum E1) | not NULL; aligned to sizeof(T); no wrap |

T is any of `uchar ushort uint ulong byte short int long` (C `uint8_t` .. `int64_t`). At most 6 slots;
the result is `ulong`, `long` or `void`; parameter names follow the v1 rules (C identifier, no `_len`
ending). **Overlap** (half-open ranges, empty ranges excluded): refused when an `edit` range (arrays and
layouts) or the result buffer overlaps any other range, or two `out` ranges overlap; an `out` range may
overlap a view. Status 33 keeps its v1 meaning (reentry); 34 and 35 as v1.

**Outputs.** Each `out` parameter is a buffer the binding owns, carved from the top of the calling
thread's Omega stack, 16-byte aligned and zero-filled before the call, passed in its slot. Only after
status 0 is it copied to the caller's pointer with `memmove`, so it may overlap the inputs
(`sha256_hash(buf, n, buf)`), and nothing is written there on a trap or refusal. The generator refuses
more than 65536 out bytes per export (they come out of the 8 MiB thread stack).

**Multi-entry code.** With exports, words 0 .. E-1 of the unit's code are `b <export k>` (E <= 32, the
compiler's limit); the binding enters export k at byte 4k, through its own `bti c` stub. The generator
refuses code shorter than 4E bytes.

**Identity.** Each OM-2 binding embeds `omega-ident 1 unit=U abi=2 profile=OM-2 src=S omc=C`: U the
unit's file basename with every byte outside `[A-Za-z0-9_]` made `_` (`sha256-om2.om` gives
`sha256_om2`), S the sha256 of the unit's exact source bytes, computed by `src/native.om` itself (a
FIPS 180-4 SHA-256 in Omega), C the sha256 of the compiler that wrote the code (`OMEGA_NATIVE_OMC2`),
supplied by `tools/native` (contract C3: the compiler does not report its own identity). The library
exports `const char *omega2_ident_U(void)`; each binding carries the expected string: C/C++
`OMEGA2_IDENT_U`, Python `OMEGA2_IDENT_U` (bytes; importing the module raises `ImportError` when the
library's string differs), Rust `OMEGA2_IDENT_U: &str`, Zig `OMEGA2_IDENT_U`, Go `Omega2Ident_U` and
`Omega2_ident_U()`. OM-1 units embed no identity (their bindings stay byte-identical); `tools/native`
writes every unit's identity, the OM-1 ones with `abi=1 profile=OM-1` and the pinned omc, to
`work/ident.txt` (harness-side; `om/units.sh --check` in omega-mv refuses a stale unit).

**Generator input.** An OM-2 unit's frame is the v1 frame followed by the line
`omega-unit U C\n` (U a C identifier, new in the set; C 64 lowercase hex digits); a missing or
malformed line is refused. Layouts are read from `layout NAME SIZE` lines (SIZE 1..4096, at most 32).
Two `note` forms are read by the bridge (and are comments to the compiler): `note bridge c-type L CNAME`
names layout L's C struct type, `note bridge c-define NAME DIGITS` adds a `#define` to the API header;
any other `note bridge` line is refused.

**API header** (`omega_api.h`, output word `api`, installed only when the set has an OM-2 unit). It
includes `omega_native.h` and gives each layout as `typedef struct { ... } CNAME;` with every field at
its declared offset (explicit `uint8_t ombr_padN[...]` padding; a field without COUNT is a scalar, with
a COUNT an array, even COUNT 1 (erratum E5); a big-endian or misaligned field is bytes), checked by
`sizeof` and `offsetof` static assertions that `tools/native` compiles; and each export as
`static inline` C function named exactly as the export, with C types (`const T *, size_t` for an
unsized view, `CNAME *` for a layout, `T [N]` for out), calling `omega2_NAME` and calling `abort()` on a
nonzero status. This is how the C names of a consumer API (for example `sha256_init`) come from the
bridge rather than from handwritten C.

**Out-of-line API** (output words `apih` and `apic`, installed as `omega_api_decl.h` and
`omega_api_defs.c` beside `omega_api.h`), for a consumer that must not reference the C library from the
objects that use the API (a freestanding object: an inline wrapper puts an `abort` reference into every
object that includes `omega_api.h`). `omega_api_decl.h` holds the same layouts, defines and static
assertions and only the prototypes of the same C functions (external linkage, no `stdlib.h`); an object
including it references only the API functions it calls. `omega_api_defs.c` includes it and `stdlib.h`
and holds their definitions, each calling `omega2_NAME` and `abort()` on a nonzero status, exactly as
the inline ones; it is compiled into the consumer's hosted binding (for the SHA cutover, the generated
`src/omega_om_units.c`). `tools/native` compiles the header alone and the definitions against it
(`-Wmissing-prototypes -Werror`). `omega_api.h` is unchanged, byte for byte. Use one form or the
other in a program, not both: each defines the functions under the same names.

**Unsupported (caller precondition, not detected),** as the contract states: that the memory exists for
`len` elements, is writable for edit, or stays alive during the call; forged lengths and read-only
memory passed as edit. Function-mode stack exhaustion faults as in v1. Loops in the seeded compiler
run at most 1,000,000 passes (trap 4 beyond); a unit over a longer view must loop in parts (`part`).

### Qualification (`OMEGA_NATIVE_OMC=<seed omc> OMEGA_NATIVE_OMC2=<OM-2 omc> sh tests/native/v2/run.sh [measure]`)

Recorded with the OM-2 compiler of omega-mv `om2/compiler-s4` @ f6a6492fd (draft PR #764, ledger L834),
sha256 `499236398aabc652e2dae27fe4bdc4c5db3d3726314356e0dbef23e3345803ec`, which compiles the three OM-2
test units `tests/native/v2/{vec,lay,one}.om`; that digest is the `omc=` of their identities. Its code
follows the convention above with no departure found: the entry table (vec: six `b` words), the slots
and element counts, the out pointers, and the traps the callers expect (the `part` checks in the
contract's order, element bounds, trap 9 after an out write). Before S4 existed the bridge was developed
against hand-written OM-1 stand-ins of these units (commit 1392549); they are removed.

The run checks: v1 byte identity (above); every identity string against `sha256sum` (oracle); the
embedded code against the compiler's bytes; the exact exported symbol set (15 `omega2_` symbols, 12
exports and 3 identities, and `omega_madd`; no private helper, no v1 name for a v2 unit); no caller
declaring an Omega function by hand; the C caller (64 checks) normally and with BTI enforced; the C++,
Python, Rust (2021 and 2024), Zig and Go callers (16 to 18 checks each); the link-time refusal in all six
languages (v1 bindings of an OM-1 unit named `bsum` against the library: `undefined reference to
omega_bsum`, Python `undefined symbol: omega_bsum`); the stale identity (a header from `vec.om` with one
note byte changed is detected; its Python binding refuses to import; the matching header passes); 15
generator refusals of OM-2 input with a control; and three negative controls (the wrap check, the
edit-overlap rule and the out copy each removed from a copy of the generator must make the C caller
fail, on the checks named).

The C caller covers: values; empty views (NULL, misaligned); NULL with len 1; misalignment by 1, 2 and
4 for 4- and 8-byte elements and an edit; `len*size` overflow (2^62 x 4, 2^61 x 8, 2^64-1); address wrap
at 2^64-16 (end 2^64 refused, end 2^64-8 accepted); a 2^32+5-element length accepted and passed whole
(PROT_NONE mapping, no element read); the #748 golden at the boundary (len 2^64-1, o 2^64-2, k 4: 32)
and inside the code (len 16, o 2^64-2, k 4: trap 3, the wrapped `o + k` never used), every (o, k) in
0..18 over 16 bytes; splits at every point of 64 bytes; 16 MiB of bytes and 64 MiB of words against a C
reference; edit == view, overlap by one element, adjacent ranges, empty ranges, the result inside an
edit or a view; the layout through `omega_api.h`; out overlapping a view (in-place reverse) and its own
layout view; two outs adjacent, overlapping by one byte and at one address; out untouched after a
trap; NULL and misaligned out; 2000 interleaved rounds across the three separately compiled OM-2 units
and the OM-1 `madd` in one binary (module boundary); reentry from a signal handler (33); two threads
with their own stacks and out buffers.

Caller cost (HOST, `run.sh measure`, GB10 host CPU under load average 7-11 from other work, lowest of 7
runs, ns per call, two runs, S4 code):

| call | ns |
|---|---|
| refused (argument checks only, no entry) | 2.6-3.1 |
| one view, code returns its len (checks, entry, register saves, stack switch) | 8.0-8.2 |
| empty view to `bsum` (its chunk loop runs once and calls `psum`) | 9.8 |
| ABI v1, three scalars (baseline) | 5.2-6.1 |
| a plain noinline C call (scale) | 1.4 |
| one view and an 8-byte out (zero, run, memmove) | 14.3-15.0 |
| 16-byte view sum (scalar C loop 4.9) | 15.0-15.5 |
| 4 KiB view sum: 0.346 ns/B (C 0.258) | 1418 |
| 16 MiB view sum: 0.379-0.384 ns/B (C 0.291-0.295) | 6.4 ms |
| a thread's first call (maps its 8 MiB stack and 8 MiB guard), then the second | 11.5-12.4 us, 64 |

The fixed v2 overhead over a plain C call is about 6.6 ns (checks about 1.5, entry and stack switch
about 5), about 2 ns over v1 for one view; an out costs its zeroing and copy. Memory: 16 MiB of
NORESERVE address space per calling thread; the RSS did not change at KiB resolution over a new thread's
first two calls.

Not run: status 34 and 35 (as v1).
