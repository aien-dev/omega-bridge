# MAX CPU route: an Omega kernel as a MAX 26.7.0 graph custom op

Status: **EXERCISED(host CPU)** on the DGX Spark's Grace aarch64 host, 2026-10-30/31. This is a
host-CPU run, not a hardware qualification and not a GPU result. Every graph is built on
`DeviceRef.CPU()` and the session is `InferenceSession(devices=[CPU()])`, so no kernel ran on the
GPU. That alone does not keep the GPU closed: MAX 26.7.0 `Graph()` (`_populate_device_info_mapping`)
creates an `Accelerator()`, a CUDA context, whenever `accelerator_count() > 0`. The run of record
did not hide the GPU, so [INFERENCE] each of its graph processes opened a GB10 context. On
2026-10-31 a rerun at `6ec6dab7` exited 1 for that reason: the last `measure` child (matmul
256x256x256 warm) failed in `Accelerator()` with `CUDA_ERROR_OUT_OF_MEMORY` while the GPU was busy;
every check and negative control had passed. `run.sh` and `mogg-cache-repro.sh` now export
`CUDA_VISIBLE_DEVICES=` and `omega_max.py` exits 2 while an accelerator is visible. With the GPU
hidden, the 2026-10-31 rerun exited 0 (`OMEGA MAX CPU: PASS`, 16 of 16 measurements) and the warm
omega 16x16x8 `maxrss_kib` was 495648 against 589472 in the GPU-visible rerun.

## What runs

`max-cpu/omatmul.om` (seeded Omega, OM-2) computes `C[M,N] = A[M,K] @ B[K,N]` with bf16 inputs
widened exactly to f32 and an in-order f32 accumulation. `tools/native` (the bridge's existing
native path, unchanged) compiles it into `libomega_native.so`, exporting `omega2_omatmul`.
`max-cpu/kernels/__init__.mojo` registers the MAX custom op `omega_matmul` (`type="cpu"`); its only
work is to resolve `omega2_omatmul` with `OwnedDLHandle()` (dlopen(NULL) + dlsym over the library
the harness loads `RTLD_GLOBAL`), call it on the tensors' buffers, and raise on a nonzero status or
result. `max-cpu/omega_max.py` builds the MAX graphs, checks the numbers and measures.

Graph (`both`/`omega`): f32 inputs A and B (already bf16-rounded by the harness) are cast to bf16
in the graph (exact), flattened and concatenated into `ab`; the shape `s = int64[3]` is a graph
input; `C = ops.custom("omega_matmul", ...)`. Variants: `omega_nocat` takes the concatenated bf16
buffer as a graph input; `concat` is the cast + concat alone; `matmul` is MAX's own `ops.matmul` on
the same f32 values.

## Pins

| Item | Value |
|---|---|
| MAX | `max`, `max-core`, `max-mojo-libs`, `modular` 26.7.0 = modular/modular `527d069ee11a41ac5320af1f9402db0a66b2b868` (max/v26.7.0) |
| Mojo | `mojo`, `mojo-compiler` 1.2.0 |
| Python / numpy | 3.12.3 / 2.5.4 (venv `~/workspace/maxinterop/venv`) |
| omc stage 1 | `git -C ~/workspace/omega show 55f9b0af:seed/out/omc`, sha256 `734f0a39319fbfa930bcc62cb30dbf06d47d78e126372b74f5baf478e6126b61` |
| omc stage 2 | `ec07d25d:seed/out/omc`, sha256 `499236398aabc652e2dae27fe4bdc4c5db3d3726314356e0dbef23e3345803ec` |
| Unit ident | `raw/idents.txt`: `unit=omatmul abi=2 profile=OM-2 src=214493520a48…` (mutant `src=8e2a67f1bd70…`) |
| C compiler | gcc 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1), driven by `tools/native` |
| Bridge base | omega-bridge `1958a1895279c0d4869bab39eaa20f070b174a6c` (origin/main) |

## Reproduce

```sh
TMPDIR=/dev/shm taskset -c 5-9 nice -n 19 ionice -c3 max-cpu/run.sh            # ~11 min
TMPDIR=/dev/shm taskset -c 5-9 nice -n 19 ionice -c3 max-cpu/mogg-cache-repro.sh  # after run.sh
```

`run.sh` extracts both omc stages from git objects and checks their sha256, builds the library and
the mutant, writes the glue variants (each substitution must match exactly once), and gives every
MAX process an **empty `MODULAR_CACHE_DIR`** (see the cache observation below). It exits 0 and
prints `OMEGA MAX CPU: PASS` only when every control passes and every negative fails as required.
Run of record: exit 0, wall time 667 s; console output:

```
check         OMEGA_MAX_CHECK: PASS
neg-shape     OMEGA_MAX_NEG_SHAPE: PASS
neg-wrongsym  OMEGA_MAX_NEG_LOAD: PASS
neg-extcall   OMEGA_MAX_NEG_LOAD: PASS
neg-mutant    OMEGA_MAX_CHECK: FAIL
OMEGA MAX CPU: PASS (controls green, negatives red as expected)
```

Raw output: `raw/check.log`, `raw/check.json`, `raw/neg-shape.{log,json}`, `raw/neg-wrongsym.log`,
`raw/neg-extcall.log`, `raw/neg-mutant.{log,json}`, `raw/build-lib.log`, `raw/build-mutant.log`,
`raw/measure/summary.tsv` plus one JSON per series with every latency (`lat_ns`), `raw/measure.log`,
`raw/mogg-cache-repro.log` and `raw/mogg-cache-repro/`. The first run's two red harness logs
(`run1-harness-red/`) are kept: the harness compared only the last line of MAX's multi-line error
and expected the JIT's stderr text in the exception; both were harness defects, fixed before the
run of record, and the kernel and glue were unchanged.

## Numeric check (control)

Shapes (M,K,N): (1,1,1), (3,5,7), (16,16,8), (33,17,9), (64,128,32), (256,256,256); cases random
(bf16-rounded normal), zeros, identity (K = N), and large (inputs scaled by 2^60, 16x16x8). The
reference is numpy float64 of the same bf16 values. Pass bound, elementwise:
`|C - ref| <= tol(K) * (|A| @ |B|)` with `tol(K) = 2*gamma(K-1, 2^-24)`, the standard bound for an
f32 recursive sum of exact products, doubled.

`WolframLanguageEvaluator: g[n_,u_]:=n u/(1-n u); u32=2^-24; u64=2^-53; Table[{k, N[g[k-1,u32]+g[k-1,u64],17], N[2 g[k-1,u32],17]}, {k,{1,5,16,17,128,256}}]`
-> K=1: 0, 0; K=5: 2.384186363890841e-7, 4.768372718899898e-7; K=16: 8.940704726574863e-7,
1.788140941984304e-6; K=17: 9.536752276781760e-7, 1.907350451803638e-6; K=128:
7.569847202727132e-6, 1.513969437725460e-5; K=256: 1.519941546475356e-5, 3.039883087288574e-5.

Result (`raw/check.log`): all 15 cases PASS. The largest bound ratio was 0.067 (33x17x9 random);
256x256x256 random max abs error 1.75e-05, ratio 0.00677. Against MAX's own `ops.matmul` on the
same inputs, every case was **bit-identical** (`ratio_max=0 maxerr_max=0`).

## Negative controls

| Control | Expectation | Observed (raw log) |
|---|---|---|
| wrong symbol: glue asks for `omega2_omatmul_missing` | load/execute error naming it | `symbol not found: omega2_omatmul_missing` → PASS (`neg-wrongsym.log`) |
| plain `external_call["omega2_omatmul", UInt32]` glue (lib loaded `RTLD_GLOBAL` first) | model setup fails | stderr `JIT session error: Symbols not found: [ omega2_omatmul ]`, exception `Failed to materialize symbols` → PASS (`neg-extcall.log`) |
| shape [16,15,8] on a 16x16x8 buffer | Omega result 2 | `omega_matmul refused: status 0 result 2` |
| shape [5000,16,8] | result 1 | `... result 1` |
| shape [0,16,8] | result 1 | `... result 1` |
| shape [12,16,12] (ab matches, c does not) | result 3 | `... result 3` |
| valid call after the four refusals | correct numbers | ratio 0.0336, PASS |
| graph construction `ops.matmul` [16,16]x[15,8] | refused before compile | `Failed to create op 'MatmulOp'` → PASS (`neg-shape.log`) |
| mutant: `ai = mul i k` → `ai = mul i n` (A row stride N) | numeric check FAILs | FAIL on 3x5x7, 16x16x8, 16x16x8 large, 33x17x9, 64x128x32 (ratios up to 1.41e+07); shapes with K = N or zero data still pass, as they must (`neg-mutant.log`) |

The mutant was meant to be a transposed C write (`C[j*M+i]`), but every form of it fails to compile
with omc error 12 (more than 16 live values) because `brow` is already at the limit; the A-stride
mutant is the one-token index fault that compiles.

Why `external_call` fails: in the pinned source only `mojo run` passes `libraryPaths` to the
ExecutionEngine; the MAX kernel JIT does not resolve symbols from the process image, and
`LD_PRELOAD` gave the same error. The Mojo FFI docs at the pin (c-ffi.mdx, Limitations) say
`external_call()` cannot load dynamic libraries and point to `OwnedDLHandle`.

## Measurements (EXERCISED(host CPU), `taskset -c 10-14`; historical run of record. Cores 10-14 are reserved on this host now: rerun on 5-9)

`measure-all` starts one child process per series. `cold_ns` runs from process start to the end
of the first execute (import, graph build, compile, load, first call); `fresh` = empty
`MODULAR_CACHE_DIR`, `warm` = the same directory reused by a second process. Then 20 warm-up
calls and 300 timed calls (`perf_counter_ns`, including the copy-out to numpy). Peak RSS is
`ru_maxrss` of the child. Source: `raw/measure/summary.tsv`. KiB → MiB:
`WolframLanguageEvaluator: N[{1292596, 595448, …, 595948}/1024, 5]` -> `{1262.3, 581.49, …, 581.98}`.

| op | shape | cache | cold s | p50 µs | p99 µs | peak RSS MiB |
|---|---|---|---|---|---|---|
| omega | 16x16x8 | fresh | 12.65 | 72.5 | 282.2 | 1262 |
| omega | 16x16x8 | warm | 3.56 | 156.3 | 471.1 | 581 |
| omega_nocat | 16x16x8 | fresh | 11.46 | 105.3 | 463.3 | 1239 |
| omega_nocat | 16x16x8 | warm | 3.57 | 49.4 | 266.8 | 580 |
| concat only | 16x16x8 | fresh | 12.51 | 34.3 | 261.9 | 1262 |
| concat only | 16x16x8 | warm | 3.54 | 36.1 | 51.5 | 581 |
| ops.matmul | 16x16x8 | fresh | 30.53 | 36.5 | 451.8 | 1406 |
| ops.matmul | 16x16x8 | warm | 3.61 | 35.4 | 270.5 | 580 |
| omega | 256x256x256 | fresh | 12.76 | 49386.6 | 50393.1 | 1263 |
| omega | 256x256x256 | warm | 3.56 | 49399.2 | 49896.5 | 582 |
| omega_nocat | 256x256x256 | fresh | 11.11 | 49246.7 | 49523.3 | 1239 |
| omega_nocat | 256x256x256 | warm | 3.58 | 49235.3 | 49566.0 | 582 |
| concat only | 256x256x256 | fresh | 12.52 | 172.4 | 3015.6 | 1263 |
| concat only | 256x256x256 | warm | 3.61 | 157.2 | 1031.9 | 582 |
| ops.matmul | 256x256x256 | fresh | 28.40 | 320.0 | 1901.8 | 1408 |
| ops.matmul | 256x256x256 | warm | 3.47 | 439.3 | 1997.3 | 582 |

Quantile cross-check: all 32 p50/p99 values of `summary.tsv` were recomputed from the raw
`lat_ns` with `WolframLanguageEvaluator: Quantile[#, q, {{1,-1},{0,1}}]` for q = 1/2, 99/100
(numpy's linear rule) and agree exactly, e.g. omega 256 warm -> `{4.9399161*^7, 4.989648293*^7}`,
matmul 256 warm -> `{439308.5, 1.99725278*^6}`.

Reading:
- At 256x256x256 the Omega op is 112x (warm) to 154x (fresh) slower than `ops.matmul`:
  `WolframLanguageEvaluator: N[{49399161/439308.5, 49386625/319987}]` -> `{112.447…, 154.339…}`.
  Throughput `N[2*256^3/49399161]` -> 0.679 GFLOP/s for Omega versus `N[2*256^3/439308.5]` ->
  76.4 GFLOP/s for MAX. The Omega unit is a scalar, single-threaded triple loop with bounds-checked
  loads; MAX's kernel is tiled, vectorised and multi-threaded across the five pinned cores.
- The in-graph concat is not the cost: omega_nocat / omega at 256 warm is
  `N[49235279/49399161]` -> 0.997, and the concat alone is `N[157226/49399161]` -> 0.32% of the
  Omega op.
- At 16x16x8 every series is within a few tens of µs of the per-execute floor (concat alone ≈
  `ops.matmul` ≈ 35 µs p50) and the fresh/warm spread (72 vs 156 µs for the same graph) shows
  that this size measures dispatch noise, not the kernel.
- A warm cache cuts cold start from 11–31 s to about 3.5 s and peak RSS from about 1.24–1.41 GiB
  to about 0.58 GiB; the first `ops.matmul` compile is the slowest (28–31 s).

## MAX 26.7.0 observation: stale compiled kernel after a glue edit

Not filed upstream (human-only). Repro (`max-cpu/mogg-cache-repro.sh`, log `raw/mogg-cache-repro.log`):

1. Package dir `P/kernels` holds the `external_call` glue (sha256 `6684216a…`); run with
   `MODULAR_CACHE_DIR=A` → `Failed to materialize symbols` (expected).
2. Replace `P/kernels/__init__.mojo` with the working `OwnedDLHandle` glue (sha256 `6159e31a…`),
   same cache `A` → **the same failure**, `JIT session error: Symbols not found: [ omega2_omatmul ]`.
3. Same new glue, empty cache `B` → runs.
4. The new glue copied to a **different path** `Q/kernels`, cache `A` → **the same failure**.

The `__kernel_<hash>` names in the materialisation error are byte-identical in steps 1, 2 and 4
(md5 of the sorted name list `09abc084…` in all three). Step 2 adds five cache entries (one
`.max_cache/mof/mef`, one `.mogg_cache`, three `.mojo_cache/mojo/transform`;
`raw/mogg-cache-repro/cacheA-after-{1,2}.txt`), yet the stale kernel object is still linked. The
first observation used the default `~/.cache/modular` and took the same shape.
`[INFERENCE]` The key under which MAX 26.7.0 caches a compiled custom-op kernel ignores both the
Mojo source contents and the package path, depending only on what reaches the kernel names
(op name, signature, graph). Workaround used here: an empty `MODULAR_CACHE_DIR` per run.

## Host dependencies

| Dependency | Version | Role | Omega replacement |
|---|---|---|---|
| MAX engine + graph API | 26.7.0 | graph build, compile, schedule, tensors, `ops.matmul` reference | none at this boundary: the goal is to run Omega *under* MAX |
| Mojo glue `max-cpu/kernels/__init__.mojo` | Mojo 1.2.0 | registers the custom op, dlsym + call | none while MAX accepts custom ops only as Mojo `@compiler.register` structs |
| Python harness `max-cpu/omega_max.py` | CPython 3.12.3 | graph driver, checks, timing | none for the MAX Python API; oracle could move to an Omega f64 unit |
| numpy | 2.5.4 | bf16 rounding of inputs, float64 reference, quantiles | an Omega f64 reference unit (verification oracle) |
| gcc | 13.3.0 | compiles the bridge's emitted C (`tools/native`) | gap 6 below: native object/shared-library output from omc |
| glibc `dlopen`/`dlsym` | system (Ubuntu 24.04) | `OwnedDLHandle()` resolves `omega2_omatmul` | same as gap 6 |
| omc stage 1 / stage 2 | sha256 above | Omega compiler | first party |

## Omega gaps met, as omega-mv extension proposals

1. **More function-mode parameter slots, or descriptor parameters.** OM-2 function mode has six
   slots and an unsized view takes two, so A, B and C cannot be three views plus a shape.
   Proposal: raise the slot count to at least 8, or admit a `struct` parameter whose fields are
   view descriptors. Today A and B travel concatenated, which forces an in-graph concat.
2. **Floating element types in unsized views.** Views carry integer cells only, so f32 data moves
   as `uint` bit patterns and every load needs `bitcast`. Proposal: `view f32 *` / `edit f32 *`
   (and f16/bf16 once gap 3 lands) with the same bounds checks.
3. **bf16 (and f16) as types.** bf16 is widened by `shl 16` + `bitcast f32` by hand; there is no
   narrowing conversion with round-to-nearest-even. Proposal: `bf16`/`f16` scalar types with
   exact widening and RNE narrowing, so outputs could also be bf16.
4. **The 16-live-value limit has no spill (error 12).** It forced the dot product into a helper
   function and made a one-expression transposed-index mutant uncompilable. Proposal: spill to
   frame slots instead of refusing; keep error 12 only for a hard frame-size limit.
5. **The per-loop 1,000,000-pass cap.** A flat loop over M*N*K stops at 100^3; the kernel nests
   loops to stay under it. Proposal: a declared bound (`for p ulong k max 4096`) checked once at
   entry, replacing the fixed per-loop cap for loops with a proven bound.
6. **No native object or C ABI export from omc (FR-7).** The callable symbol comes from the
   bridge's emitted C compiled by gcc. Proposal: omc emits an ELF relocatable or shared object
   with the bridge's `omega2_` ABI directly, removing gcc from the build path.
