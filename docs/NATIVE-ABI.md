# Native call ABI v1

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
- gives the code a 32-entry runtime table whose trap entry restores the caller's stack pointer from x19
  and returns the trap code from the exported function (no setjmp/longjmp, nothing crosses the caller's
  frame) and whose other entries refuse with status 34, since function-mode units of this ABI use none
  of them. This relies on the seeded compiler never writing x19..x28 (OSC-1 uses x0..x16, x29, x30);
- reaches each unit through a two-instruction stub (`bti c`, branch) so the code runs under branch
  target identification (BTI) without changing the compiler's bytes;
- exports, per unit, `uint32_t omega_<name>(uint64_t *result, ...)`.

Names must be C identifiers, a parameter name may not end in `_len` (the binding names a length
`o_<name>_len`), and each unit name appears once; anything else is refused before any C is written.

Supported signatures: up to 6 parameters, each `ulong`, `long`, or `edit`/`view` of `ulong` or `uchar`
with a fixed length; result `ulong`, `long` or `void`; one function per unit.

## The declarations for each language (`tools/native`)

`OMEGA_NATIVE_OMC=<seed omc> tools/native OUTDIR unit.om...` compiles the units with the pinned
compiler, runs the generator once per output word and writes, into OUTDIR:

| file | for | how a program uses it |
|---|---|---|
| `omega_native.c` | the library source | built into `libomega_native.so` by the same command |
| `omega_native.h` | C and C++ | `#include "omega_native.h"` (`extern "C"` inside for C++) |
| `omega_native.py` | Python 3 (ctypes) | `import omega_native`; loads `libomega_native.so` from beside itself |
| `omega_native.rs` | Rust | `mod omega_native;` beside the crate root; link with `-L OUTDIR` |
| `omega_native.zig` | Zig 0.13 | `@import("omega_native.zig")`; build with `-L OUTDIR -lomega_native -lc` |
| `omega_native.go` | Go (cgo) | package `omeganative`: a folder of that name holding the file and the library |

Every file carries the unit's Omega signature line as a comment above its declaration, the five status
constants (0, 32, 33, 34, 35) and the parameter names prefixed `o_` (so no language's reserved words
collide). The scalar type is the language's unsigned 64-bit integer, an array is a pointer then a
`uint64_t` count, the status is unsigned 32-bit: C `uint64_t` / `void *` / `const void *`; Python
`ctypes.c_uint64` / `ctypes.c_void_p` (any ctypes array or address); Rust `u64` / `*mut u64`, `*mut u8`,
`*const u64`, `*const u8`; Zig `u64` / `?[*]u64`, `?[*]u8`, `?[*]const u64`, `?[*]const u8`; Go
`uint64` / `unsafe.Pointer` to memory holding no Go pointers. The result pointer is `uint64_t *`,
`ctypes.POINTER(c_uint64)` (pass `ctypes.byref`), `*mut u64`, `?*u64`, `*uint64`. The Go file wraps
each C function as `Omega_<name>` so the caller needs no cgo of its own.

All six files are generated before any is written, so a refused unit leaves OUTDIR without a half set.
The library is compiled with its own header included (`-include omega_native.h`): a declaration that
disagrees with a definition fails that build, so the C file and the header cannot drift apart. The
other four files are checked by the qualification below, where each language builds its caller against
its generated file only and a one-word type change in the generator must make that build or run fail.

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
returns. Writes made before a trap stay visible (no rollback). Calls on different threads are independent; each
call has its own runtime table.

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
library itself or carries its own cgo). They check values, wrap-around, signed bits, a signed overflow trap with
the result left unchanged, a trap after two buffer writes (writes visible, result unchanged), a
successful buffer call and a refused null result. The C caller also checks a null buffer, a wrong length,
misalignment, result/buffer overlap, a view overlapping an edit array, a call after traps, reentry from a
signal handler (status 33), a six-parameter unit with `view`/`edit` `uchar` and `ulong` arrays and no
result (success, a `trap 9` after two writes, a conversion trap 5 after one write), a trap from a frame
holding a 4,000,000-byte local array, that array on a 256 KiB thread, and that x19..x28 and d8..d15 keep
the caller's values across a normal return and a trap. The Rust caller runs the array on a default
thread. The C caller runs a second time against a library built with BTI enforced. The generator is
shown to refuse a non-C unit name, a parameter ending in `_len` and a repeated unit name, and to accept
the same unit once. Not exercised: status 34 and 35 (no supported unit reaches another runtime entry;
mapping failure is not induced).

Red before green (this change): with the generator of commit e7777ca, the C caller dies with SIGILL
under BTI, and the 4,000,000-byte array on a 2 MiB thread dies with SIGSEGV; with this generator both
pass. Extra receipts: 5+20+7 = 32 (calc:08302bc4), (7+1)+7 = 15 (calc:e44bce3f), 5+20+300 exceeds 255
by 70 (calc:a6a8bb76), 4,000,000 bytes is 0.954 of 4 MiB (calc:ffff21b2). Negative control: madd's `add` changed to
`sub` in the code must make the C caller fail.

Separate claims, not made here: source translation (ABI v0) and GPU execution are qualified on their
own. Only AArch64 Linux is supported.

Zig and Go: run with Zig 0.13.0 and Go 1.27.3 (official aarch64 archives, checksums from
ziglang.org/download/index.json and go.dev/dl, unpacked in the user's ~/.local/opt). Both callers pass
10 checks. The library is linked with `-soname libomega_native.so`: without that name, Zig records the
library as `./libomega_native.so` and the caller fails to load outside the build folder (red: dd8b9a9;
green: 1e40844). The embedded code is unchanged by the name.

Generated declarations (this change): before it, each caller typed its own prototypes and a wrong
type there was the caller's mistake to find. Now `tools/native` builds everything and the generator
writes the six files above from the parsed signatures; the C output is byte for byte what the previous
generator wrote. The run adds: the no-hand-declaration check; refusals of a missing and of an unknown
output word; and five generator mutants, one per binding, each changing one scalar type word in the
generator's text (`uint64_t` to `uint32_t`, `c_uint64` to `c_uint32`, `u64` to `u32` twice, `uint64`
to `uint32`). Each is caught: the header mutant by the library build (`conflicting types for
omega_madd`), the Python mutant by wrong results (two of the ten checks fail: the argument is
truncated to 32 bits), the Rust, Zig and Go mutants by their compilers (a 64-bit value passed to a
32-bit parameter). Found by reading the output before the run, not by a test: the first Go wrapper
called `C.omega_(` with no name; the test that would have caught it is the Go build, which this
change runs.
