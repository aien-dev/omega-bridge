# GGML strict placement primitives (not a backend)

Refs [Bridge #10](https://github.com/aien-dev/omega-bridge/issues/10).
These two stateless, handwritten seeded `.om` units implement a bounded part of
`bridge-strict-v1`. They do not register a GGML backend, execute an operator,
authenticate a graph, or enforce placement in llama.cpp yet.

## Trust boundary

The future pinned frontend adapter must derive **structural roles**, selected
nodes, exact backend identity, complete expected node identities, and current
graph/storage generation tokens from independently validated state. These
inputs are **trusted facts**, not permissions a caller can grant itself. No
node name or substring is an input. A caller relabeling an internal gather as
an embedding can fool this primitive; it must not be exposed as a security or
whole-graph attestation API.

The hook must see the complete post-allocation graph, before input setting or
any launch, and repeat admission on reuse/branch/shape/buffer changes. A plugin
sees only its partition and cannot supply that proof. Count equality alone
does not prove complete, unique node coverage. Equal generation tokens do not
prove that the owner correctly invalidated a changed graph or storage object.

## Selected-node API

`strict_node.om` exports one function:

```
strictnode(role: ulong, op: ulong, detail: ulong, backend: ulong) -> ulong
```

Only selected nodes enter this function. Selection and input/output/transfer
accounting remain the future whole-graph adapter's responsibility. File I/O,
tokenization, host input preparation and sampling are retained frontend work,
not arbitrary additional GGML compute roles authorized by this function.

| Role | Allowed GGML op values | Placement |
| --- | --- | --- |
| 1: metadata/leaf | NONE=0, RESHAPE=36, VIEW=37, PERMUTE=38, TRANSPOSE=39 | CPU=1 or qualified Omega=2 |
| 2: token-embedding gather | GET_ROWS=40 only | CPU=1 only |
| 3: transformer/internal/output computation | ADD=2, MUL=7, RMS_NORM=25, MUL_MAT=29, CONT=35, GET_ROWS=40, SET_ROWS=42, SOFT_MAX=46, ROPE=48, GLU=101 | qualified Omega=2 only |

`detail` is the GLU subtype: only `GGML_GLU_OP_SWIGLU=2` is admitted for GLU.
For every other op it must be zero. This does **not** validate tensor types,
layouts, dimensions, RoPE/attention/precision parameters, split input arity or
kernel availability. Those remain separate exact operator/descriptor gates
under CUDApp #75 and the existing Omega owners. A policy-admitted operation
must never be advertised as implemented merely because it passes this check.

Unknown roles, operations, subtypes and placements fail closed. Backend value
2 means the future adapter has already verified the exact available Omega
device/context; writing the number 2 is not device discovery or authentication.

Return order is stable: 0 = admit; 1 = unknown role; 2 = op not allowed for
role; 3 = wrong detail; 4 = wrong/missing/foreign backend. The consumer retains
the node ID and inputs for a node-specific diagnostic. No pointer is retained,
no allocation occurs, and a refusal does not poison subsequent calls.

## Snapshot API

`strict_snapshot.om` exports one function:

```
strictsnapshot(observed, expected, graph, currentgraph,
               residency, currentresidency: ulong) -> ulong
```

The expected count comes from the separately validated selected-node manifest,
not from recounting the same untrusted list. Generation tokens are nonzero,
owner-issued tokens; zero is reserved for unavailable/uninitialized state.
The caller must supply the live owner tokens, not reuse cached values twice.

Return order: 0 = consistent header; 1 = either count zero; 2 = missing/extra
node count; 3 = zero/stale graph token; 4 = zero/stale residency token. Counts
are not capped to a toy graph size. This header check does not replace exact
node-set comparison, topology/profile hashing, buffer validation or lifetime
ownership. Use the existing descriptor implementation, not another one here.

## Source and test provenance

The op/subtype numbers above come from llama.cpp
`d327bf1f0780f87b8c01b367b61853b0c291d7c4`, `ggml/include/ggml.h`, SHA-256
`2b4dd92fa992cb4ef484917a6c62fef5097698744160ccc09214fd0c459c92c7`.
API version 3 alone does not qualify another header revision. This is the
source-derived dense F16 profile, **not an executed model graph census**.
No model/GGUF hash is invented or frozen by this increment.

First-party policy assertions are in `tests/ggml/placement.om`: 59 executed
assertions on the successful path (53 distinct failure IDs, with two assertions
repeated over four metadata ops). They cover intentional CPU embedding versus
forbidden CPU internal GET_ROWS, missing/foreign devices, CONT versus metadata,
unsupported ops/subtypes, empty/incomplete snapshots, stale graph/storage and
valid admission after refusals. Numeric expectations are literal fixtures, not
computed by the production functions.

An explicit **external C reference-only** route uses the existing Omega
Omegese frontend, OSC IR emitter and interpreter at
`697539a577ee7594ba12d905062f2e09cb9cc77c`. Required source hashes and the exact
compiler-library build inputs are pinned by `reference-source.sha256`.
The manifest includes the transitive `src/compiler/model/osc_model.h` header;
compiler dependency-only output confirms 31 local reference C/header inputs,
with none outside the manifest.
The interpreter source `src/compiler/osc_interp.c` SHA-256 is
`3a77128f2cf04670a41c103c8593dd48d052add4b5f804cbc181fe9bf07df26b`.
`reference_main.c` only loads IR and invokes that existing interpreter: it has
no policy or expected-answer implementation. Shell coordinates compilation,
concatenation, note-line removal, and execution. Neither this reference route
nor a generated C/Python policy is a production runtime fallback.

The reference frontend is an older bounded integer Omegese/OSC subset, not the
current seeded compiler. It cannot qualify seeded-only facilities, globals,
host syscalls, pointers, callbacks or floating point. The runner strips only
whole `note` comment lines before parsing. An initially untyped `false` local
was refused by that frontend; the shared valid spelling `bool false` is used
explicitly. All final policy/tests fit its integer, comparison, boolean,
bounded-for and function-call subset. Reference success does not establish
native seed acceptance, code generation or native calling-convention behavior.

```
OMEGA_REFERENCE_SOURCE=/path/to/exact/reference/source sh tests/ggml/run-controls.sh
```

This command has no download/install/bootstrap/hardware behavior. It runs the
real `.om` assertions through the reference interpreter, then eight IR-compiled
policy mutants. First it also checks two source-provenance controls (interpreter
source and its transitive model header): each must fail its exact hash check
before a compiler can be invoked. A policy mutant is caught only by its exact expected assertion ID
with interpreter trap=0 and process exit 1; parse/build failures, traps, signals
and arbitrary nonzero exits cannot masquerade as successful controls.

For an already authorized Linux AArch64 host with the existing compiler pinned
by `tools/native`:

```
OMEGA_NATIVE_OMC=/path/to/existing/qualified/omc sh tests/ggml/run-native.sh
```

This runs the same combined `.om` test program through the seeded compiler.
Elsewhere it reports NOT_RUN and exits 77, never silently using the reference
route. This script has **not** been qualified on AArch64 in this increment.
The units fit native call v1's one-function-per-unit, up-to-six-ulong-arguments,
ulong-result surface, but native binding execution remains separately unrun.
The original `tools/test.sh` suite is unchanged; run both test routes explicitly
when the corresponding tools are available. No CI or production hook is added.

## Remaining gates and ownership

- Bridge #8/#9 and their native ABI/bindings are reused unchanged; this branch
  is stacked on #9 head `247bcb154c9fca0451de47124402a858d07d20f3`.
- Omega #674 owns tensor metadata/lifetime admission. No duplicate validator,
  allocator, compiler or runtime is implemented here.
- Omega #636/#637, L481/L484/L410 retain native attachment and callback/lifetime
  ownership. The existing borrowed-call ABI is not qualified retained GGML
  context/callback support. No `libggml-omega.so` is fabricated here.
- The trusted whole-graph prelaunch/reuse hook remains absent. No foreign
  forwarding edit is made or implicitly authorized by this component.
- CUDApp #75 owns real operator closure; benchmarks-mv #42 owns real-model and
  physical qualification. GB10, full model, numerical quality, ABI/DSO loading,
  actual placement and performance remain NOT_RUN/BLOCKED, not PASS.

Host-reference test success cannot close Bridge #10 or these dependency gates.

## Publication

Bridge #10 routes publication through the existing desk. The consumed Omega
#637 rules name Renda/L708 as the PR/merge/release desk. This work may be kept on
an isolated local branch for review; starting implementation is not permission
to bypass that desk, push a new remote branch or directly open a draft PR. Hand
the exact reviewed commit and evidence to the existing desk. No publication,
upstream outreach, merge, release or live-machine change is performed here.
