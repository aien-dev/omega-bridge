# DeepInfer FlopsEstimator pair counts in Omega

`flops_pairs.om` is `FlopsEstimator::floor_prefix`, `capped_prefix` and `pairs` from
[deepseek-ai/DeepInfer](https://github.com/deepseek-ai/DeepInfer) `553741557a57df44a46fb3ab72b6aafeaf945337`
`csrc/engine/flops_estimator.hpp` lines 237-257 (Apache-2.0), as an OM-2 unit bound by `tools/native`
into `omega2_floor_prefix`, `omega2_capped_prefix` and `omega2_pairs`.

- Each step is the C++ expression's step in the same order, so a step that leaves `long` traps 1
  exactly where the C++ is undefined behaviour (the pinned compilers trap on long add, sub and mul:
  `overflow.sh`, `evidence/deepinfer-flops-pairs/overflow-measurement.log`).
- Outside n >= 0, ratio > 0, cap >= 0, 0 <= begin <= end a `requires` clause traps 9. OM-2 is used
  because the pinned compilers do not check an OM-1 `requires` (same log).
- The C++ parameter `end` is `finish`: `end` is an Omega keyword (error 16).

Files:

| File | Role |
|---|---|
| `flops_pairs.om` | the unit |
| `diff.cpp` | upstream bytes (extracted, sha256-checked, GCC UBSan) vs Omega vs enumeration / step model / second closed form |
| `diff.py` | the generated Python binding vs Python oracles |
| `boundary.txt` | overflow and domain edges with Wolfram-checked values |
| `flops_estimator-omega.patch` | the pinned header with the three bodies calling `omega_native.h`; a trap becomes `TORCH_CHECK` |
| `patched.cpp` | original vs patched header on `PairTerm::count` and `query_ranges`, stub `TORCH_CHECK` |
| `callers/` | c (also BTI-enforced), cpp, python, rust, zig and go callers using only the generated bindings |
| `run.sh` | everything above plus three mutants that must be caught |
| `overflow.sh` | long overflow, `requires` and `end` probes per compiler |

Run (host only, no GPU):

```sh
DEEPINFER_SRC=<DeepInfer checkout at 5537415> OMEGA_NATIVE_OMC=<seeded omc pinned by tools/native> \
OMEGA_NATIVE_OMC2=<omega-mv e5b32567 seed/out/omc> [TORCH_INC=<torch/include>] sh examples/deepinfer/run.sh
```

Applying the patch to DeepInfer also needs `omega_native.h` on its include path and
`libomega_native.so` linked into `deepinfer._C`; that build and the upstream pytest
`tests/engine/test_flops_estimator.py` (needs the model config) were not run. Evidence:
`evidence/deepinfer-flops-pairs/`.
