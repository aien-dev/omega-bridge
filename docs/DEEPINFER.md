# DeepInfer as a bridge target

Status: PROPOSED target. The inventory and the import verdicts below are EXERCISED on the host
(AArch64, no GPU). No DeepInfer function is converted today. Nothing here is QUALIFIED, MERGED or
DEPLOYED.

Ownership follows ARCH-0042: Omega owns computation, CUDA++ (aien-dev/CUDApp) owns GPU execution,
Omega Bridge owns compatibility. Source translation adapters live in omega-mv; the Python front end of
the porting tool lives in aien-dev/babel.

## Pins

| item | pin |
|---|---|
| deepseek-ai/DeepInfer | `553741557a57df44a46fb3ab72b6aafeaf945337` (2026-10-25), Apache-2.0, package 0.1.0, Python >= 3.12 |
| vendor submodules (gitlinks, not fetched) | DeepEP `f6aa38fe`, DeepEP-Ascend `3b25377d`, DeepGEMM `1fc9c669`, DeepGEMM-Ascend `3a353262`, DeepSelect `bfa4507d`, FlashMLA `2e5429fc` |
| omega-bridge | `1958a189` (main) |
| omega-mv adapters | PR #839 head `656192e0`: `build/L627/import/python-import` sha256 `4c74b1f7…`, `build/S2/c-i64-import` `4cd9f018…`, `build/L739/cpp-import` `ed90e640…` |
| aien-dev/babel | `156360f8` (adapter pin omega-mv `2d4c6407`) |
| aien-dev/CUDApp | `b5746b94` |

Upstream targets NVIDIA SM100 and Huawei Ascend 950 (README lines 35-36). The Spark GPU is GB10
(sm_121). Running any DeepInfer kernel on GB10 is NOT_RUN and outside upstream's stated support.

## Three layers

Every DeepInfer component falls in one or more of these layers, each owned by an existing component.

1. Source translation: a function is imported by an omega-mv adapter (directly or through babel) into
   OMSA, lowered to `.om`, and called through bridge bindings. Bounded by the import profiles.
2. Operator mapping: a tensor kernel (TileLang, DeepGEMM, FlashMLA, DeepEP, DeepSelect) is matched to
   an Omega computation and a CUDA++ realization. Nothing converts these automatically today.
3. Framework attachment: torch and `deepinfer._C` callers are switched to Omega-generated code through
   bridge bindings (`tools/native`) or the PyTorch attachment (bridge #23, #30, both open drafts).

## Component inventory

Python sizes are file and line counts at the pin; csrc is C/C++.

| component | size | layer | today |
|---|---|---|---|
| `model_executor/layers/tilelang_ops` (30 kernel families, each a `cuda/` and an `asc/` file) | 93 files, 23,331 lines | 2 | no Omega or CUDA++ counterpart; extension E |
| `model_executor/models` (deepseek, 23 `v4_modules`: attn, mla_attn, index_attn, compress, engram, hc, mhc, moe, mlp, rope, norm, yoco, linear, heads, …) | 34 files, 7,051 lines | 2 | routed-expert FP4 decode exists as a seeded-Omega host port in aien-sovereign-core-mv #780 (draft, `om/dsv4/fp4dq.om`); MLA, index attention, compress, engram, hc/mhc have no Omega port |
| other `model_executor` (top-level files, layers outside tilelang_ops, eplb, input_metadata, parallel_utils) | 30 files, 4,925 lines | 2, 3 | CUDApp codegen covers attn, attn256, pattn, gdn, gemm, bf16, qmma, moe, moe2, router, dec, pf, tc, tern, qg at Qwen3.6-35B shapes; DeepSeek shapes NOT_RUN |
| `csrc/engine` (scheduler 1,329 lines, prepare_tensor_input_v4, sequence, block_manager, flops_estimator, mtp_varlen, zos, outputs, prepare_sample) + `graph_timer`, `cuda_utils`, `asc_utils` | 33 files, 5,908 lines | 1, 3 | 0 functions import (below); FlopsEstimator pair counts are extension D |
| `deepinfer._C` (pybind11, 15 Python importers) | 22 classes, 153 `def` entries | 3 | the bridge native ABI carries scalars and flat arrays only; no class or handle form (extension F) |
| `engine`, `worker`, `distributed`, `entrypoints` | 20 files, 5,421 lines | 1, 3 | 0 functions import |
| `structure_output` (xgrammar) | 5 files, 595 lines | 3 | no Omega counterpart |
| `hugging_face`, `ve`, `npu_ops`, `deep_cluster` | 29 files, 3,221 lines | 1, 3 | no Omega counterpart; `npu_ops` is Ascend-only |
| `tests` | 19 files, 3,117 lines | oracle | need torch and an SM100 or Ascend device; NOT_RUN |

## External dependencies

"Files" counts DeepInfer Python files that import the module at the pin.

| dependency | version | files | role | Omega replacement |
|---|---|---|---|---|
| torch | 2.13.0+cu132 | 129 | tensors, CUDA streams and graphs, distributed | CUDA++ runtime plus Omega computation; attachment is bridge #23 (CPU, `torch.compile` backend) and #30 (CUDA++, pending) |
| tilelang | 0.1.15 | 60 | JIT kernel DSL for every `tilelang_ops` family | none; extension E |
| tile-kernels | 2.1.0 | 46 | prebuilt TileLang kernels | none; extension E |
| DeepGEMM | `1fc9c669` | 9 | FP8/FP4 dense and grouped-MoE GEMM | CUDApp gemm/qmma/moe/moe2 at Qwen shapes; FP4 expert decode in core-mv #780 (host, draft) |
| FlashMLA | `2e5429fc` | 4 | MLA attention | none |
| flash-attn-4 | 4.0.0b34 | 1 | prefill attention | CUDApp attn/attn256/pattn at Qwen shapes |
| DeepEP | `f6aa38fe` | 5 | expert-parallel all-to-all across GPUs | none; a single GB10 has no expert-parallel peer [INFERENCE] |
| DeepSelect | `bfa4507d` | 4 | sparse index selection | none |
| xgrammar | 0.2.2 | 3 | grammar token masks | none |
| transformers, tokenizers | 4.50.0, 0.21.4 | 4, 1 | config and tokenizer | none |
| safetensors | 0.8.0 | 2 | weight files | none recorded here |
| pybind11 | 3.0.1 | (csrc) | `deepinfer._C` | `tools/native` bindings, scalars and arrays only (extension F) |
| pyzmq, posix_ipc | 27.1.0, 1.3.2 | 1, 1 | process messaging | none |
| torch-npu, CANN, DeepGEMM-Ascend, DeepEP-Ascend | 2.13.0rc1, 9.2, `3a353262`, `3b25377d` | 2 (torch_npu) | Ascend backend | out of scope: no Ascend device |
| einops, numpy, scipy, sympy, orjson, pillow, psutil, requests, huggingface_hub, tabulate, tqdm, ninja | requirements.txt pins | | host support | not on the conversion path; none |

## Measured translation coverage (layer 1)

Replay: `OMEGA_MV=<built omega-mv> sh evidence/deepinfer/run.sh` re-runs all 30 inputs below and prints
`DEEPINFER-COVERAGE REPLAY PASS` when every exit status matches. Negative control: replacing
`ctrl_pos.py` with the unmasked control makes that row `FAIL` and the script prints
`DEEPINFER-COVERAGE REPLAY FAIL`. Both outcomes were observed on 2026-10-31.

### Python (profile python-u64-v1)

`evidence/deepinfer/select_candidates.py` walks all 270 `.py` files (1,915 functions) and keeps
functions whose body is one `return` over parameters and integer literals. Six qualify; the remaining
1,909 are outside every Python profile by shape (statements, calls, tensors, attributes) and were not
sent to the adapter. The six were sent verbatim (`py-verbatim/`) and then with annotations,
docstrings and leading underscores removed (`py-stripped/`) to expose the next refusal.

| function | location | verbatim | stripped |
|---|---|---|---|
| `is_power_of_two` | `model_executor/layers/tilelang_ops/common.py:30` | 66 TYPE (annotation) | 68 ARITHMETIC (`&`, `==`) |
| `ceil_div` | `tilelang_ops/common.py:34` | 66 TYPE | 68 ARITHMETIC (`//`, unmasked) |
| `i64` | `tilelang_ops/random_sampling.py:49` | 66 TYPE | 69 CONSTRUCT (conditional expression) |
| `expanded_image_token_len` | `ve/processor/image_processor.py:76` | 72 SOURCE_FORM (docstring) | 68 ARITHMETIC (unmasked `+ *`) |
| `_align_to_multiple` | `worker/cache_engine.py:36` | 72 SOURCE_FORM (docstring) | 68 ARITHMETIC (`//`) |
| `_needs_compress_state` | `worker/cache_engine.py:119` | 71 SIGNATURE (leading `_`) | 68 ARITHMETIC (comparison) |

Controls: `ctrl_pos.py` (one masked u64 add) imports, rc 0, 324 bytes; `ctrl_unmasked.py` refuses 68.

The refusals are the profile working as specified, not adapter bugs. python-u64-v1 refuses unmasked
arithmetic because Python `int` is unbounded; idiomatic DeepInfer integer code is unmasked. The S2 Python
form (`python-i64-select-v1`) requires the `_ck(...)` range helper and also excludes `//`, `%`, `&` and
shifts (translation-s2-v1 section 1), so S2 would not accept these either.

### C and C++ (FlopsEstimator, `csrc/engine/flops_estimator.hpp`)

`floor_prefix`, `capped_prefix` and `pairs` (lines 239-257) were chosen by reading the file as the csrc
functions closest to the integer profiles. No systematic csrc scan was run; the babel splitter covers
Python only.

| input | adapter | rc | refusal |
|---|---|---|---|
| verbatim, no header | c-i64-import, cpp-import | 72 | UNSUPPORTED_PREPROCESSOR (missing required header line) |
| verbatim + `#include <stdint.h>` (`*.hdr-c`) | c-i64-import | 66 | UNSUPPORTED_TYPE (`static`, default argument) |
| verbatim + `#include <cstdint>`, `std::int64_t` (`*.hdr-cpp`) | cpp-import | 69 | UNSUPPORTED_CONSTRUCT (specifiers) |
| `floor_prefix` rewritten as one C17 expression (`floor_prefix.c17`) | c-i64-import | 68 | UNSUPPORTED_ARITHMETIC (division) |

Controls: `ctrl_pos.c17` rc 0 (345 bytes); `ctrl_pos.hdr-cpp` (`calc`, `std::uint64_t`) rc 0 (361
bytes); `ctrl_name.hdr-cpp` (same body, name `f`) rc 71, because cpp17 profiles accept only `calc` or
`omega_*` names.

### Result

No DeepInfer function imports with the current adapters: 1,909 Python functions fall outside every
profile by shape, the 6 in-shape Python functions refuse, and the 3 C/C++ functions tried refuse in
every form. The gaps, in order of reach: integer division and remainder with each language's rounding,
unbounded Python `int`, comparisons and selects outside the `_ck` form, specifiers and default
arguments, classes, and every tensor operation.

## Extensions

Each gap becomes reusable work in the component that already owns that layer. No DeepInfer-specific
converter is added.

| id | extension | owner | status |
|---|---|---|---|
| A | Python splitter in babel: split a module into functions, route each to `python-import`, record per-function verdicts and a refusal histogram | aien-dev/babel | IMPLEMENTING (lane BabelPySplit, draft PR pending) |
| B | S2.1 integer profile: i64 division and remainder with C/C++ truncation and Python floor rounding as distinct ops, `min`/`max`, trap on divisor 0 and on `INT64_MIN / -1`. Reaches `floor_prefix`, `capped_prefix`, `pairs`, `ceil_div`, `_align_to_multiple` | omega-mv translation | PROPOSED (protocol change; needs the S2 owner's review) |
| C | `python-int-checked-i64` profile: idiomatic Python `int` (annotations `int`/`bool`, docstrings, `//`, `%`, `&`, comparisons, conditional expressions) imported as i64 whose realization traps whenever CPython's exact result leaves -2^63..2^63-1. Wrapping is not a refinement here, because out-of-range Python results are defined values, not errors. Reaches 5 of the 6 Python candidates; `i64` stays refused (literal 2^63 is outside i64) | omega-mv translation | PROPOSED; depends on B for `//` and on a trapping `long` realization (S2 section 5 records wrapping `long` at omc `f8588e10`; lane D measures the current pin) |
| D | FlopsEstimator pair counts as native `.om` with domain contracts, bridge bindings, a differential against the upstream functions and a caller-switch patch | omega-bridge | IMPLEMENTING (lane FlopsPairsNative, draft PR pending) |
| E | TileLang kernel importer: TileLang `T.prim_func` bodies to Omega computation plus CUDA++ kernels, family by family (start with `norm`, `gather`, `quant`) | CUDApp with omega-mv | PROPOSED; parity needs a GPU window; upstream kernels target SM100, GB10 is sm_121 |
| F | Handle ABI for bindings: opaque object handles with constructor, method and destructor entries so `py::class_` surfaces such as `Scheduler`, `BlockManager` and `Sequence` can be served by Omega units | omega-bridge `src/native.om` | PROPOSED |

## Switching callers

A caller moves to Omega only after its `.om` unit is differentially checked against the pinned upstream
function and its bindings pass `tests/native/run.sh` (`NATIVE-CALL PASS` with all seven callers). The
switch is a patch against the DeepInfer pin, kept in this repository (`examples/deepinfer/`), not a fork.
Every dependency in the table above stays listed until its replacement is EXERCISED in that way.
