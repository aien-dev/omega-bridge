# L720 native Qwen3-8B consumer work

**Incomplete. There is no 8B model server or Renda cutover.**
The compiler/device/transport dependencies are recorded in
[requests/owners.md](requests/owners.md); L720 stays open.

All newly authored code and tests are `.om` compiled by the supplied immutable
machine-code seed descendant. Nothing uses the repository's generated C/Python
bridge or the superseded Rust worktree. Shell, Git, coreutils, jq, readelf and
nvdisasm are existing inspection/build tools, never the forward pass.

Implemented consumer components:

| Source | Behavior and qualification limit |
|---|---|
| numeric.om | E4M3FN and BF16 conversion over binary32 bits, ties-to-even, saturation and signed zeros. Host-native codec only. |
| checkpoint.om | Strict exact-model tensor names, dimensions, types, scale orientation, contiguous ranges, duplicates, overflow and complete651-tensor inventory. Errors latch until reset. |
| inspect.om | Reads both actual safetensors headers through inherited fd3/fd4 and runs descriptor admission. Does not load or hash tensor payloads. |
| geometry.om | Grouped-query head mapping, KV addressing, FP8 scale indexing, split-half RoPE pairing and finite-logit greedy argmax with first-index ties. No attention or RoPE arithmetic. |
| kernels.om | Handwritten sm121 f32 residual-add and elementwise-product instructions, emitted as explicitly nonlaunchable LAB capsules. |
| tests/mutate.om | Native source-mutation harness, fails unless the requested substitution occurs exactly once. |

Unmodified JSON source is vendored from L690
30762489ee1fc4e0ceed02310bb6f19b0d128b00, native/hermes/src/json.om,
SHA2565dbdd1fbc9996ff1aad5b2a2e05e58af2d3f343108eac5d241e79f956a844191.
Its bounds remain65536 bytes/4096 tokens/32 nesting levels. Checkpoint admission
reuses its parser one root entry at a time, so the full header's token count does
not require changing the shared parser or its owner tree.

The exact checkpoint is Qwen/Qwen3-8B-FP8 revision
220b46e3b2180893580a4454f21f22d3ebb187d3, `/home/drakestapleton/models/qwen3-8b-fp8`.
External sha256sum reverified all12 files against the saved manifest. Native
inspection validated all651 descriptors, covering all36 layers and the embedding,
final norm and separate output head. Tensor bytes are9,436,551,168 across both
shards. Descriptor offsets are relative to each shard's payload, not file start.
Header sizes are42024/35576; payloads4953198592/4483352576 bytes.

This validator intentionally accepts the pinned checkpoint's canonical ASCII
names and contiguous descriptor order. Escaped names, unknown tensors, extra
descriptor fields, alternative quantization and unordered storage are refused.
It is not a general safetensors reader. `admit` describes metadata only; it does
not authorize executing model bytes. Consumers must check every return status,
the final admission bit, external file identity and payload integrity.

Tokenization remains unimplemented. The audited tokenizer uses NFC normalization,
Unicode regex pretokenization and byte-level BPE with151643 entries,151387 merges,
26 added tokens. The embedding/head have151936 rows, so vocabulary-entry count
must not be mistaken for matrix dimension. Tool/chat rendering needs the pinned
Qwen template, including actual tool-call/result continuation. No canned model
answer, tool call or tokenization fixture is represented as live behavior.

## Kernel boundary

The immutable reference fixture is seed/sm121/vecadd.bin from Omega
57f5f4258cebf3d5b2c22853cd062e351265c525, SHA256
39f3dfdfc529a75a8274a27900acf4e7382b7f280a211e0412c51609f44b62a1.
Handwritten kernel prologue/load/store/exit bytes match that fixture. The one
arithmetic instruction becomes FADD or FMUL, waiting on the original load
scoreboard and stalling6 cycles before its store. Encoding and scheduling fields
were read from that pin's sm121.tbl and the historical elementwise scheduler.
No historical C source or compiler is executed to produce these artifacts.

VECTOR_1D constants: descriptor0x358, blocksize0x360, a0x380, b0x388, out0x390,
uint32 length0x398. Inputs/outputs are f32 contiguous arrays. There are no
reductions, barriers, tensor cores, matrix multiplication or GPU allocation here.
Capsule schema matches L605: OMGP/schema1/arch121/flags1/LAB ONLY,512 code bytes,
10 registers,28 parameter bytes,2 inputs. A one-byte selector0/1 to kernel-cli
emits add/product; any other selector refuses. No launch command exists.

Byte checks and independent nvdisasm establish encoding, not GPU behavior,
memory safety, scheduling correctness or performance. Full numeric goldens,
GPU mutants, payload transfer and native launcher acceptance remain NOT_RUN.

## Reproduction

Use a private output directory and verify `omc` equals SHA256
191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9 before building.
The supplied artifact was verified then copied read-only into the L720 handoff
inputs directory; the original was never modified. The source lineage is
load0 -> seed0 -> hex1 -> asm2 -> om4 -> omc stage1 -> omc stage2, as qualified
in L694 and omega-bridge0fc7d866. This task did not rerun the full seed bootstrap.

Concatenate each row's files in order, send the result on compiler stdin and save
stdout as the executable. Require successful compilation, nonempty AArch64 static
ELF and executable permission before running. Existing `quiet-build` schedules
CPU work; its lock worked here but its shared wait-log write was read-only.

| Program | Files under native/renda8b, in order |
|---|---|
| numeric | numeric.om, tests/report.om, tests/numeric.om |
| checkpoint | vendor/json.om, checkpoint.om, tests/report.om, tests/checkpoint.om |
| geometry | geometry.om, tests/report.om, tests/geometry.om |
| kernels | kernels.om, tests/report.om, tests/kernels.om |
| inspect | vendor/json.om, checkpoint.om, inspect.om |
| kernel-cli | kernels.om, kernel-cli.om |
| mutate | tests/mutate.om |

Run kernels with fd3 opened on fixtures/seed-vecadd.bin. Run inspect with fd3/fd4
opened on the two model shards in order. The shell opens files; the compiled
Omega reader performs all header parsing and validation. Numeric/checkpoint/
geometry tests need no input. Test lines are ID followed by0 for pass/1 for fail;
exit1 means any check failed. Mutation input is one selector byte0..5 followed by
the combined suite source; compile its output and require test exit1. Selectors
damage FP8 ties, BF16 ties, shape validation, GQA mapping, greedy tie handling and
kernel addition respectively. A compiler failure does not count as a caught mutant.

## Remaining implementation and acceptance

FP8 scaling arithmetic, RMSNorm/QK norm, full RoPE, attention/KV execution,
projection/head matrix multiplication, SwiGLU, device storage and full forward are
unimplemented. So are full tokenizer, config/model loader, HTTP/SSE/tools and
caller routing. These are substantive remaining work, not merely deployment.
Need independent frozen full-model goldens and hardware negative controls after
the existing owners supply qualified execution interfaces. No speed measurement
or model-quality result is claimed. See evidence/renda8b-L720 for actual results.
