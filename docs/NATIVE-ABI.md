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
decimal digits, the code) and writes one C file. Output appears only after every unit is accepted;
anything outside the supported signature set is refused (exit 110, no output). The C file:

- embeds each unit's code byte for byte (tests/native/run.sh compares the bytes inside the built
  library with the compiler's output);
- enters the code through a small trampoline that saves the callee-saved registers x19..x28 and
  d8..d15, sets x7 and loads the arguments;
- gives the code a 32-entry runtime table whose trap entry returns control to the exported function
  (setjmp/longjmp inside the binding; nothing crosses the caller's frame) and whose other entries
  refuse with status 34, since function-mode units of this ABI use none of them;
- exports, per unit, `uint32_t omega_<name>(uint64_t *result, ...)`.

Supported signatures: up to 6 parameters, each `ulong`, `long`, or `edit`/`view` of `ulong` or `uchar`
with a fixed length; result `ulong`, `long` or `void`; one function per unit.

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

Buffers stay owned by the caller and are borrowed for the call only; Omega keeps no address after it
returns. Writes made before a trap stay visible (no rollback). The caller supplies an 8 MiB stack, as in
ABI v0. Calls on different threads are independent; each call has its own runtime table.

## Qualification (`OMEGA_NATIVE_OMC=<seed omc> sh tests/native/run.sh`)

The compiler is pinned by sha256 (`d0603ff8fc276774ac7b438c27d146123b9a4513547fe9671e36d8e02d183e83`,
omega-mv PR #696). Expected values come from receipts, not from Omega:
(2^64-1)*2+5 mod 2^64 = 3 (calc:93e7b00a); 1311768467463790320*18364758544493064720+1085102592571150095
mod 2^64 = 3637949782307626511 (calc:9bf5b67e, Wolfram agrees); -13 as 64-bit bits = 18446744073709551603
(calc:cbb0735b); 0+1+...+999999 = 499999500000 (calc:3f197279).

Each caller checks values, wrap-around, signed bits, a signed overflow trap with the result left
unchanged, a bounds-style trap after two buffer writes (writes visible, result unchanged), a successful
buffer call, and refused arguments. The C caller also checks misalignment, result/buffer overlap, a call
after traps, and reentry from a signal handler (status 33). Negative control: madd's `add` changed to
`sub` in the code must make the C caller fail.

Separate claims, not made here: source translation (ABI v0) and GPU execution are qualified on their
own. Zig and Go callers exist (tests/native/caller.zig, caller.go) and are NOT_RUN until those
toolchains are installed. Only AArch64 Linux is supported.
