# Native sm121 backend: offline lab target

This extends the native CUDA C++ frontend toward the [entirely Omega replacement
programme](PROGRAM.md). It emits **real sm_121 instruction bytes**, not another
CPU program, PTX, generated C, an nvcc subprocess or a stored vector-add output.
Every accepted expression node is lowered to actual register instructions.

It is **offline lab code, not qualified GPU execution**. No hardware scheduling,
launcher, GPU source-checker proof, runtime attachment or live consumer cutover is
claimed. The installed command refuses `run --target sm_121-lab`. The production
`sm_121` target still refuses. No driver, module, firmware or model was touched.

## Commands

```sh
om check --from cuda-cpp --target sm_121-lab kernel.cu
om build --from cuda-cpp --target sm_121-lab kernel.cu -o kernel.omgpu
# Intentionally refused, exit 69:
om run --from cuda-cpp --target sm_121-lab kernel.cu
```

Build output is private mode600 **data**, not a host ELF, cubin, or executable.
All normal source snapshot, source-inode collision, destination symlink refusal
and atomic publication rules remain. Failed frontend/ABI/target requests preserve
existing destinations. CPU simulation still requires `--target cpu-sim`; no CPU
fallback is used for this target.

## Source and launch ABI

The [CUDA C++ profile](CUDA-CPP.md) remains bounded unsigned-int32 elementwise
kernels. This target currently requires **two** const input buffers plus output
and length; CPU simulation retains one through four inputs. Other GPU arities
refuse before any artifact is emitted. Parameters are mapped by their declarations,
not literal source names. Operators `+ - * & ^ |`, unsigned constants, input values
and the length parameter compile; precedence and wrap-at-each-operation semantics
remain those of the selected profile. SSA nodes use distinct registers R16 upward,
bounded by the parser's128-node cap. This is not a production register allocator.

The prologue is inherited from the pinned chip-proven vector kernel. The fixed
VECTOR_1D constant-bank ABI is: descriptor0x358, block size0x360, inputA0x380,
inputB0x388, output0x390, uint32 length0x398. An added LDC snapshots length into R8
before UR4:UR5 is reused for the memory descriptor. The known final load consumer
is retained before arbitrary arithmetic. This mechanism and its instruction words
are tested offline; the new instruction scheduling and added length load still
need real-device qualification. A byte-for-byte canonical encoding comparison or
an arithmetic interpreter cannot prove timing, dependency stalls or warp safety.

Canonical source read as an external reference:
CUDApp `232332422bfdc31c8918085b50f13c1e18ab702e`,
`src/omega_blackwell_encoder.c` and `src/omega_blackwell_codegen.c`.
The seed vector reference is Omega seed/omega-in-omega `57f5f425`'s
`seed/sm121/vecadd.bin`, SHA256
`39f3dfdfc529a75a8274a27900acf4e7382b7f280a211e0412c51609f44b62a1`.
The production backend is handwritten Omega and reads neither reference at runtime.
Canonical C and GNU C++ are test-only oracles, never product dependencies.

## Capsule schema1

All fields are little-endian. The32-byte header is:

| Offset | Field |
|---|---|
| 0 | ASCII `OMGP` |
| 4 | uint32 schema1 |
| 8 | uint32 architecture121 |
| 12 | uint32 flags1, **LAB ONLY, LAUNCH PROHIBITED** |
| 16 | uint32 following code byte length |
| 20 | uint32 declared register count |
| 24 | uint32 parameter byte length28 |
| 28 | uint32 const input count2 |

Code consists of128-bit instructions, padded to128-byte alignment, at least512
bytes. A final EXIT and branch-to-self guard precede NOP padding. Header fields
are declarations, not a proof or launch authorization. This capsule has no signed
receipt or attached checker proof. Future runtime work must not accept the lab
flag as a production executable. It must separately validate code, ABI, device,
allocation bounds, resource admission and the exact immutable qualified candidate.

## Frontend protocol and construction

The private native frontend's stdin is now one selector byte (`C` CPU source
lowering or `G` lab GPU emission), followed by the original CUDA source bytes.
The installed shell dispatcher inserts it outside the snapshotted source; the
source's full16384-byte bound is unchanged. This is an internal framing protocol,
not a new legal CUDA source prefix. Public `om` syntax and CPU results are unchanged.
The builder concatenates `src/cuda-cpp.om` and `src/cuda-sm121.om`, then uses the
same reconstructed seed compiler. No foreign compiler constructs either backend.

## Offline tests

```sh
# Full suite additionally needs this local clone only as an external test oracle.
CUDA_CPP_CUDAPP_SOURCE=/path/to/canonical/CUDApp tools/test-native.sh
```

The test-only oracle builder archives the exact CUDApp pin, compiles its unchanged
encoder in private output space and never links it into Omega. The GPU gate checks
all emitted arithmetic instructions against that encoder, including scheduling
words. It checks the prologue against the pinned seed bytes with the separately
verified length-load insertion. A separate binary instruction decoder/evaluator
then compares generated instructions against **compiled original C++**, with
boundary unsigned values, varied dimensions and uncovered-output preservation.
Actual compiled semantic mutants must still produce decodable kernels and differ
from the independent original-source result. Wrong magic/size/prefix and unsupported
GPU ABI arities are refusal controls.

These are finite **offline encoding and arithmetic** checks. They are not hardware,
parallel correctness, performance, full CUDA C++, a native runtime, or proof that
Omega can yet replace the whole CUDA stack. The programme stays open until the
source-to-real-device path and actual caller/dependency retirement pass.
