<!-- Copied from the MAX 26.7.0 analysis checkout on 2026-10-23. The raw
command outputs and verbatim main-branch reference extracts cited as evidence/
stay in that analysis checkout; their SHA-256 values are in MAX-SHA256SUMS.txt.
No MAX source is copied into Omega/CUDApp/Bridge production paths. -->
# MAX 26.7.0 Interoperability Probe Plan

Companion to `FEASIBILITY-REPORT.md` (pin `527d069ee11a41ac5320af1f9402db0a66b2b868`).
This plan separates **non-GPU feature detection** from **GPU-window experiments**.

Hard rules:

- The GPU on this workstation belongs to a live serving process. **No GPU step may be run without an authorized window and exclusive access.** Every GPU step below is `NOT_RUN` in this report.
- Do not modify MAX source, do not contact Modular, do not submit upstream changes. All probes are local, read-only with respect to MAX except for temporary directories.
- Do not copy MAX code into Omega/CUDApp/Bridge. Probe scripts live under `probe/` (temporary) and evidence under `evidence/probes/`.
- Do not run destructive commands (`nvidia-smi -r`, driver reload, `rm` of MAX installs). Stop on any unexpected GPU process.
- Every probe captures: command, environment, exit status, stdout/stderr, and (where relevant) output files. Save under `evidence/probes/<probe-id>/`.

Definitions:

- `$MAXPY` — Python interpreter with MAX installed (detected in P1). Do not assume the system Python.
- `$MAXPKG` — directory containing the installed `max` package (`python -c "import max,os;print(os.path.dirname(max.__file__))"`).
- `$CORE` — the installed native extension, e.g. `$MAXPKG/_core*.so` or `$MAXPKG/_core/…so`; locate in P2.
- `$WINDOW` — a temporary directory under `/tmp/max-probe-*`, never inside a repo.

---

## 0. Preconditions and stop conditions

Before any GPU probe:

1. Confirm the pin of the checkout used for comparison:
   `git -C ~/workspace/maxinterop/max-source rev-parse HEAD` → must be `527d069...`.
2. Confirm the installed MAX version and build:
   `$MAXPY -c "import max; print(max.__file__, getattr(max,'__version__','NO_VERSION'))"`
3. Record `nvidia-smi -q` and `nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv` **without killing anything**.
4. Abort the window if any other compute process is active or if the serving process is still up. Do not share the GPU.

Non-GPU probes are safe to run at any time, but must not import CUDA contexts. Importing `max.driver` and constructing `CPU()` is safe; constructing `Accelerator()` is a GPU step because it creates a context/stream.

---

## 1. Non-GPU feature detection

These are static/import/compile-only probes. They require no device and no GPU context. None were executed for this report; only git/source inspection was performed.

### P1 — Locate interpreter and package

```bash
$MAXPY - <<'PY'
import json, os, sys
import max
print(json.dumps({
  "python": sys.version,
  "executable": sys.executable,
  "max_file": max.__file__,
  "max_dir": os.path.dirname(max.__file__),
  "version": getattr(max, "__version__", None),
}, indent=2))
PY
```

Record: path, version string, wheel/source install. If `max` is absent, stop; the remaining probes need an installed build.

### P2 — Import surface and native extension inventory

```bash
$MAXPY - <<'PY'
import importlib, os, json
mods = ["max.driver", "max.engine", "max.graph", "max._core.driver",
        "max._core.engine", "max._core.dlpack", "max._core.mlrt"]
out = {}
for m in mods:
    try:
        mod = importlib.import_module(m)
        out[m] = {"file": getattr(mod, "__file__", None),
                  "has": [n for n in ("Buffer","Device","Accelerator","DeviceQueue",
                                     "DeviceEvent","CompletionFlag","make_dlpack_capsule",
                                     "import_dlpack","InferenceSession","Model")
                          if hasattr(mod, n)]}
    except Exception as e:
        out[m] = {"error": repr(e)}
print(json.dumps(out, indent=2))
PY
find "$MAXPKG" -maxdepth 3 -name '*.so' -o -name '*.pyd' | sort
```

Pass criteria / interpretation:
- `max._core.dlpack.make_dlpack_capsule` present → raw-pointer DLPack bridge exists.
- `max.driver.DeviceQueue.native_stream_handle` present as a property → stream co-scheduling possible.
- Absence of any launch/load symbol in `max.driver`/`max._core.driver` confirms the report's Python-launch-absence claim.

### P3 — Symbol and dependency inspection of the native extension

Read-only; this is exactly the analysis permitted by the license.

```bash
for so in $(find "$MAXPKG" -name '*.so'); do
  echo "=== $so"
  readelf -d "$so" 2>/dev/null | grep -E 'NEEDED|RPATH|RUNPATH'
  nm -D --defined-only "$so" 2>/dev/null | grep -E \
    'AsyncRT_DeviceContext_(loadFunction|enqueueFunction|create|synchronize)|M_driver_(bundle_load|function_load|queue_execute)|cuModuleLoadDataEx|cuLaunchKernelEx' || true
  strings -a "$so" | grep -aE 'cubin|PTX|SASS|telemetry\.modular\.com|MODULAR_DRIVER_PLUGINS|M_driver_bundle_load' | sort -u | head -50
done
```

Record:
- `NEEDED libcuda.so.1` (or absence) — proves/refutes CUDA linkage at the installed package level.
- Presence of `AsyncRT_DeviceContext_loadFunction` / `M_driver_bundle_load` — tells which runtime generation the installed pin actually ships (pinned source is silent).
- Presence of `MODULAR_DRIVER_PLUGINS` strings — plugin env support in the installed binary.
- `telemetry.modular.com` strings — native egress surface.

Caveat: symbol visibility/static linking may hide functions; absence of a symbol is weaker evidence than presence.

### P4 — Debug/compile IR dump without a device

Compile a trivial CPU graph and stop before JIT:

```bash
WINDOW=$(mktemp -d /tmp/max-probe-ir.XXXX)
MODULAR_DEBUG=pre-jit,ir-output-dir="$WINDOW" $MAXPY - <<'PY'
from max.driver import CPU
from max.dtype import DType
from max.engine import InferenceSession
from max.graph import DeviceRef, Graph, TensorType
try:
    with Graph("probe", input_types=[TensorType(DType.float32, [4], device=DeviceRef.CPU())]) as g:
        g.output(g.inputs[0].tensor + g.inputs[0].tensor)
    s = InferenceSession(devices=[CPU()])
    s.compile(g)
except Exception as e:
    print(type(e).__name__, e)
PY
find "$WINDOW" -type f -maxdepth 3 | sort
```

Pass criteria:
- `CompilationStopped` appears (documented: `max/python/max/_core/engine.pyi:488-496`).
- The IR dir contains MLIR/Mojo for the graph, letting us see `mo.custom`, `mo.graph`, and lowering form without a GPU.
- Repeat with `MODULAR_DEBUG=ir-output-dir=$WINDOW` (no pre-jit) only if CPU JIT is acceptable; otherwise stop at pre-jit.

Also probe the `sensible` alias and `device-sync-mode` parsing (CPU-only, no execution):

```bash
MODULAR_DEBUG=sensible $MAXPY -c "from max._core.engine import DebugConfig; d=DebugConfig(); print(d.nan_check, d.assert_level, d.device_sync_mode)"
```

### P5 — Virtual-device compile and MEF export (no GPU)

This tests whether compilation and MEF export can happen with no attached accelerator. The APIs are documented at `max/python/max/_core/driver.pyi:895-1006` and `max/python/max/engine/api.py:450-455,1070-1076`.

```bash
WINDOW=$(mktemp -d /tmp/max-probe-mef.XXXX)
$MAXPY - <<'PY'
from max.driver import CPU, set_virtual_device_api, set_virtual_device_target_arch, set_virtual_device_count
from max.dtype import DType
from max.engine import InferenceSession
from max.graph import DeviceRef, Graph, TensorType
set_virtual_device_api("cuda")
set_virtual_device_target_arch("sm_121")
set_virtual_device_count(1)
dev = DeviceRef.GPU(0)
with Graph("probe", input_types=[TensorType(DType.float32, [4], device=dev)]) as g:
    g.output(g.inputs[0].tensor + g.inputs[0].tensor)
s = InferenceSession(devices=[CPU()])
c = s.compile(g)
c.export_mef("$WINDOW/probe.mef")
print("exported")
PY
xxd -l 64 "$WINDOW/probe.mef"
grep -abo $'\x7fELF' "$WINDOW/probe.mef" | head
```

Pass criteria:
- Compile succeeds under a virtual CUDA device targeting sm_121 with no accelerator present.
- MEF starts with magic `0xBEF0` (`MAIN MLRT/docs/GraphRT/ModularExecutorFormat.md:136-159`).
- Embedded ELF magic offsets show code objects. Do not attempt to parse them further yet.

If virtual-device compile fails on this build, record the exact error; it is itself a finding.

### P6 — MEF read-back and metadata

```bash
$MAXPY - <<'PY'
from max._core import engine
b = open("$WINDOW/probe.mef","rb").read()
c = engine.read(b)
print(len(c), c.names)
for m in c: print(m.name, [(t.name, t.dtype, t.shape) for t in m.input_metadata],
                   [(t.name, t.dtype, t.shape) for t in m.output_metadata])
PY
```

Pass criteria: `engine.read` accepts the exported bytes; names/metadata survive. Failure indicates the artifact is build-specific.

### P7 — `.mojoc` and custom-op packaging (no GPU)

Build a trivial custom-op package with the MAX/Mojo toolchain, if available:

```bash
mojo package path/to/probe_kernel -o "$WINDOW/probe.mojoc"
file "$WINDOW/probe.mojoc"
xxd -l 64 "$WINDOW/probe.mojoc"
grep -abo $'\x7fELF' "$WINDOW/probe.mojoc" | head
```

Purpose: determine whether `.mojoc` is itself an ELF/container with embedded object code, and whether it could carry a cubin. Do not modify MAX; this is a local package.

### P8 — Environment and config surface

```bash
env | grep -E '^(MODULAR_|MAX_|OTEL_|CUDA_)' | sort
$MAXPY - <<'PY'
from max._core import engine
for k in ("debug", "max-debug.ir-output-dir", "max-debug.pre-jit",
          "telemetry", "nvptx-compiler-path"):
    try: print(k, "=", engine.get_config_value(k))
    except Exception as e: print(k, "->", type(e).__name__, e)
PY
```

Record the precedence documented at `max/python/max/_core/engine.pyi:85-114`: global override → `MODULAR_<KEY>` env → `modular.cfg`.

Relevant variables found in source:

| Variable | Purpose | Evidence |
|---|---|---|
| `MODULAR_DEBUG` | comma-separated debug properties | `max/python/max/_core/engine.pyi:418-423` |
| `MODULAR_NVPTX_COMPILER_PATH` | override bundled ptxas | `max/docs/site/gpu/hardware-compatibility.mdx:30-36` |
| `MAX_SERVE_DISABLE_TELEMETRY` | disable serve telemetry | `max/python/max/serve/config.py:311-315` |
| `OTEL_SDK_DISABLED` | disable OTel exporters | `max/python/max/serve/telemetry/common.py:115-124` |
| `MODULAR_DRIVER_PLUGINS` | main-only plugin auto-load | `MAIN Target/lib/DriverPlugin/DriverPlugin.cpp:286-321` |
| `MAX_CUSTOM_OP_BINDING_CACHE_SIZE` | custom-op binding cache bound | `max/python/max/_interpreter_ops/custom_gc.py:155-158` |
| `MODULAR_MAX_DEBUG_PROFILING_OUTPUT_PATH` | profiler output | `max/python/max/_core/profiler.pyi:126` |
| `MODULAR_DEVICE_CONTEXT_DISABLE_HEALTHCHECK` | driver health check toggle (name found in source grep) | `evidence/commands/16-telemetry-offline.txt` |

### P9 — Offline/egress check (non-GPU)

Run the P4/P5 compile-only path under a network-isolated namespace, if permitted:

```bash
unshare -n -- $MAXPY - <<'PY'
# same CPU/virtual-device compile as P5
PY
```

If `unshare` is unavailable, use `strace -f -e trace=network -o "$WINDOW/net.log"` and inspect for `connect()` to non-local addresses. Pass criteria: compile/export completes with no egress, or the exact failing connect is identified. This probes the Python path only; native threads may be spawned but still traced with `-f`.

### P10 — Static license and provenance check

```bash
git -C "$HOME/workspace/maxinterop/max-source" rev-parse HEAD
sha256sum -c SHA256SUMS
```

Confirm the pin and that no file under `omega/`, `cudapp/`, or `bridge/` contains copied MAX code. This is a policy check, not a runtime probe.

---

## 2. GPU-window probes (all NOT_RUN)

Run only in an authorized window, with the serving process stopped and the GPU exclusively owned. Each probe must start from a clean process; a device fault leaves the CUDA context unusable (`max/docs/site/gpu/hardware-compatibility.mdx:129-131`).

General setup:

```bash
nvidia-smi --query-gpu=name,driver_version,compute_cap --format=csv
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
# Expect: compute_cap 12.1, driver >= 580, no compute apps.
```

### G1 — Context identity and stream ownership

Goal: prove MAX and an external CUDA caller share the same `CUcontext` and that `native_stream_handle` is the stream MAX uses.

Sketch (Python + cuda-python, or C++):
1. `dev = max.driver.Accelerator()`; `q = dev.default_queue`.
2. `h = q.native_stream_handle`; assert `h != 0`.
3. `cuda.cuStreamGetCtx(h)` → context handle; compare with the context current in the external caller (`cuCtxGetCurrent` after a MAX operation).
4. Create an external stream or use `h` directly; call `cuStreamQuery(h)` and confirm no error.

Pass: same context handle, nonzero stream, query succeeds. Fail: distinct contexts → pointer sharing via UVA is not safe; stop and reassess.

Evidence: handles (hex), `cuCtxGetCurrent`, `cuStreamGetCtx`, `cuStreamQuery` results.

### G2 — Ordering: MAX work → external kernel → MAX work on one stream

Goal: validate the Rank-1 co-scheduling boundary without loading the cubin into MAX.

Sketch:
1. MAX: allocate `dst`, enqueue a fill/copy on `q`.
2. External: launch a CUDApp sm_121 kernel on `h` that reads `dst` and writes `out`.
3. MAX: `q.record_event()`; `event.synchronize()`; read `out` with `to_numpy()`.
4. Repeat with `q.wait_for(other_queue)` and a second stream to confirm event ordering.

Pass: deterministic output across ≥100 iterations; no implicit sync required. Fail: race/ordering violation.

### G3 — DLPack import of a CUDApp allocation into MAX

Goal: prove MAX can consume externally allocated memory zero-copy.

Sketch:
1. CUDApp allocates `ptr` (same context) and fills it.
2. Build an exporter capsule:
   `cap = max._core.dlpack.make_dlpack_capsule(owner, ptr, device_type, device_id, dtype, shape, strides, None)`
   (signature at `max/python/max/_core/dlpack.pyi:20-29`).
3. `b = max.driver.Buffer.from_dlpack(cap)`; assert `b._data_ptr() == ptr`; run a MAX graph that reads `b`; compare.
4. Drop `b`, then free `ptr` only after MAX is done (producer-owned contract).

Pass: no copy (pointer equality), correct values, no use-after-free. Fail: pointer mismatch means a copy; use-after-free indicates ownership mishandling.

### G4 — Reverse: MAX buffer into CUDApp

1. MAX allocates `b`, fills it.
2. `cap = b.__dlpack__(stream=q.native_stream_handle)`; CUDApp imports; reads values.
3. Free order: keep `b` alive until CUDApp is done; then release.

Pass: values match; MAX's `__dlpack__` synchronized pending work per the contract (`max/tests/tests/driver/test_buffer_sync_contracts.py:13-29`).

### G5 — Load a CUDApp cubin via a Mojo custom op (Rank 2)

Goal: determine whether the pinned `DeviceContext.load_function` accepts a raw cubin in practice and whether MAX can own the launch.

Precondition: a sm_121(a) cubin from CUDApp with a known entry point and a simple pointer/int signature.

Steps:
1. Write a minimal Mojo custom-op package:
   - `@extensibility.register("probe_cubin", type="gpu", api="cuda", arch="sm_121a")` struct;
   - `execute` takes tensors + `ctx: DeviceContext`;
   - constructs `asm` from the cubin bytes (this is the risky step; try `String(unsafe_from_utf8=...)` and, as a control, a PTX version);
   - `var f = ctx.load_function[probe_sig](function_name="<symbol>", asm=asm)`;
   - `ctx.enqueue_function(f, out, in, n, grid_dim=..., block_dim=...)`;
   - `ctx.synchronize()` (or rely on MAX's graph sync).
2. Build `.mojoc` for sm_121a; compile a graph with `custom_extensions=[...]`; execute.
3. Controls:
   - same wrapper with PTX text (should pass);
   - wrong entry-point name (should raise at load);
   - a cubin with an embedded NUL / invalid UTF-8 (tests the `String` transport);
   - a cubin for the wrong arch (should fail at `cuModuleLoadDataEx` or launch).
4. Capture: `load_function` exception type/message, `enqueue_function` result, numeric output, and whether `DeviceQueue.synchronize()` observes the external launch.

Pass: cubin accepted, output correct, MAX sync covers it. Fail modes to distinguish:
- `String` construction rejects bytes → blocked at transport (expected risk).
- `cuModuleLoadDataEx` rejects → cubin invalid/arch mismatch.
- `cuModuleGetFunction` fails → symbol name wrong/mangled.
- launch succeeds but output wrong → ABI mismatch.
- launch succeeds but sync doesn't cover it → ordering defect.

Do not proceed to G6 unless G5-PTX control passes (establishes the wrapper mechanics).

### G6 — HAL bundle path on a main-branch build (Rank 3)

Precondition: a MAX build from `origin/main` (not the pin), with `CUDAPlugin.so` and HAL headers. This probe cannot be run against v26.7.0 because the headers/plugin are absent.

Sketch (C++ or Mojo):
1. `M_driver_create` → `M_driver_device_get` → `M_driver_context_create`.
2. `M_driver_static_bundle{ mapped_data = cubin_bytes(size), file_type="cubin" }`.
3. `M_driver_bundle_load(ctx, &bundle, opts, &rt)`.
4. `M_driver_function_load(ctx, rt, "symbol", len, &fn)`.
5. `M_driver_memory_alloc_sync(ctx, n, &mem)`; `M_driver_queue_create`; `M_driver_queue_copy_to_device`; `M_driver_queue_execute(q, fn, &cfg, args, sizes, nargs)`; `M_driver_queue_copy_from_device`; `M_driver_queue_synchronize`.
6. Controls: `file_type="ptx"` with PTX bytes; wrong `file_type`; wrong symbol; zero-size `wrapSync`.

Pass: numeric correctness, sync semantics, status codes. Also record whether `file_type` is enforced (source says CUDA ignores it — `MAIN Target/lib/CUDA/Function.cpp:68-90`).

### G7 — Memory alignment and views

1. Allocate many MAX buffers; print `_data_ptr() % 256`, `% 128`, `% 64`.
2. Run a kernel using 16-byte vector loads on the base pointer and on a `Buffer` slice; check `_aligned(16)`.
3. Test DLPack-imported CUDApp pointers at unaligned offsets; record driver/kernel behavior.

Pass: documented floor (64 B on main; unknown at pin) holds; slices honor `_aligned`. Fail: record actual distribution; do not assume 256 B.

### G8 — Error propagation across the boundary

1. Launch an out-of-bounds kernel externally on MAX's stream; call `DeviceQueue.synchronize()`; record whether it raises and what message.
2. Repeat with a kernel that traps; check whether MAX marks the context unusable (`hardware-compatibility.mdx:129-131`).
3. Check that MAX's next operation fails rather than silently continuing.

Pass: MAX surfaces the error (sticky CUDA error) or clearly documents otherwise. Fail: silent corruption risk.

### G9 — Graph capture with external work

1. `Model.capture(...)` while an external kernel is enqueued on the same stream.
2. Determine whether capture records the external `cuLaunchKernelEx` (it should, if on the captured stream) or fails.
3. Replay and verify.

Pass: either capture includes the external launch and replay is correct, or capture rejects it explicitly. Silent omission is a finding.

### G10 — sm_121 vs sm_121a compatibility

1. Produce two cubins from the same kernel: `-arch=sm_121` and `-arch=sm_121a`.
2. Load/run each on the DGX Spark (`sm_121` device) via G5 or G6.
3. Record `CUDA_ERROR_NO_BINARY_FOR_GPU`, `CUDA_ERROR_INVALID_PTX`, or success.

Pass: at least one form loads; document which. This is the only way to resolve the sm_121/sm_121a question; source cannot.

### G11 — MEF injection (only after G6)

Attempt only if G6 passes and legal review approves. Build a MEF with `MLIRToMEF` from a main build, or mutate a non-code section of an exported MEF and re-read it. Do not parse/rewrite code sections without a format owner. This is expected to fail or be version-fragile; record it as negative evidence.

### G12 — Plugin env targeting (only on main build)

1. Set `MODULAR_DRIVER_PLUGINS="CUDA@/path/to/CUDAPlugin.so"` and run a MAX compile/execute; confirm the plugin is loaded (logs/`strace` open/`dlopen`).
2. Set a bogus path; confirm the documented "Failed to load driver plugin" path (`MAIN Target/lib/DriverPlugin/DriverPlugin.cpp:286-321`).
3. Do **not** point it at a custom `.so` unless Rank 4 is being seriously pursued; that is a backend port, not a minimal probe.

---

## 3. Decision matrix

| Probe result | Consequence |
|---|---|
| G1 same context, G2 ordering stable, G3/G4 zero-copy | Rank 1 is viable immediately; Omega can co-schedule without MAX changes. |
| G5 PTX passes, cubin fails on `String` | Rank 2 needs an upstream byte-safe `load_function` overload or an unsafe workaround; report as `REQUIRES_MODULAR_CHANGE` for a supported path. |
| G5 cubin passes | Rank 2 becomes the preferred MAX-owned boundary at the pin. |
| G6 passes | Rank 3 is the clean architectural path on main; wait for/upgrade to a build containing HAL. |
| G8 error not surfaced | Rank 1 is unsafe for production; require explicit external synchronization/error handling. |
| G9 capture silently omits external launch | Do not combine graph capture with Rank 1 without disabling capture. |
| G10 only sm_121a loads | Require CUDApp to emit sm_121a (or PTX) for DGX Spark. |
| P3 shows no `M_driver_bundle_load` / `loadFunction` symbols | Installed pin differs from source assumptions; rerun the report's pin analysis against the wheel. |
| P5 fails | MEF export/cross-compile claims are false for this build; restrict to attached-device compile. |

---

## 4. Evidence capture template

For every probe:

```bash
ID=G2-ordering
OUT=evidence/probes/$ID
mkdir -p "$OUT"
{ echo "date: $(date -Is)"; echo "host: $(uname -a)";
  echo "pin: $(git -C "$HOME/workspace/maxinterop/max-source" rev-parse HEAD)";
  echo "max: $($MAXPY -c 'import max;print(max.__file__,getattr(max,"__version__",None))')";
  echo "gpu: $(nvidia-smi --query-gpu=name,driver_version,compute_cap --format=csv,noheader)";
} > "$OUT/meta.txt"
{ set -x; <command>; } > "$OUT/run.log" 2>&1
echo "exit=$?" >> "$OUT/run.log"
sha256sum "$OUT"/* >> "$OUT/SHA256SUMS"
```

After the window, append the probe outputs to the top-level `SHA256SUMS` manifest and update `FEASIBILITY-REPORT.md` §8 (what is not proven) with what was actually established.
