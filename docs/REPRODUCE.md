# Reproduce the verified host results

All commands are run from a checkout on Linux AArch64. No step requires the GPU
unless marked **window**. The three branches are:

| Repo | Branch |
|---|---|
| `aien-dev/omega-mv` | `feat/max-interop-contracts` |
| `aien-dev/CUDApp` | `feat/max-artifact-export` |
| `aien-dev/omega-bridge` | `feat/gpu-interop` |

Paths below assume sibling checkouts: `omega/`, `cudapp/`, `bridge/`.

## 0. Tools

- `gcc`, `make`, `sha256sum`, `file`, `python3` (stdlib only for the oracle and
  receipt tests).
- Omega seed compiler, checked by fingerprint
  `191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9`. Provide
  it as `OMEGA_SEED=/path/to/omc`; the bridge worktree also uses `build/omc`.
- Optional independent readers: `nvdisasm`, `cuobjdump` (CUDA 13).
- MAX tests: a venv with `modular==26.7.0` (`MAXPY=/path/to/venv/bin/python`).

## 1. Contracts and oracle (no GPU)

```sh
cd omega
sh tools/max-interop/build.sh
python3 tests/max-interop/test_contracts.py
# 26/26; contract ids 647116fc… and 003696e4…
```

Expected contract ids:
`matmul-bf16-v1` = `647116fc1ba1e1394982fc8ba181ce565293f160a6b56afc0f02b2128a675704`,
`gqa-causal-v1` = `003696e422bba7274877ba9e01a61076ea0f862f32760cbaa06c60f85a115359`.

## 2. Native artifact + cubin (no GPU)

```sh
cd cudapp
make -j8 test-native-artifact
./tools/artifact_smoke.sh evidence/MAX-INTEROP/68
```

This builds `build/artifact-export`, exports the frozen matmul and attention
artifacts, and validates them with `nvdisasm`/`cuobjdump`. To recreate the
committed evidence:

```sh
./build/artifact-export matmul --m 16 --k 16 --n 8 \
  --contract-id 647116fc1ba1e1394982fc8ba181ce565293f160a6b56afc0f02b2128a675704 \
  --out evidence/MAX-INTEROP/68/matmul-16x16x8 --commit <40-hex-source-commit>
./build/artifact-export attention --q-heads 8 --kv-heads 1 \
  --contract-id 003696e422bba7274877ba9e01a61076ea0f862f32760cbaa06c60f85a115359 \
  --out evidence/MAX-INTEROP/68/attention-hd128-gqa8 --commit <40-hex-source-commit>
```

## 3. Envelope + C2 receipt (no GPU)

```sh
cd omega
sh tests/max-interop/build_receipt.sh
python3 tests/max-interop/test_envelope.py \
  --artifact ../../cudapp/evidence/MAX-INTEROP/68/matmul-16x16x8 \
  --fixture tests/max-interop/fixtures/matmul-v1.json
# 26/26; envelope 4b17c821…, receipt f13b1bff…
```

The receipt uses the existing TEST key through `src/checker2/c2_receipt.c`; it
attests provenance only. `execution=NOT_RUN` is deliberate.

## 4. Bridge adapter (no GPU)

```sh
cd bridge
sh tools/build-gpu-adapter.sh
python3 tests/gpu/test_gpu_adapter.py \
  --artifact ../../cudapp/evidence/MAX-INTEROP/68/matmul-16x16x8
# 49/49, ACCEPT/REFUSE coverage
```

## 5. Conformance harness (CPU smoke)

```sh
cd bridge
MAXPY=/path/to/venv/bin/python sh conformance/run.sh
# CONFORMANCE HARNESS PASS; device runs NOT_RUN
```

## 6. Authorized GPU window (not executed here)

The coordinator holds `~/.local/state/aien-coordinator/CHIP-RESERVED`, so
`spark-window open` refuses. When a window is granted:

```sh
# 1. Load/run the exported cubin through the vendor loader.
cd cudapp
spark-window open maxinterop-cubin --ledger L679 --gb10 shared --quiet none --lease 10
spark-window run ./build/cubin_probe evidence/MAX-INTEROP/68/matmul-16x16x8.cubin \
  omega_matmul_bf16 16 16 8
spark-window close

# 2. Stage A: Omega native, then MAX, in separate processes.
cd ../bridge
spark-window open maxinterop-stageA --ledger L679 --gb10 shared --quiet none --lease 10
SPARK_WINDOW=$SPARK_WINDOW sh conformance/run.sh --device
spark-window close
```

A GPU run must record its `SPARK_WINDOW` id; `verify.py` refuses a GPU result
without one. Do not use `--quiet none` for a reported speed; use the quiet lock
for measurements and keep all runs, including failures.
