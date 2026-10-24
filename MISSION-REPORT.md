# Omega × Modular MAX — verified interoperability, current state

Date: 2026-10-23. This is the consolidated report for the three branches. It
separates what ran from what did not. Every `PASS` below has raw output in the
named `evidence/` directory; every unexecuted device test is `NOT_RUN`.

## 1. Revisions

| Repo | Branch | Review base | Latest commit |
|---|---|---|---|
| omega-mv | `feat/max-interop-contracts` | `cd5897e3` | `0dbc2067` |
| CUDApp | `feat/max-artifact-export` | `80f3a24` | `fcd7d24` |
| omega-bridge | `feat/gpu-interop` | `77376b1` (`feat/c-python-bridge`) | branch tip |

Pinned external software: Modular MAX `max/v26.7.0` =
`527d069ee11a41ac5320af1f9402db0a66b2b868` (`mojo/v1.2.0`), installed as
`modular==26.7.0`. Omega seed compiler:
`191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9`.
CUDApp driver/firmware target: NVIDIA 580.173.02, GB10, sm_121.

## 2. Completed and verified

| Deliverable | Evidence | Status |
|---|---|---|
| Frozen BF16 matmul + causal GQA contracts, canonical ids | `omega/evidence/MAX-INTEROP/680/` | PASS, 26 checks |
| Independent stdlib oracle, deterministic fixtures, mutation corpus | same | PASS |
| Native `.om` contract checker (seed-built) | `build/contract-check`, ids `647116fc…`, `003696e4…` | PASS |
| Native sm_121 cubin container from generated text | `cudapp/evidence/MAX-INTEROP/68/`, `nvdisasm`/`cuobjdump` | PASS offline |
| Artifact manifest: text/QMD/cbank SHA-256, contract/spec/ISA/shape/bounds/numeric/provenance | same | PASS, 47 checks |
| Admission/refusal (tamper, ISA, format, reloc, driver, contract) | same | PASS |
| Bridge GPU adapter v1 (negotiation + admission, named refusals, no fallback) | `bridge/evidence/MAX-INTEROP/3/` | PASS, 49 checks |
| Cross-runtime envelope + 416-byte C2 TEST receipt | `omega/evidence/MAX-INTEROP/681/` | PASS, 22 checks |
| MAX 26.7 source/API/licence pin and capability matrix | `bridge/docs/max/` | PASS (analysis) |
| Separate-process MAX vs Omega harness | `bridge/evidence/MAX-INTEROP/5/` | PASS on CPU |
| MAX/Omega numeric agreement (fixture) | same | bit-identical matmul SHA-256; GQA max abs error 2.7e-7 |

### Exact artifacts

- Matmul artifact `8dcc18e06f2306a785dd413c73f7289e12df0df995066ccb8cd5ff985a709db6`;
  cubin `b6ad13f4…`; text `f989e654…`.
- Attention artifact `b7c2c772ca3401160fa18c73d7c653114db20f928aaa993f217657e81df95cb8`.
- Envelope `86aabdb2e296636cd485b33a3f7141955431e3165bf857d86077315494622054`;
  receipt `5c05295af4e9eb482827db52d7f6b6a6b0c2a6b7392d15c8ac9e18b5296a9c27`.

The envelope binds `execution=NOT_RUN`, `oracle_verdict=NOT_RUN`, and a zero
output digest. It is a provenance/identity record, not a device result.

## 3. Blocked or not run

| Item | Reason | What unblocks it |
|---|---|---|
| `cuModuleLoadData` + launch of the exported cubin on GB10 | chip reserved by the coordinator (`CHIP-RESERVED`); `spark-window` refuses | an authorized `spark-window` with `--gb10 shared --quiet none`; run `build/cubin_probe` |
| Omega native matmul/GQA on GB10 | same | same window; `conformance/run.sh --device` |
| MAX 26.7 graph matmul/GQA on GB10 | same | same window; `max_runner.py --device gpu` |
| Paired ≥5-run benchmarks | requires two device paths | after the above |
| In-MAX native Omega cubin execution | pinned 26.7.0 has no byte-safe native module API; `load_function` takes `String` and only PTX is tested; the main-branch HAL path is not in the release, not production, and not reachable from public Python | upstream change in §4, or a decision to test main |
| AMD/Intel/Metal | no adapter, no hardware test | separate owner and qualification |

No speedup, no CUDA-free claim for MAX and no cross-context pointer sharing is
asserted. CPU timings in `harness.log` are harness diagnostics only.

## 4. Upstream request (draft, not submitted)

A byte-slice native-module entry point in the released MAX, with MAX retaining
device, context, queue, allocation and error ownership: accept a cubin ELF as
bytes (not UTF-8 `String`), document primary-context identity, define the entry
name and parameter ABI, return deterministic errors for wrong arch/entry, and
ship a cubin load/launch qualification test. Details and proposed signatures:
`docs/MAX-INTEGRATION.md`. No contact with Modular has been made; no PR exists.

## 5. Reproduce

See `docs/REPRODUCE.md`. Short form:

```sh
# omega-mv
sh tools/max-interop/build.sh && python3 tests/max-interop/test_contracts.py
sh tests/max-interop/build_receipt.sh && python3 tests/max-interop/test_envelope.py \
  --artifact ../../cudapp/evidence/MAX-INTEROP/68/matmul-16x16x8 \
  --fixture tests/max-interop/fixtures/matmul-v1.json
# CUDApp
make -j8 test-native-artifact && ./tools/artifact_smoke.sh evidence/MAX-INTEROP/68
# bridge
sh tools/build-gpu-adapter.sh && python3 tests/gpu/test_gpu_adapter.py
sh conformance/run.sh
```

## 6. Residual risks

1. The cubin container is offline-valid only. The driver may require sections
   absent here (for example capability metadata); `cuModuleLoadData` is the
   decisive test, and it has not run.
2. `sm_121` vs `sm_121a` acceptance is untested; the MAX toolchain targets
   `sm_121a` for DGX Spark.
3. The Bridge adapter is host-tested; no device is opened by design, so its
   "real adapter" path is an admission contract, not a loader.
4. The MAX 26.7 report's main-branch citations are not release evidence; the
   pin lacks those paths.
5. CUDApp is Apache-2.0 WITH LLVM-exception; MAX paths mix Apache-2.0 WITH LLVM-exception/LLVM and the MAX
   Community License. Any upstream contribution needs its own licence review.
