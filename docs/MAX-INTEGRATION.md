# MAX integration: measured state and the exact blocker

Pinned MAX: `max/v26.7.0` = `527d069ee11a41ac5320af1f9402db0a66b2b868`
(`mojo/v1.2.0`). Full source analysis: [MAX-26.7-FEASIBILITY.md](max/MAX-26.7-FEASIBILITY.md).

## What is proven

1. **Container.** A CUDApp-generated sm_121 kernel is packaged as a cubin ELF and
   read back by `nvdisasm`/`cuobjdump`; the text section equals the generated
   bytes and the parameter metadata targets the CUDA constant-bank ABI
   (`0x380`). This is offline evidence, not a device load.
2. **Admission.** The Bridge GPU adapter accepts the exported artifact under
   `nvidia-cubin-elf64`, zero-VA QMD, fresh receipt and producer ownership, and
   refuses wrong ISA/driver/ABI/capability/rights/sync/format/reloc/receipt/
   ownership/alias. 49 checks, no device.
3. **Numeric equivalence (host).** MAX 26.7 on CPU and the CUDApp host path
   produce **bit-identical** f32 output for the frozen matmul fixture
   (`sha256 60a7f7d4…`); MAX causal GQA matches the fp64 oracle within
   `2.7e-7`, far inside the contract tolerance. This validates the harness and
   the mathematical embedding, not GB10 execution.
4. **Evidence binding.** The envelope binds artifact/cubin/QMD/input/output/
   contract/ISA and a 416-byte TEST-class C2 receipt; tampering, stale epochs
   and wrong ids are refused.

## What is not proven, and why

- **No GB10 run exists.** The chip is reserved by the coordinator
  (`CHIP-RESERVED` lists L332 L424 L401 …), so `spark-window open` refuses. Every
  device row is `NOT_RUN`; no simulation is substituted.
- **Pinned 26.7.0 does not ship the HAL bundle path.** `SDK/`, `Target/`,
  `MLRT/`, `max/driver/` are main-only. At the pin the only source-visible
  external-code entry is Mojo `DeviceContext.load_function(function_name, asm:
  String)`; its docstring says PTX/SASS, but only PTX is tested and `String`
  requires valid UTF-8, so raw cubin transport is **UNKNOWN**.
- **Main's HAL path accepts cubin structurally** (`M_driver_static_bundle` →
  `M_driver_bundle_load` → `cuModuleLoadDataEx` → `cuModuleGetFunction` →
  `cuModuleLaunch`), and NeoDriver sets `file_type="cubin"`. But it is not in
  the pinned release, is not the production path, and is not reachable from
  public Python `max.driver`.
- MAX on NVIDIA is **not CUDA-free**: the CUDA backend loads `libcuda.so.1`.

## Upstream request (draft; not submitted)

A byte-safe native-module entry point in the pinned release, with MAX retaining
device, context, stream, allocation and error ownership. Minimum shape:

```c
// Proposed, not existing API.
M_driver_status M_driver_bundle_load_bytes(
    M_driver_context *ctx, const uint8_t *data, size_t size,
    const char *file_type /* "cubin" */, M_driver_bundle **out);
M_driver_status M_driver_function_load(
    M_driver_bundle *b, const char *entry, M_driver_function **out);
M_driver_status M_driver_queue_execute(
    M_driver_queue *q, M_driver_function *f,
    const void *const *kernel_params, uint32_t grid[3], uint32_t block[3],
    uint32_t shared_bytes, M_driver_completion **done);
```

Acceptance requested: (a) cubin ELF accepted as bytes, not a UTF-8 string;
(b) primary-context identity documented so an external producer knows which
context the module lands in; (c) deterministic error for a wrong arch/entry;
(d) no cross-context pointer sharing implied; (e) a qualification test that
loads a cubin, not only PTX.

Until that exists or the release exposes the main HAL path, this repository
does **not** claim in-graph native execution. The separate-process harness is the
supported demonstration, and it is ready to run the moment a GPU window is
authorized.

## Next probes (all NOT_RUN)

G1 load the exported cubin through `cuModuleLoadData` and launch with
`cuLaunchKernel` on GB10; G2 load a PTX string through `load_function` on the
pin; G3 attempt the same with cubin bytes through an unsafe `String` only if the
licence and safety review permit; G4 repeat Stage A through MAX's public
graph/engine on GB10; G5 compare numeric output to the independent oracle and
record receipts. Details: [MAX-26.7-PROBE-PLAN.md](max/MAX-26.7-PROBE-PLAN.md).
