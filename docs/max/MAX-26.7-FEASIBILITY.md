<!-- Copied from the MAX 26.7.0 analysis checkout on 2026-10-23. The raw
command outputs and verbatim main-branch reference extracts cited as evidence/
stay in that analysis checkout; their SHA-256 values are in MAX-SHA256SUMS.txt.
No MAX source is copied into Omega/CUDApp/Bridge production paths. -->
# MAX 26.7.0 Interoperability Feasibility Report

Status: analysis complete for source-level feasibility. **No GPU step was executed** (see `PROBE-PLAN.md`).
Repository: `https://github.com/modular/modular`
Pinned ref: tag `max/v26.7.0` (also `mojo/v1.2.0`)
Pinned commit: `527d069ee11a41ac5320af1f9402db0a66b2b868`
Tree: `0d873aea6bafed021bf6033b3904db392778d76d`
Local checkout: `~/workspace/maxinterop/max-source` (HEAD = pinned commit, sparse, blobless clone)

Evidence conventions used below:

- `PIN <path>:<lines>` — file exists at the pinned commit. Path is relative to the repository root and is present in the sparse checkout.
- `MAIN <path>:<lines>` — file exists only at the current `origin/main` head used for the requested comparison, commit `da0db31d422e19ad5952d8d106b6da1d6899cf0a` (verified different from the pin), extracted verbatim under `evidence/main-references/` and hashed in `evidence/commands/06-main-reference-hashes.txt`. MAIN evidence is **not** release-tag evidence.
- Test files are cited only as corroboration, never as the sole basis for a capability claim.
- External NVIDIA semantics (`cuModuleLoadDataEx` accepting PTX or cubin) are called out as vendor-API semantics, not as MAX source.

---

## 1. Headline answer

1. **The pinned v26.7.0 source tree does not contain MAX's hardware-abstraction "bundle/module" path at all.** There is no `SDK/`, `Target/`, `MLRT/`, `GraphCompiler/`, or `max/driver/` directory at the pin (`evidence/commands/05-path-divergence.txt`). Every file named in the task brief is main-only.
2. At the pin, the **only documented route for externally produced device code is the Mojo API** `max.gpu.host.DeviceContext.load_function(...)`, whose docstring says it loads "assembly code (PTX/SASS)" and whose sibling `enqueue_function` launches a `DeviceExternalFunction` (`PIN max/mojo/max/gpu/host/device_context.mojo:5257-5310`, `:5324-5360`). This runs inside a Mojo custom op, so **MAX owns the context, allocations, queue and synchronization** for that launch. PTX is exercised by a pinned CUDA test (`PIN max/mojo/test/asyncrt/test_cuda.mojo:177-186`); **no pinned test loads a cubin**, and the argument type is `String` with a valid-UTF-8 precondition (`PIN Mojo/stdlib/std/collections/string/string.mojo:380-394`), so raw CUBIN ingestion is not a byte-safe public contract.
3. On **main**, MAX does have the path the brief describes: `M_driver_static_bundle` (raw bytes + `file_type`) → `M_driver_bundle_load` → `cuModuleLoadDataEx` → `M_driver_function_load` → `cuModuleGetFunction` → `M_driver_queue_execute` → `cuLaunchKernelEx` → `M_driver_queue_synchronize` (`MAIN SDK/include/HAL/M_driver_bundle.h:39-51,96-101`; `MAIN Target/lib/CUDA/Function.cpp:68-90,106-131`; `MAIN Target/lib/CUDA/M_driver_queue.cpp:155-196`; `MAIN Target/lib/CUDA/Queue.cpp:258-266`). The NeoDriver client explicitly sets `file_type = "cubin"` for NVIDIA targets (`MAIN max/driver/src/max_license/_hal/context.mojo:65-78`), and the HAL CUDA implementation does not inspect `file_type` (`MAIN Target/lib/CUDA/Function.cpp:68-90`). Structurally, a raw CUDApp-produced CUBIN is accepted by that path; no MAX signature or metadata check exists.
4. **sm_121 is a first-class pinned target.** The pinned Mojo toolchain maps `DGXSpark` to `sm_121`/`sm_121a` and emits `arch = "sm_121a"` (`PIN Mojo/stdlib/std/_gpu/host/_builtin_targets.mojo:70,477-496`); the public hardware-compatibility table lists sm_121 = DGX Spark (`PIN max/docs/site/gpu/hardware-compatibility.mdx:81-85`).
5. **Nothing here proves arbitrary SASS ingestion, and no hardware was run.** Loading a cubin still requires: the cubin be a valid ELF for the device; the entry-point symbol name be known; the kernel obey the CUDA parameter ABI; the CUDA context be the one MAX uses; and, at the pin, a byte-safe transport into `load_function`. See §8 for the explicit non-claims.
6. **MAX on NVIDIA is not CUDA-free.** The main CUDA backend `dlopen`s `libcuda.so.1` (`MAIN Target/lib/CUDA/Loader/CUDALoader.cpp:37`), and the pinned public docs require NVIDIA driver 580 / CUDA 13.0 or later (`PIN max/docs/site/gpu/hardware-compatibility.mdx:20-24`).

---

## 2. Pin and checkout verification

| Check | Result | Evidence |
|---|---|---|
| `git rev-parse HEAD` | `527d069ee11a41ac5320af1f9402db0a66b2b868` | `evidence/commands/01-pin-verification.txt` |
| `git rev-parse max/v26.7.0^{commit}` | same oid | `evidence/commands/01-pin-verification.txt` |
| `git cat-file -t max/v26.7.0` | `commit` (lightweight tag) | `evidence/commands/01-pin-verification.txt` |
| `git ls-remote` tag oid | `527d069...b868` | `evidence/commands/01b-remote-tag-oids.txt` |
| tree hash | `0d873aea6bafed021bf6033b3904db392778d76d` | `evidence/commands/01-pin-verification.txt` |
| subtree hashes | `max` `6b05fe51cb5c75113de512ca4e3f39b534faf96a`; `Licenses` `9763f7484ce927796ac686fb2c243b9c49a19077`; `Support` `cae6645b0e3c0c26aca10010917010c92bbb1d21` | `evidence/commands/02-tree-hashes.txt` |
| sparse set | `AsyncRT`, `Licenses`, `Mojo/stdlib/std/_gpu`, `Mojo/stdlib/std/_plugin`, `Mojo/stdlib/std/sys`, `Mojo/stdlib/std/collections/string`, `Support`, `docs`, `max` | `evidence/commands/07-checkout.txt` |
| working tree | only untracked deliverables (`FEASIBILITY-REPORT.md`, `PROBE-PLAN.md`, `SHA256SUMS`, `evidence/`) | `evidence/commands/07-checkout.txt` |

Clone method: `git clone --filter=blob:none --no-checkout https://github.com/modular/modular.git`, then `git fetch --depth=1 origin refs/tags/max/v26.7.0:refs/tags/max/v26.7.0`, then sparse checkout and detached checkout of the pinned commit. The clone also contains `origin/main`, used only for the divergence mapping requested by the task.

---

## 3. Divergence: requested paths at the pin vs main

Command output: `evidence/commands/05-path-divergence.txt`. Main commit: `da0db31d422e19ad5952d8d106b6da1d6899cf0a`.

| Requested path | At pin `527d069` | At main `da0db31` | Pinned equivalent / consequence |
|---|---|---|---|
| `SDK/include/HAL/M_driver_bundle.h` | MISSING | EXISTS | No HAL bundle API at pin. Closest pinned surface: `DeviceContext.load_function` (`PIN max/mojo/max/gpu/host/device_context.mojo:5257`). |
| `Target/lib/CUDA/M_driver_function.cpp` | MISSING | EXISTS | CUDA plugin source not published at pin. |
| `max/driver/src/max_license/README.md` | MISSING | EXISTS | NeoDriver does not exist at pin. Pinned driver is `max/python/max/driver/`. |
| `Target/test/CUDAPluginTest.cpp` | MISSING | EXISTS | No pinned HAL qualification test. |
| `Licenses/MAX_LICENSE` | MISSING | EXISTS | Pin has `Licenses/LICENSE` (MAX Community License) and root `LICENSE` (Apache-2.0 WITH LLVM-exception LLVM). |
| `GraphCompiler/`, `MLRT/`, `max/driver/`, `Kernels/` | MISSING | EXISTS | Compiler/runtime/HAL internals are not in the pinned source distribution. |

Pinned top-level tree (abridged): `AsyncRT Cache Config Init LICENSE Licenses MODULE.bazel Mojo README.md REPO.bazel Support bazel bazelw context7.json docs max pyproject.toml rust_kv tools utils`.
Main top-level tree adds: `GraphCompiler Kernels MLRT SDK Target`.

**Consequence for the core question:** at the exact pin, "MAX's own bundle/module path" cannot be inspected, built, or called from source; the HAL analysis in this report is a main-branch analysis and must be labelled as such. The only pinned, source-visible device-code ingestion API is the Mojo `DeviceContext` API.

---

## 4. Capability matrix

Status vocabulary: **SUPPORTED**, **UNSUPPORTED**, **UNKNOWN**, **REQUIRES_MODULAR_CHANGE**. A row is evaluated against the source named in the Source column; a capability can therefore be SUPPORTED on main and UNKNOWN/UNSUPPORTED at the pin.

| # | Capability | Source | Status | Evidence |
|---|---|---|---|---|
| 1 | Custom op registration at Mojo source level (`mo.custom` + `@extensibility.register`) | PIN | SUPPORTED | `max/python/max/graph/ops/custom.py:69-129`; `max/kernels/src/graph_compiler/extensibility/decorators.mojo:46-75`; `max/python/max/graph/graph.py:296-314` |
| 2 | Register a custom op from a precompiled binary that is not a Mojo package | PIN | UNSUPPORTED | `max/python/max/graph/graph.py:258-283` accepts only `.mojoc` or Mojo source; `max/python/max/graph/ops/custom.py:109-127` requires the symbol to resolve in the kernel library |
| 3 | Graph construction into an MLIR module | PIN | SUPPORTED | `max/python/max/graph/graph.py:551-568,843-865` |
| 4 | Public graph-compile API to a compiled artifact | PIN | SUPPORTED | `max/python/max/engine/api.py:1276-1305`; `max/python/max/_core/engine.pyi:69-83` |
| 5 | Graph compiler internals / MEF writer implementation | PIN | UNKNOWN | Source absent at pin (`evidence/commands/05-path-divergence.txt`); only the native capsule call is visible (`api.py:1294-1296`) |
| 6 | MEF binary format definition | MAIN | SUPPORTED | `MLRT/docs/GraphRT/ModularExecutorFormat.md:136-159, 93-100` |
| 7 | GPU device/context ownership and lifetime, public Python API | PIN | SUPPORTED (surface) | `max/python/max/_core/driver.pyi:32-45,229-238,314-315`; internals UNKNOWN at pin |
| 8 | Context identity: primary `CUcontext` shared with other libraries | MAIN | SUPPORTED | `Target/lib/CUDA/Context.cpp:20-30`; `MLRT/lib/Driver/DeviceContext/CUDA/CUDADeviceContext.cpp:904` |
| 9 | Device memory allocation through `Buffer` | PIN | SUPPORTED | `max/python/max/_core/driver.pyi:1131-1183` |
| 10 | Guaranteed allocation alignment | PIN | UNKNOWN | Only a query exists (`driver.pyi:1463-1466`); no guarantee stated in pinned source. Main: minimum 64 B (`MLRT/lib/Driver/DeviceContext/MemoryManager.cpp:851-865`) |
| 11 | DLPack zero-copy import/export | PIN | SUPPORTED | `driver.pyi:1318-1333,1442-1448`; `max/python/max/_core/dlpack.pyi:20-43`; `max/python/max/driver/buffer.py:201-269` |
| 12 | Wrap an arbitrary device pointer without DLPack | PIN | UNSUPPORTED (no public API) | Constructors only take dtype/shape/device/stream (`driver.pyi:1164-1183`); `_data_ptr` is private (`driver.pyi:1479-1480`) |
| 13 | Ownership transfer / producer-retains semantics | PIN | SUPPORTED (DLPack) | `driver.pyi:1322-1323`; main implementation `max/python/max/_core/max_license/lib/Driver/Buffer.cpp:306-335` |
| 14 | Queues/streams/events and ordering primitives | PIN | SUPPORTED | `driver.pyi:678-696,707-762,830-842`; `CompletionFlag` `:378-458`; `DeviceEvent` `:475-528` |
| 15 | Synchronization, completion and error propagation | PIN | SUPPORTED | `driver.pyi:707-713` (raises on internal error), `:509-528`; contract test `max/tests/tests/driver/test_buffer_sync_contracts.py:13-29` |
| 16 | Load external PTX | PIN | SUPPORTED | `device_context.mojo:5257-5310`; test `max/mojo/test/asyncrt/test_cuda.mojo:177-186` |
| 17 | Load external CUBIN/SASS | PIN | UNKNOWN | Doc/release note claim PTX/SASS (`device_context.mojo:5269-5281`; `max/docs/site/releases/v26.5.md:606-614`), but only PTX is tested and the type is `String` with UTF-8 precondition (`Mojo/stdlib/std/collections/string/string.mojo:380-394`); runtime implementation absent |
| 18 | Load external CUBIN through MAX's HAL bundle path | MAIN | SUPPORTED (code path), not production | `max/driver/src/max_license/_hal/context.mojo:65-78,359-369`; `Target/lib/CUDA/Function.cpp:68-90`; `Target/lib/CUDA/M_driver_queue.cpp:155-196`; production status `MAIN max/driver/src/max_license/README.md:31-38` |
| 19 | Ingest LLVM IR as device code | PIN/MAIN | UNSUPPORTED | No API accepts LLVM IR; `load_function` documents only PTX/SASS (`device_context.mojo:5269-5281`); HAL passes bytes to `cuModuleLoadDataEx` (`MAIN Target/lib/CUDA/Function.cpp:80-85`), which is PTX/cubin only |
| 20 | Native launch hook reachable from public Python | PIN | UNSUPPORTED | No launch/module API in `max.driver` or `max._core.driver` (`evidence/commands/20-python-launch-absence.txt`); `Model.execute` only runs a compiled graph (`engine.pyi:271`) |
| 21 | Native launch hook reachable from public Mojo | PIN | SUPPORTED | `device_context.mojo:5257-5310` (load), `:5324-5360` (enqueue), `_device_context_extras.mojo:228-250` (argument packing); `DeviceExternalFunction` is not re-exported at `host/__init__.mojo:21-33` |
| 22 | NeoDriver / HAL bundle API | PIN | UNSUPPORTED (absent) | Directory and headers absent at pin (`evidence/commands/05-path-divergence.txt`) |
| 23 | Plugin selection by environment variable | MAIN | SUPPORTED | `Target/include/Target/DriverPlugin.h:47-53`; `Target/lib/DriverPlugin/DriverPlugin.cpp:286-321` (`MODULAR_DRIVER_PLUGINS`, colon-separated `.so` list); `MLRT/lib/Driver/DeviceContext/CompilerDeviceArch.cpp:59` |
| 24 | Serving telemetry, opt-out available | PIN | SUPPORTED | `max/python/max/serve/telemetry/common.py:96,115-124`; `max/python/max/serve/config.py:311-315` |
| 25 | Engine/driver offline operation without network egress | PIN | UNKNOWN | No network imports in inspected Python driver/engine scope, but the native `_core` implementation is absent from the pinned tree; compile can be cross-target (`engine/api.py:450-455,1070-1076`) but offline egress is unproven |
| 26 | License terms per relevant path | PIN/MAIN | SUPPORTED | §9 below |
| 27 | CUDA-free NVIDIA execution | PIN/MAIN | UNSUPPORTED | `max/docs/site/gpu/hardware-compatibility.mdx:20-24`; `Target/lib/CUDA/Loader/CUDALoader.cpp:37` |

---

## 5. Capability detail

### 5.1 Custom op registration ABI

**Pinned Python side.** `max.graph.ops.custom.custom(name, device, values, out_types, parameters)` builds an MLIR `mo.custom` op whose `symbol` is the registration name, attaches a `device` attribute and optional `parameters`, then calls `graph._kernel_library.verify_custom_op(custom_op)` (`PIN max/python/max/graph/ops/custom.py:69-129`). `inplace_custom` builds the same op with an extra chain operand (`:132-208`). `KernelLibrary` accepts only:
- `.mojoc` compiled Mojo packages, or
- a Mojo source directory, which is compiled to `.mojoc` (`PIN max/python/max/graph/graph.py:258-283`).

**Pinned Mojo side.** `@extensibility.register(name, type=..., api=..., arch=..., model=...)` registers a struct as an implementation of an `mo`/`mo.custom` op. The graph compiler picks the most specific match; `arch` examples include `sm_100a`, `sm_90a`, `gfx942` (`PIN max/kernels/src/graph_compiler/extensibility/decorators.mojo:46-75,115-124`). This is a **compile-time, source-level ABI**, not a binary plugin ABI: the registration is consumed by the Mojo compilation of the kernel library. A worked example is `PIN max/examples/custom_ops/kernels/vector_addition.mojo:83-107`.

**What this does not establish.** A custom op's registration name does not let us hand MAX a SASS blob. The kernel library must be Mojo source or a Mojo-compiled package, and the registered implementation is Mojo code. The Mojo implementation may itself load external assembly at runtime via `DeviceContext.load_function` (see §5.6), but that is a wrapper technique, not a registration of native code as a graph op.

### 5.2 Graph compilation and artifact format

Pinned surface:
- `Graph` creates a `mo.graph` op inside a `builtin.ModuleOp` (`PIN max/python/max/graph/graph.py:843-865`); `Module` wraps that MLIR module (`:551-568`).
- `InferenceSession._compile_module` passes `module.mlir_module._CAPIPtr` to the closed native implementation `self._impl.compile(...)` and returns an `AsyncValue[CompiledModels]` (`PIN max/python/max/engine/api.py:1276-1305`).
- `CompiledModels.export_mef(path)` writes a `.mef`; `max._core.engine.read` reads one back; `Model` is the executable form (`PIN max/python/max/_core/engine.pyi:69-83,126-152,154`).
- Pinned comments state that host ELF and cubins "both embed self-contained in the exported MEF" (`PIN max/python/max/_interpreter_ops/unary_elementwise_gc.py:195-199`).
- The lowered/fused execution form is visible as `mgp.generic.execute` kernels in `Model.kernel_summaries` (`PIN max/python/max/_core/engine.pyi:247-255`).

**Gap at the pin:** the compiler that performs MLIR → MGP → device code and the MEF encoder are not in the pinned source tree (`evidence/commands/05-path-divergence.txt`). The pin therefore gives us the *shape* of the artifact (MEF containing cubins) but not a writable format.

**Main adds the format definition.** `MLRT/docs/GraphRT/ModularExecutorFormat.md` documents MEF: magic `0xBEF0`, section list, VBR encoding, unknown sections skipped, produced by `MLIRToMEF`, and explicitly "MEF files can be created by an arbitrary producer" (`MAIN MLRT/docs/GraphRT/ModularExecutorFormat.md:93-100,136-159`). This is documentation only; there is no public, stable MEF-writer API in the pinned Python surface.

### 5.3 GPU device and context ownership

Pinned public API:
- `Device` is the base; `Accelerator` represents any non-CPU backend. Repeated construction with the same device id returns/reuses the first instance, including its memory limit (`PIN max/python/max/_core/driver.pyi:32-45,321-338`).
- `Device.default_queue` is created when the device object is created (`:229-238`).
- `Device._device_context_ptr()` is explicitly internal (`:314-315`); `DeviceQueue._device_context_ptr()` likewise (`:826-827`). These are lifetime/identity escape hatches, not ownership-transfer APIs.
- Public synchronization is `Device.synchronize()` (`:69-74`) and `DeviceQueue.synchronize()` (`:707-713`).

**Main internals (not proof for the pin).** MLRT retains the CUDA **primary context** (`cuDevicePrimaryCtxRetain`) when constructing a context and releases it on teardown (`MAIN MLRT/lib/Driver/DeviceContext/CUDA/CUDADeviceContext.cpp:904` and destructor at `:310`); the HAL CUDA plugin does the same (`MAIN Target/lib/CUDA/Context.cpp:20-39`). A context owns allocations, loaded code, queues and events (`MAIN max/driver/src/max_license/README.md:83-87`). Because both MAX and another library using the CUDA runtime/driver primary context share `CUcontext`, addresses allocated in one are valid in the other **provided both use the same primary context and no competing `cuCtxCreate` context**. CUDA device addresses are `CUdeviceptr` values in a unified virtual address space; MAX's HAL `wrapSync` stores the raw address and does not translate handles (`MAIN Target/lib/CUDA/Context.cpp:81-91`), so a loaded external function receives the same address MAX allocated. This is the structural basis for pointer interop, but it is main-only evidence and was not tested at runtime. If the pinned runtime creates a private context instead, pointers from another primary context are invalid; that is exactly what probe G1 resolves.

Queue semantics on main: NeoDriver has **no default queue**, a queue guarantees only start-to-start ordering, and a `Stream` is a queue with end-to-start (FIFO) ordering (`MAIN max/driver/src/max_license/README.md:88-102`). A `DeviceQueue` obtained from the pinned Python API behaves as an in-order stream in its documented contract (`PIN max/python/max/_core/driver.pyi:678-696`). CUDA streams are created non-blocking (`MAIN Target/lib/CUDA/Queue.cpp:36-39`). Cross-stream dependencies require `record_event`/`wait_for`; completion is observed by `synchronize()` or event signaling, and errors surface as `ValueError` (pin) or `M_driver_status_t` (main).

### 5.4 Device memory: allocation, alignment, import/export, ownership

Pinned:
- `Buffer(dtype, shape, device=..., usage=...)` allocates; DLPack import is `Buffer.from_dlpack(array, copy=...)`, documented as usually no-copy with the producer retaining ownership (`PIN max/python/max/_core/driver.pyi:1131-1183,1318-1333`).
- `Buffer.__dlpack__` / `__dlpack_device__` export a capsule (`:1442-1448`); `Buffer._data_ptr()` returns the address but is marked internal (`:1479-1480`); `Buffer._aligned(alignment)` is a query only (`:1463-1466`).
- `max._core.dlpack.make_dlpack_capsule(owner, data, device_type, device_id, dtype, shape, strides, max_version)` builds an exporter capsule from an external pointer, and `import_dlpack(producer, stream)` imports one (`PIN max/python/max/_core/dlpack.pyi:20-43`). This is the byte/pointer interop entry point on the Python side, although it lives under the private `max._core` namespace.
- `max.driver.buffer._from_dlpack` accepts contiguous numpy arrays and tensors and rejects non-contiguous inputs (`PIN max/python/max/driver/buffer.py:201-269`).

Alignment: the pin exposes only a predicate (`_aligned`), tested in `max/tests/tests/driver/test_buffer.py:972-1012`. **No minimum alignment is guaranteed in pinned source.** On main, the MLRT memory manager enforces a minimum of 64 bytes (`MAIN MLRT/lib/Driver/DeviceContext/MemoryManager.cpp:851-865`), and base allocations go through `cuMemAlloc` (`MAIN Target/lib/CUDA/Context.cpp:61-79`), whose base alignment is a CUDA driver property rather than a MAX constant. Treat 64 B as the documented main-side allocator floor and 256 B as a typical `cuMemAlloc` base alignment only after measuring.

Ownership:
- DLPack import wraps producer-owned memory and installs the producer's deleter; the producer keeps ownership (`PIN max/python/max/_core/driver.pyi:1322-1323`; `MAIN max/python/max/_core/max_license/lib/Driver/Buffer.cpp:306-335`).
- On main, `Device.wrapExternalBuffer` calls `createBufferOwning(data, size, owning=true)` and then replaces the destructor with the caller's deleter (`MAIN max/python/max/_core/max_license/lib/Driver/Device.cpp:69-76`). The HAL exposes explicit `M_driver_memory_wrap(address, size, owning)` and `M_driver_memory_unwrap` for ownership transfer (`MAIN SDK/include/HAL/M_driver_memory.h:91-149`); the CUDA implementation simply stores the address and a boolean, ignoring `size` and not validating the pointer (`MAIN Target/lib/CUDA/Context.cpp:81-91`).

This means MAX can operate on externally allocated memory, but **the caller must guarantee the pointer came from the same CUDA context/device and stays alive**.

### 5.5 Queues, events, ordering, synchronization, error propagation

Pinned:
- A `DeviceQueue` is "a sequence of operations that will be executed in order"; multiple queues may run concurrently (`PIN max/python/max/_core/driver.pyi:678-696`).
- `record_event()` returns a `DeviceEvent` signaled after previously enqueued work; `record_event(event)` records an existing event; `wait_for(DeviceQueue|Device)` orders future work (`:716-762`).
- `wait_for_host_value(flag, value)` stalls the queue until a 64-bit host-mapped flag equals the value, documented as wrapping MLRT `DeviceStream::enqueueWaitOnHostValue` / CUDA `cuStreamWaitValue64` (`:759-781`).
- `DeviceEvent` supports `synchronize()`, `is_ready()`, `elapsed_time()` (`:475-528`); `CompletionFlag` is pinned host memory mapped into device space (`:378-458`).
- `DeviceQueue.synchronize()` blocks until all work completes and **raises `ValueError` if any enqueued operation had an internal error** (`:707-713`). Read-back operations (`to_numpy`, `item`, `__dlpack__`) are contractually synchronous with pending device work (`PIN max/tests/tests/driver/test_buffer_sync_contracts.py:13-29`).
- `native_stream_handle` returns the CUDA `CUstream` / HIP `hipStream_t` (0 if none), explicitly so native code outside MLRT can order its own work, e.g. record an event; the handle remains owned by the stream and must not be destroyed (`PIN max/python/max/_core/driver.pyi:830-842`). **This is the cleanest pinned co-scheduling primitive.**

Main internals:
- HAL queue creation uses `cuStreamCreateWithPriority` with the non-blocking flag (`MAIN Target/lib/CUDA/Queue.cpp:36-39`); record/wait use `cuEventRecord` / `cuStreamWaitEvent` (`:221-240`); sync is `cuStreamSynchronize` (`:258-266`).
- MLRT exposes the same through `CUDADeviceContext::createStream`, `enqueueEvent`, `synchronize` (`MAIN MLRT/lib/Driver/DeviceContext/CUDA/CUDADeviceContext.cpp:2341-2360,2387-2399`) and can wrap an externally created stream (`createExternalStream`, `:2382-2386`).

### 5.6 Module loading and acceptance of SASS/cubin/PTX/LLVM IR

**Pinned Mojo API (the only pinned external-code loader).**
`DeviceContext.load_function[func_type](function_name=..., asm=...)` constructs a `DeviceExternalFunction`; the docstring says it loads a pre-compiled GPU function from "assembly code (PTX/SASS)" instead of compiling from Mojo source (`PIN max/mojo/max/gpu/host/device_context.mojo:5257-5310`). The constructor forwards `function_name`, `asm`, `asm.byte_length()`, a debug level and an optimization level to the runtime symbol `AsyncRT_DeviceContext_loadFunction` (`:4377-4425`). `enqueue_function` accepts that value and packs each argument's address into an array (`PIN max/mojo/max/gpu/host/_device_context_extras.mojo:228-266`), matching the CUDA `void** kernelParams` convention.
- The API is documented in source (the `load_function` docstring is the public description), but `DeviceExternalFunction` is **not** re-exported by `max/gpu/host/__init__.mojo` (only `DeviceFunction` is; `PIN max/mojo/max/gpu/host/__init__.mojo:21-33`). Callers import it from `max.gpu.host.device_context`.
- The `asm` parameter is `String`. Mojo's `String` constructors require valid UTF-8 (`PIN Mojo/stdlib/std/collections/string/string.mojo:380-394`). PTX is ASCII and fine. A cubin is arbitrary binary; there is no documented byte-slice overload at the pin. A caller could construct a non-valid-UTF-8 `String` via unsafe means, but that violates the documented precondition. This is a real gap for CUBIN ingestion, not a cosmetic one.
- Pinned tests load only PTX text (`PIN max/mojo/test/asyncrt/test_cuda.mojo:177-186`); release notes mention "PTX/cubin blob" for the cache-key fix (`PIN max/docs/site/releases/v26.5.md:606-614`) and external functions in device graphs (`:575-587`). No pinned cubin test exists.
- The runtime implementation of `AsyncRT_DeviceContext_loadFunction` is **not** in the pinned source tree (AsyncRT at the pin contains no `DeviceContext`; `evidence/main-references` main MLRT is the only implementation evidence).

**Main HAL path (structurally accepts cubin).**
- `M_driver_static_bundle` is a non-owning byte slice plus a `file_type` string; `M_driver_bundle_load` turns it into a runtime bundle; `M_driver_function_load` retrieves a named entry point (`MAIN SDK/include/HAL/M_driver_bundle.h:39-51,96-101`; `MAIN SDK/include/HAL/M_driver_function.h:38-42`).
- The CUDA implementation ignores `file_type` and calls `cuModuleLoadDataEx` with the bytes, then `cuModuleGetFunction` with the exact name (`MAIN Target/lib/CUDA/Function.cpp:68-90,106-131`). CUDA's driver accepts PTX text or a cubin/fatbin ELF here; this is vendor-API behavior, not a MAX check.
- `Target/lib/CUDA/M_driver_function.cpp` is only the exported C-ABI shim: it validates handles and forwards to `M_driver_runtime_bundle::load` / `M_driver_function::load` / `unload` (`MAIN Target/lib/CUDA/M_driver_function.cpp:23-79`); the CUDA calls live in `Function.cpp`.
- The existing HAL CUDA qualification test is **PTX-only**: it builds `M_driver_static_bundle` with `fileType("ptx")` and a PTX `vecAdd` blob, then exercises bundle load/unload, function load/introspection, synchronous and asynchronous memory allocation, queue execute and synchronize (`MAIN Target/test/CUDAPluginTest.cpp:36-107,145-162,249-330`). There is no cubin case in that test; it therefore demonstrates the bundle/launch path but not cubin acceptance.
- The NeoDriver client sets `file_type` to `"cubin"` for `nvptx64-nvidia-cuda` targets and `"hsaco"` for AMD (`MAIN max/driver/src/max_license/_hal/context.mojo:65-78`), and comments that PTX text is accepted even when `file_type="cubin"` (`:359-369`). That is direct evidence that MAX's NVIDIA bundle format **is the raw cubin**, not a MAX-specific wrapper.
- No LLVM IR path exists. The HAL passes bytes straight to the CUDA driver; the Mojo loader documents PTX/SASS only.

**MEF vs `.mojoc` vs shared object.**
- `.mef` is the compiled *graph* artifact (MEF, magic `0xBEF0`), containing host ELF and cubins (`PIN .../engine.pyi:69-83`; `PIN .../unary_elementwise_gc.py:195-199`; `MAIN MLRT/docs/GraphRT/ModularExecutorFormat.md:136-159`).
- `.mojoc` is a Mojo *binary package* consumed as a custom-op kernel library (`PIN max/python/max/graph/graph.py:258-283`); it is compiler output, not a generic SASS container.
- A shared object is not a MAX device-code bundle. The only `.so` surfaces are MAX's own HAL/driver plugins, loaded by `MODULAR_DRIVER_PLUGINS` on main (`MAIN Target/lib/DriverPlugin/DriverPlugin.cpp:286-321`).

**Bundle format, restated exactly.** For NVIDIA on main, the expected object is **a cubin ELF (or PTX text) passed as a byte slice**, plus a `file_type` annotation of `"cubin"`; it is not a `.mojopkg`, not a `.mojoc`, not a shared object, and not a MAX-wrapped container (`MAIN max/driver/src/max_license/_hal/context.mojo:65-78,359-369`; `MAIN SDK/include/HAL/M_driver_bundle.h:39-51`; `MAIN Target/lib/CUDA/Function.cpp:68-90`). The MEF is the graph artifact that *contains* such code objects; it is not the input to `M_driver_bundle_load`.

#### 5.6.1 Entry-point and launch ABI (main HAL)

- **Symbol lookup:** `cuModuleGetFunction(module, function_name)` with the exact symbol string (`MAIN Target/lib/CUDA/Function.cpp:113-119`). For a C++-mangled kernel this is the mangled name; for an `extern "C"` kernel it is the plain name.
- **Parameters:** standard CUDA `void** kernelParams` — each element points to the argument value; the CUDA HAL ignores `arg_sizes` and `num_args` (`MAIN Target/lib/CUDA/M_driver_queue.cpp:155-196`). The Mojo external-function path likewise packs each argument's address (`MAIN`-equivalent pinned code: `PIN max/mojo/max/gpu/host/_device_context_extras.mojo:228-266`).
- **Launch descriptors:** grid/block dimensions, dynamic shared-memory bytes, and a `CUlaunchAttribute` array (cluster dims, etc.) are passed through to `cuLaunchKernelEx` (`MAIN SDK/include/HAL/M_driver_queue.h:184-195`; `MAIN Target/lib/CUDA/M_driver_queue.cpp:170-185`).
- **Constant bank:** there is no implicit constant-bank layout requirement. Constant memory is copied separately by name via `cuModuleGetGlobal_v2` + `cuMemcpyHtoDAsync_v2` (`MAIN MLRT/lib/Driver/DeviceContext/CUDA/CUDADeviceContext.cpp:1620-1639`).
- **No MAX-specific metadata** (no signature blob, no registration record, no shape metadata) is consulted at load or launch. Shape/type checking happens in the graph/executor layer before the HAL call, not in the CUDA plugin.

### 5.7 Native launch hook from public Python / Mojo

- **Python: no.** A search of `max/python/max/driver`, `max/python/max/_core/driver.pyi`, and `max/python/max/_core/engine.pyi` finds no `launch`, `load_function`, `load_module`, or `enqueue_function` API (`evidence/commands/20-python-launch-absence.txt`). The only path is building a `Graph` and calling `InferenceSession.compile` (or `read` a MEF), then `Model.execute` (`max/python/max/engine/api.py:1276-1305`; `max/python/max/_core/engine.pyi:271`). `Model.execute` accepts `Buffer`/DLPack inputs and copies them to the execution device (`engine.pyi:271-283`).
- **Mojo: yes**, via `DeviceContext.load_function` + `enqueue_function` as above. The intended usage is inside a MAX custom op: the custom op receives a `DeviceContext` and tensors, and the example calls `gpu_ctx.enqueue_function(...)` (`PIN max/examples/custom_ops/kernels/vector_addition.mojo:43-80`). A custom op can equally call `ctx.load_function` first.
- **C HAL: yes on main only**, through `M_driver_bundle_load` / `M_driver_function_load` / `M_driver_queue_execute`.

### 5.8 Plugin loader / env-var targeting (requested by the parent)

- At the pin, there is no source-visible HAL plugin loader. The pinned CUDA "plugin" is a compile-time Mojo struct (`PIN max/mojo/max/_plugin/cuda.mojo:20-28`), not a dynamically registered `.so` selected by an environment variable. No `MODULAR_*PLUGIN*` env var appears in the pinned driver/engine Python surface (`evidence/commands/16-telemetry-offline.txt`).
- On main, the legacy C++ runtime auto-loads driver plugins from **`MODULAR_DRIVER_PLUGINS`**, a colon-separated list of plugin spec paths (`MAIN Target/include/Target/DriverPlugin.h:47-53`; `MAIN Target/lib/DriverPlugin/DriverPlugin.cpp:286-321`). Each `.so` is expected to implement `M_driver_*` and `M_driver_create`. The compiler-side arch query also reads the same variable (`MAIN MLRT/lib/Driver/DeviceContext/CompilerDeviceArch.cpp:59`). Tests use `"CUDA@/path/to/CUDAPlugin.so"` (`MAIN MLRT/test/Driver/HAL/BUILD.bazel:62`).
- NeoDriver's Mojo client loader uses an explicit plugin spec `"name@/path/to/lib.so"` rather than an env var (`MAIN max/driver/src/max_license/_hal/plugin.mojo:47-78`; `driver.mojo:39-54`).
- **NeoDriver is not reachable from public Python `max.driver`** on main: `max/python/max/driver/__init__.py:21-43` imports only `max._core.driver` legacy types (`MAIN max/python/max/driver__init__.py` in evidence; repository path `max/python/max/driver/__init__.py`).

### 5.9 Telemetry and offline operation

- Serving telemetry is real and enabled by default: the OTLP endpoint is `https://telemetry.modular.com:443` (`PIN max/python/max/serve/telemetry/common.py:96,470,724,1281`); `Settings.disable_telemetry` defaults to `False` (`PIN max/python/max/serve/config.py:311-315`); opt-out is `MAX_SERVE_DISABLE_TELEMETRY` or `OTEL_SDK_DISABLED=true` (`common.py:115-124`).
- The CLI `max-pipelines` configures telemetry for subcommands not on the opt-out list (`PIN max/python/max/_entrypoints/pipelines.py:211-213,216`).
- The inspected `max.driver` / `max.engine` Python scope imports no HTTP client and mentions only `MODULAR_DEBUG` and `MODULAR_MAX_DEBUG_PROFILING_OUTPUT_PATH` (`evidence/commands/16-telemetry-offline.txt`). That is **not** proof of no native egress: the pinned source tree ships only `.pyi` stubs for `max._core`; its native implementation is not in the repository, and the MAX Community License itself says use of MAX may be subject to telemetry collection (`PIN Licenses/LICENSE:108-116`).
- Compilation can be separated from a device: `CompiledModel.export_mef` is documented for cross-compilation/virtual-device scenarios where the target device is not attached (`PIN max/python/max/engine/api.py:450-455`), and `compile` is documented for cross-compilation (`:1070-1076`). This supports offline *compilation* planning but does not establish network-free execution.
- **No CUDA-free claim.** NVIDIA programming requires driver 580+/CUDA 13.0+ (`PIN max/docs/site/gpu/hardware-compatibility.mdx:20-24`); main's CUDA backend `dlopen`s `libcuda.so.1` (`MAIN Target/lib/CUDA/Loader/CUDALoader.cpp:37`).

---

## 6. Concrete end-to-end trace

### 6.1 Pinned v26.7.0 (what is visible in source)

| Step | Concrete function/type | Evidence |
|---|---|---|
| 1. Graph op | `max.graph.ops.custom.custom()` emits `mo.custom` with symbol = registration name; `inplace_custom()` adds a chain | `max/python/max/graph/ops/custom.py:69-129,132-208` |
| 2. Kernel selection (lowering input) | `@extensibility.register(name, type, api, arch, model)` selects the most specific Mojo implementation at compile time | `max/kernels/src/graph_compiler/extensibility/decorators.mojo:46-75` |
| 3. Lowered/fused form (observable) | `Model.kernel_summaries`: one summary per `mgp.generic.execute` fused kernel | `max/python/max/_core/engine.pyi:247-255` |
| 4. Module | `Graph` builds `mo.graph` in `builtin.ModuleOp`; `Module.mlir_module` | `max/python/max/graph/graph.py:551-568,843-865` |
| 5. Compile call | `InferenceSession._compile_module` → `self._impl.compile(module.mlir_module._CAPIPtr, ...)` | `max/python/max/engine/api.py:1276-1305` |
| 6. Artifact | `CompiledModels` / `export_mef`; MEF embeds host ELF + cubins | `max/python/max/_core/engine.pyi:69-83`; `max/python/max/_interpreter_ops/unary_elementwise_gc.py:195-199` |
| 7. Driver module load | **Not present in pinned source.** Native runtime boundary only | `evidence/commands/05-path-divergence.txt` |
| 8. Allocation | `Buffer(dtype, shape, device=...)`; `Model.execute` copies inputs to device | `max/python/max/_core/driver.pyi:1164-1183`; `max/python/max/_core/engine.pyi:271-283` |
| 9. Dispatch | `Model._execute_device_tensors` (native); no Python launch API | `max/python/max/_core/engine.pyi:359-361`; `evidence/commands/20-python-launch-absence.txt` |
| 10. Sync | `DeviceQueue.synchronize()` / `Device.synchronize()`; read-backs are synchronous | `max/python/max/_core/driver.pyi:69-74,707-713`; `max/tests/tests/driver/test_buffer_sync_contracts.py:13-29` |
| 11. Output | `list[Buffer]` returned from `Model.execute` | `max/python/max/_core/engine.pyi:271` |

### 6.2 Main branch internals (source-visible, not the pin)

| Step | Concrete function/type | Evidence |
|---|---|---|
| 1–4 | Same Python graph/custom-op surface as above | as above |
| 5. Artifact | MEF (`0xBEF0`) produced by `MLIRToMEF`; format documented | `MAIN MLRT/docs/GraphRT/ModularExecutorFormat.md:93-100,136-159` |
| 6. Bundle load | `Context.load_bundle(asm: StringSlice)` builds `M_driver_static_bundle{mapped_data, file_type="cubin"}` → `M_driver_bundle_load` | `MAIN max/driver/src/max_license/_hal/context.mojo:65-78,359-396`; `MAIN SDK/include/HAL/M_driver_bundle.h:96-101` |
| 7. Module load | `M_driver_runtime_bundle::load` → `cuModuleLoadDataEx` | `MAIN Target/lib/CUDA/Function.cpp:68-90` |
| 8. Function | `M_driver_function::load` → `cuModuleGetFunction` + `cuFuncSetAttribute` | `MAIN Target/lib/CUDA/Function.cpp:106-131` |
| 9. Allocation | `M_driver_context::allocSync` → `cuMemAlloc` in primary context; or `wrapSync` | `MAIN Target/lib/CUDA/Context.cpp:20-30,61-91` |
| 10. Dispatch | `M_driver_queue_execute` → `cuLaunchKernelEx(args, extra=nullptr)`; `arg_sizes`/`num_args` are not used by CUDA | `MAIN Target/lib/CUDA/M_driver_queue.cpp:155-196` |
| 11. Sync/events | `M_driver_queue::synchronize` → `cuStreamSynchronize`; events `cuEventRecord`/`cuStreamWaitEvent` | `MAIN Target/lib/CUDA/Queue.cpp:221-240,258-266` |
| 12. Output | Buffers returned to caller; MLRT legacy path returns `DeviceBufferRef` | `MAIN Target/lib/CUDA/Context.cpp:61-79`; `PIN max/python/max/_core/engine.pyi:271` |

MLRT's legacy CUDA path is equivalent: `CUDADeviceContext::loadFunction` → `cuModuleLoadDataEx` → `cuModuleGetFunction` (`MAIN MLRT/lib/Driver/DeviceContext/CUDA/CUDADeviceContext.cpp:2212-2280`), `enqueueFunctionExecDirect` → `cudaCallKernelDirect` → `cuLaunchKernelEx` (`:2296-2312`, `:1573-1611`), `synchronize` → `cuStreamSynchronize` (`:2387-2399`).

---

## 7. Interoperability boundary candidates for Omega sm_121 code (ranked)

Ranking criterion: smallest new surface + least MAX modification + lowest legal/ownership risk. All candidates assume the CUDApp-produced artifact is a valid cubin ELF for the device; that assumption is **not verified here**.

### Rank 1 — Co-scheduled execution: DLPack + `native_stream_handle` (no MAX code change)

**Boundary.** MAX allocates/owns a `Buffer` (or imports a CUDApp allocation via DLPack). Export the pointer with `Buffer._data_ptr()` or, preferably, wrap CUDApp memory with `max._core.dlpack.make_dlpack_capsule` and let MAX import it. Order work with `DeviceQueue.native_stream_handle`: Omega/CUDApp enqueues its own kernel on that exact `CUstream` via the CUDA driver, after MAX's prior work and before MAX's subsequent work. MAX remains responsible for its own graph; Omega's kernel is not a graph node.

**Why smallest.** No MAX compilation, no plugin, no artifact format, no MAX modification. `native_stream_handle` is explicitly documented for this use ("Lets native code outside MLRT order its own work against this stream", `PIN max/python/max/_core/driver.pyi:830-842`). DLPack zero-copy import/export is supported (`driver.pyi:1318-1333,1442-1448`; `dlpack.pyi:20-43`).

**What is missing / must be validated.**
- `_data_ptr` and `max._core.dlpack` are private/underscored; the pointer bridge is not a stability guarantee.
- Raw-pointer DLPack import (`make_dlpack_capsule`) requires the caller to provide an owner object and keep the memory alive; `Buffer.from_dlpack` retains producer ownership semantics (`driver.pyi:1322-1323`).
- CUDA context identity at the pin is unproven; both sides must use the same primary context (main evidence: `MAIN .../CUDADeviceContext.cpp:904`, `MAIN Target/lib/CUDA/Context.cpp:20-30`).
- MAX will not see the Omega launch as a graph node: no graph capture, no MAX launch trace, no MAX dependency tracking. Ordering must be enforced with `DeviceEvent` / stream ordering.
- Error propagation from an externally launched kernel into MAX's `DeviceQueue.synchronize()` is unverified. CUDA sticky errors will surface on the next driver call; whether they surface through MAX's Python error path is a probe item.
- Memory ownership: if MAX allocates and CUDApp writes, the MAX Buffer must outlive the kernel; if CUDApp allocates, the DLPack owner must outlive MAX's view.

### Rank 2 — Mojo custom op wrapper around `DeviceContext.load_function` (MAX owns execution)

**Boundary.** Build a small Mojo custom-op library (`.mojoc`) that registers an op (e.g. `omega_kernel`, `type="gpu", api="cuda", arch="sm_121a"`) and, in `execute`, calls `ctx.load_function(...)` with the cubin, then `ctx.enqueue_function(...)` with the op's tensors. MAX's graph compiler then schedules the op, MAX owns device buffers, the queue and synchronization, and the output is a normal graph result.

**Why second.** This is the smallest path that gives MAX end-to-end ownership at the pin. All required public-ish APIs exist: `@extensibility.register` (`decorators.mojo:46-75`), `load_function` (`device_context.mojo:5257-5310`), `enqueue_function` for `DeviceExternalFunction` (`:5324-5360`), argument packing (`_device_context_extras.mojo:228-266`).

**What is missing.**
- **Byte-safe cubin transport.** `load_function` takes `asm: String`; Mojo's `String` constructors require valid UTF-8 (`Mojo/stdlib/std/collections/string/string.mojo:380-394`). PTX works; cubin needs an unsafe/non-conforming `String` or an upstream API change. This is the single largest risk in this candidate.
- **Toolchain.** Building the `.mojoc` requires MAX's Mojo compiler and the `extensibility` package; the compiled wrapper targets sm_121a (`_builtin_targets.mojo:477-479`).
- **Metadata.** Entry-point name must match the cubin symbol; the wrapper must declare argument types (`DeviceExternalFunction` has no arg-size metadata; `_device_context_extras.mojo:249-250`), so the Mojo function signature must exactly match the cubin kernel ABI. Constant memory, dynamic shared memory and cluster dimensions must be specified explicitly.
- **Graph-compiler contract.** Shape function may be required for data-dependent outputs (`graph.py:316-340`); graph verification requires the symbol in the kernel library (`custom.py:127`).
- **No pinned cubin test.** The only test is PTX (`max/mojo/test/asyncrt/test_cuda.mojo:177-186`); SASS support rests on the docstring and release notes.
- **Licence boundary.** The cubin can be a separate runtime artifact; see §7.1.

### Rank 3 — MAX HAL/NeoDriver bundle path on main (MAX owns everything, but not at the pin)

**Boundary.** Using a build from `origin/main`, call `M_driver_bundle_load` with a static bundle whose bytes are the CUDApp cubin and `file_type="cubin"`, then `M_driver_function_load` for the symbol, allocate with `M_driver_memory_alloc_sync` (or wrap), create a queue, `M_driver_queue_execute`, `M_driver_queue_synchronize`. Alternatively use the Mojo client `Context.load_bundle` (`MAIN max/driver/src/max_license/_hal/context.mojo:359-396`).

**Why third.** This is the exact architectural fit for "MAX owns device memory, queues and synchronization", and the CUDA implementation treats bundle bytes as cubin/PTX with no MAX-specific wrapper (`MAIN Target/lib/CUDA/Function.cpp:68-90`). But it does not exist at the pin.

**What is missing.**
- Not in `max/v26.7.0`: need a newer MAX build/upgrade; the HAL interface is version 0.1.0 and "changes without notice" (`MAIN max/driver/src/max_license/README.md:38-39`).
- NeoDriver is **not the production path**: "MAX runs on the legacy `DeviceContext` by default" (`MAIN max/driver/src/max_license/README.md:31-37`).
- No public Python binding; requires C/C++ or Mojo client code (`MAIN max/python/max/driver/__init__.py:21-43`).
- CUDA plugin `.so` and HAL headers are MAX-licensed; redistribution constraints apply.
- Still unproven at runtime that a CUDApp cubin loads (no actual test), and no check that the entry point exists beyond `cuModuleGetFunction` failing.

### Rank 4 — Custom HAL plugin via `MODULAR_DRIVER_PLUGINS` (backend replacement, not minimal)

**Boundary.** Ship a `.so` implementing the `M_driver_*` ABI that registers a new API, and point `MODULAR_DRIVER_PLUGINS` at it (`MAIN Target/lib/DriverPlugin/DriverPlugin.cpp:286-321`). The plugin could load CUDApp cubins and own memory/queues.

**Why fourth.** This does not reuse MAX's CUDA plugin; it reimplements a large, versioned ABI (`M_DRIVER_INTERFACE_VERSION_*`, `MAIN SDK/include/HAL/M_driver_common.h:30-66`), and the graph compiler would still need to know the new device. It is effectively a backend port, not a minimal boundary. The `.so` loader path is source-visible only on main and unverified at the pin.

### Rank 5 — Inject a cubin into a MEF (not supported without upstream help)

**Boundary.** Write a MEF whose invokable references the external function and embeds the cubin bytes, then load it with `max._core.engine.read` / `InferenceSession`.

**Why lowest.** MEF is documented and "can be created by an arbitrary producer" (`MAIN MLRT/docs/GraphRT/ModularExecutorFormat.md:93-100`), and it embeds cubins in MAX's own artifacts (`PIN .../unary_elementwise_gc.py:195-199`). However, the pinned surface has no MEF writer API; the code-object encoding and the primitive that launches an external function are compiler/runtime internals, and no public primitive is documented for "call this cubin symbol". This requires a Modular change or a deep, version-fragile reimplementation. Status: **REQUIRES_MODULAR_CHANGE** for a supported path.

### Rank 6 — Register a binary-only op / ingest SASS as a `.mojoc` (unsupported)

`KernelLibrary` accepts only `.mojoc` or Mojo source (`PIN max/python/max/graph/graph.py:258-283`), and `@extensibility.register` is a compile-time Mojo construct (`decorators.mojo:46-75`). There is no binary op ABI. **UNSUPPORTED** without an upstream change.

### 7.1 Licence boundary for CUDApp code

This is an engineering analysis, not legal advice. Two materially different acts:

1. **Runtime loading of a separately produced cubin** (Rank 1/2/3): MAX reads bytes or a file and hands them to the CUDA driver. The cubin remains a separate artifact under Apache-2.0 WITH LLVM-exception; this is the cleanest boundary.
2. **Bundling/embedding** the cubin in a MAX artifact (MEF injection, `.mojoc`, a redistributed wrapper): the LLVM exception permits redistribution of compiled object code under terms of the recipient's choosing, so no CUDApp source-disclosure obligation follows. MAX's own licence and NOTICE/attribution terms still apply to the MAX portions. Keep the CUDApp NOTICE with redistributed CUDApp-derived material.

The MAX Community License's AI clause expressly permits reading/analyzing MAX and developing software that "runs on or interoperates with MAX", while forbidding use of MAX as training input to produce a substitute (`PIN Licenses/LICENSE:81-86`; `MAIN Licenses/MAX_LICENSE:66-71`). This report is analysis; no MAX code was copied into AIEN production paths, and no MAX substitute is being generated.

---

## 8. What is NOT proven

1. **No GPU execution was performed.** Every hardware-dependent statement is structural analysis. `PROBE-PLAN.md` lists the window-only steps; all are `NOT_RUN`.
2. **A CUDApp-produced sm_121 cubin was not loaded.** The claim "structurally accepted" is based on `cuModuleLoadDataEx` receiving raw bytes and `file_type="cubin"`, plus CUDA driver semantics. It is not a successful-load result.
3. **Pinned SASS support is not empirically established.** The pin's only loader test uses PTX text; cubin support at the pin rests on a docstring and a release note, and the implementation is not in the pinned source.
4. **The `String` transport risk is not resolved.** `load_function(asm: String)` documents a valid-UTF-8 precondition. Whether MAX's internal object-emission path bypasses it, and whether an external caller can safely pass cubin bytes, is unverified.
5. **Pinned context identity is unknown.** Main uses the CUDA primary context; the pinned native runtime may differ. Pointer sharing across MAX/CUDApp at the pin must be probed.
6. **Pinned allocation alignment is unknown.** Only `_aligned()` exists; the main 64-byte floor is not a pinned guarantee.
7. **Offline engine operation is unproven.** No network imports were found in the inspected Python scope, but the pinned source tree ships only `.pyi` stubs for `max._core` (its native implementation is absent), and the license states telemetry may be collected.
8. **Custom Mojo ops do not prove arbitrary SASS ingestion.** They prove a source-level Mojo registration mechanism; external assembly enters only through `load_function`, with the caveats above.
9. **No MEF writing/injection was demonstrated.** The format is documented on main; the pinned API only exports/reads MEFs.
10. **No claim about sm_121 vs sm_121a cubin compatibility.** The toolchain targets `sm_121a` for DGX Spark; whether an `sm_121` cubin runs on an `sm_121a` device is a hardware/driver question, not established here.
11. **No claim of CUDA-free execution.** MAX's NVIDIA path depends on `libcuda.so.1` and driver 580+.
12. **Main evidence is not release evidence.** All `MAIN` citations are from `da0db31`, not from the pinned release; behavior may differ in the v26.7.0 binaries.

---

## 9. License map (per relevant path)

| Path | License | Evidence |
|---|---|---|
| `/LICENSE` (repository root) | Apache-2.0 WITH LLVM-exception with LLVM Exceptions | `PIN LICENSE:1-3` |
| `max/python/max/**` (driver, engine, graph) | Apache-2.0 WITH LLVM-exception with LLVM Exceptions (file headers) | `PIN max/python/max/driver/__init__.py:4`; `max/python/max/graph/ops/custom.py:4` |
| `max/mojo/max/**` (GPU host, plugins) | Apache-2.0 WITH LLVM-exception with LLVM Exceptions | `PIN max/mojo/max/gpu/host/device_context.mojo:4` |
| `max/kernels/**` (extensibility, kernels) | Apache-2.0 WITH LLVM-exception with LLVM Exceptions | `PIN max/kernels/src/graph_compiler/extensibility/decorators.mojo:4` |
| `max/include/max/c/*.h` | Apache-2.0 WITH LLVM-exception with LLVM Exceptions | `PIN max/include/max/c/context.h:4` |
| `Licenses/LICENSE` (shipped MAX components) | Modular MAX Community License | `PIN Licenses/LICENSE:1-7`; product split `Licenses/README.md:6-13`; separately licensed components `:88-90` |
| `Licenses/Third-Party-Notices` | LLVM Apache-2.0 WITH LLVM-exception LLVM; NVSHMEM under NVIDIA SDK license; other OSS | `PIN Licenses/Third-Party-Notices:5-8,228-233` |
| `MAIN SDK/**`, `Target/**`, `MLRT/**`, `max/driver/**` | MAX License (file headers) | `MAIN SDK/include/HAL/M_driver_bundle.h:4-5`; `MAIN max/driver/src/max_license/_hal/context.mojo:1-12` |
| `MAIN Licenses/MAX_LICENSE` | Modular MAX Community License §1.4(d) AI clause | `MAIN Licenses/MAX_LICENSE:66-71` |
| `AI_TOOL_POLICY.md` | Contribution policy (not a license): label AI-assisted work, human review | `PIN AI_TOOL_POLICY.md:10-22,42-47,61-72` |

Obligations relevant to this work:
- MAX License attribution/notice requirements apply to distributed derivative works (`PIN Licenses/LICENSE:35-41`); we distribute none.
- The AI clause permits analysis and interop, forbids using MAX as AI training input to produce a substitute (`PIN Licenses/LICENSE:81-86`; `MAIN Licenses/MAX_LICENSE:66-71`). This report is analysis only.
- Separately licensed components control over the Community License for those files (`PIN Licenses/LICENSE:88-90`).
- No MAX source was copied into Omega/CUDApp/Bridge or any production path; the only copies are the verbatim main-reference extracts under `evidence/`, retained for audit.

---

## 10. Evidence index

| Evidence | Contents |
|---|---|
| `evidence/commands/01-pin-verification.txt` | HEAD, tag peel, tag object, tree hash |
| `evidence/commands/01b-remote-tag-oids.txt` | remote `ls-remote` oids for `max/v26.7.0` and `mojo/v1.2.0` |
| `evidence/commands/02-tree-hashes.txt` | `max`, `Licenses`, `Support` subtree hashes |
| `evidence/commands/03-main-head.txt` | main oid + directory listings for requested paths |
| `evidence/commands/04-main-file-extraction.txt` | main reference extraction log |
| `evidence/commands/05-path-divergence.txt` | requested paths at pin vs main; top-level trees |
| `evidence/commands/06-main-reference-hashes.txt` | git blob oid + SHA-256 for every main reference file |
| `evidence/commands/07-checkout.txt` | sparse list, HEAD, status, file count, sizes |
| `evidence/commands/10-custom-op-abi.txt` | custom-op/registration line numbers |
| `evidence/commands/11-graph-artifact.txt` | graph/module/MEF line numbers |
| `evidence/commands/12-driver-api.txt` | device/queue/buffer/DLPack line numbers |
| `evidence/commands/13-stream-sync.txt` | stream/sync/alignment/test line numbers |
| `evidence/commands/14-load-function.txt` | `load_function`, external function, PTX-only test, release note |
| `evidence/commands/15-sm121.txt` | sm_121 target and hardware table |
| `evidence/commands/16-telemetry-offline.txt` | telemetry endpoints/defaults/opt-outs/env vars |
| `evidence/commands/17-license.txt` | license headers and clauses |
| `evidence/commands/18-main-hal-citations.txt` | main HAL/loader/launch/sync line numbers |
| `evidence/commands/19-main-license-mef.txt` | MAX_LICENSE 1.4(d), MEF format, NeoDriver, main bindings |
| `evidence/commands/20-python-launch-absence.txt` | absence of Python launch/module API; debug flags |
| `evidence/main-references/**` | verbatim main-branch files used for MAIN citations |
| `SHA256SUMS` | SHA-256 manifest over this report and `evidence/` |
