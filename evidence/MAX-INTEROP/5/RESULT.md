# omega-bridge#5 — Stage A harness result

## Commands
```
sh conformance/run.sh
# CONFORMANCE HARNESS PASS
```
The harness compiles `omega_runner` against the CUDApp worktree, generates the
frozen fixtures from the vendored oracle, runs MAX 26.7 on CPU in a separate
process, runs the Omega host-wiring path in another process, and judges both
with `verify.py`.

## Observed
- MAX CPU matmul output SHA-256 `60a7f7d4…` equals the CUDApp host output
  bit-for-bit for the frozen 4x5x3 fixture.
- MAX causal GQA matches the fp64 oracle; worst absolute error `2.7e-7`.
- `verify.py` detects a 1% scaled output, a swapped element and the wrong head
  map.
- MAX version 26.7.0, accelerator API `cpu`; no device opened.

## NOT_RUN
GB10 Stage A (Omega native API and MAX graph on the chip), Stage B, and all
paired benchmarks. The chip is reserved; `--device` is refused without
`SPARK_WINDOW`. The harness's GPU path is implemented and untested.
