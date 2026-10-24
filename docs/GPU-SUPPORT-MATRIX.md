# GPU support matrix (2026-10-23)

Status vocabulary is literal. `PASS` means the named test ran on this host and
its raw output is in `evidence/`. `NOT_RUN` means no result exists; it is not a
pass. `BLOCKED` names the blocking condition. No row claims cross-vendor or
cross-context execution without a test.

| Area | What is measured | Status | Evidence / blocker |
|---|---|---|---|
| Bridge fake GPU adapter | Deterministic negotiate + refusal round-trip, 47 checks | **PASS (host)** | `evidence/MAX-INTEROP/3/tests.log` |
| GB10 adapter negotiation | Adapter/ISA/driver/ABI/capability/rights/sync/telemetry admission | **PASS (host)** | `evidence/MAX-INTEROP/3/tests.log` |
| GB10 artifact admission | Contract/artifact id, cubin format, zero-VA QMD, fresh receipt, producer ownership, no alias | **PASS (host)** | same |
| CUDApp sm_121 artifact export | ELF cubin, text/QMD/cbank SHA-256, deterministic bytes, 42 checks | **PASS (offline)** | `cudapp/evidence/MAX-INTEROP/68/` |
| Cubin structural validity | `nvdisasm -c`, `cuobjdump -res-usage` accept the container and show the generated text | **PASS (offline)** | `cudapp/evidence/MAX-INTEROP/68/smoke.log` |
| Cubin device load (`cuModuleLoadData`) | Load the exported cubin on GB10 | **NOT_RUN** | GPU reserved by coordinator (`CHIP-RESERVED`); no window authorized |
| Cubin device execution + numeric parity | Launch the exported matmul/attention cubin and compare to the independent oracle | **NOT_RUN** | same |
| MAX 26.7.0 sensitivity/probe | `max.driver` surface, device count/api, pinned-source capability map | **PASS (host, no launch)** | `docs/max/MAX-26.7-FEASIBILITY.md` |
| MAX 26.7.0 graph matmul on CPU | Harness wiring, f32 accumulation of exact bf16 values | **PASS (harness)** | `evidence/MAX-INTEROP/5/harness.log` |
| MAX 26.7.0 graph matmul on GB10 | Independent MAX graph execution, separate process | **NOT_RUN** | same GPU reservation |
| MAX 26.7.0 causal GQA on CPU | Harness wiring, fp32 softmax path | **PASS (harness)** | same log |
| MAX 26.7.0 attention on GB10 | Independent MAX graph execution | **NOT_RUN** | same |
| Cross-runtime envelope + C2 receipt | Structural binding, TEST signature, stale/tamper refusal | **PASS (host)** | `omega-mv/evidence/MAX-INTEROP/681/` |
| In-MAX native Omega cubin | Supported graph-level invocation | **BLOCKED / REQUIRES_MODULAR_CHANGE** | At the pin, no public module-load API; `DeviceContext.load_function` takes `String` and only PTX is tested. Raw cubin acceptance is `UNKNOWN`. The main-branch HAL bundle path accepts cubin, but it is not in the pinned release, is not the production path, and is not reachable from public Python. See `docs/max/MAX-26.7-FEASIBILITY.md` §5.6, §8, §11. |
| AMD / Intel / Metal adapters | Any execution | **NOT_RUN** | No adapter implementation; no hardware test |

## Dependency and policy honesty

- MAX on NVIDIA is **not CUDA-free**: its CUDA backend loads `libcuda.so.1`, and
  the pinned documentation requires driver 580 / CUDA 13.0 or later. Omega's own
  native path is CUDA-free; that fact does not transfer to MAX.
- CUDApp is AGPL-3.0-only. MAX source is Apache-2.0-with-LLVM-exceptions or the
  MAX Community License depending on path. No CUDApp source is copied into MAX
  directories; any upstream contribution needs its own licence review.
- The artifact exporter writes no device address and opens no device. Device
  identity, load result and numeric parity must be added by an admitting loader
  in its own receipt.
- No performance number is reported for a `NOT_RUN` row.
