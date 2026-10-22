# Entirely Omega CUDA replacement programme

User direction: get to where CUDA C++ can be replaced entirely with Omega.
Owner: L605; reuse existing compiler L408, runtime migration L419, canonical motor
L457 and driver L332 rather than creating competing workers.

## Meaning of done

A supported CUDA C++ workload enters the Omega compiler; seeded-Omega frontend,
typed checking, optimization and native backend produce GPU code; seeded-Omega
runtime allocates, launches, synchronizes and recovers; results match independently
compiled original sources on the real device. Construction and production execution
contain no first-party C/Rust/Python, generated-C intermediate, nvcc/NVVM/PTX assembler,
CUDA runtime or hidden fallback. Host argument/process/file shell glue is retired
through its existing native platform work, not silently counted as Omega.

Compatibility and implementation language are different gates. Accepting CUDA C++
source does not require building Omega on C++; Omega-native source must also reach
the same native GPU path. Foreign tools remain explicitly external test oracles.

Full CUDA C++ replacement is not claimed while an ordinary documented source
feature is rejected, necessary library/API is absent, hardware behavior is NOT_RUN,
or a live consumer still depends on a retired component. Scope is versioned by
language standard, API/ABI, architecture and bounded hardware resources, never
universal support inferred from a small vector kernel.

## Dependency-ordered delivery

| Rung | Deliverable | Required evidence | Ownership/state |
|---|---|---|---|
| 0 | Qualified native compiler and existing command installation | seed reconstruction, full semantic suite, safe install/uninstall | existing seed lineage; public command delivery owner retained |
| 1 | CUDA C++ frontend with explicit CPU reference execution | original-source differential, refusal, mutation and clean install/replay | L605 source d36abe7; unsigned32 elementwise profile only |
| 2 | Native sm121 target from source, not a templated C launcher | independently decoded actual instruction bytes, canonical encoder differential, original-C++ semantic cases, source/binary closure | L605 implementing now; offline lab capsule, not hardware-ready |
| 3 | Typed/checked GPU integration and native launch boundary | use qualified native IR/checker path, exact ABI, allocation/launch/error/repeated-call tests, device proof | existing L408 native IR/GPU and L419 runtime migration; immutable prerequisite required |
| 4 | First complete real GPU source-to-result path | vector operations through installed command on GB10, independent expected values, broken kernel/refusal, repeated launch/recovery and no CUDA dependencies | same owners; use one admitted correctness window, no live motor/driver disruption |
| 5 | Complete source-language capability corpus | signed/unsigned widths, f32/f64 and conversions, functions/overloads, control flow, arrays/structs/templates, shared memory, barriers/atomics, warp operations, 1D/2D/3D launch, separate compilation; each feature gets original-source positive/negative and mutant coverage | L605 frontend/backend, L408 language/checker owner; no declaration of full C++ support from current subset |
| 6 | Runtime and library compatibility/migration | actual caller corpus, memory/transfers, streams/events, modules, error semantics, multiprocess/recovery; numerical and library contracts, real GPU differentials | reuse CUDApp canonical owners and roadmap; do not add duplicate FFT/GEMM workers |
| 7 | Immutable package and real consumer cutover | clean source rebuild, no forbidden build/runtime dependency, exact installed entry point, golden full workloads, zero-CUDA closure, rollback and independent source review | existing developer release, canonical motor and desk owners |

Rungs 5/6 extend from real workloads while rung4 is available. A failing prerequisite
is fixed, not bypassed with legacy C or a test simulator. Offline code emission is
valuable development evidence but does not qualify execution or scheduler safety.

## Current next experiment

Extend the qualified frontend with a seeded-Omega native sm121 backend and explicit
`sm_121-lab` output. It emits an O M G P capsule containing actual 128-bit GPU
instructions and a fixed VECTOR_1D ABI declaration. Reuse the chip-proven vector
prologue and canonical instruction encodings; support the existing expression
operators using actual register instructions. The first launcher ABI has two
const inputs; other arities refuse on this target while retaining CPU support.

The capsule is lab-only data, not a cubin or host executable. Installed `run` must
refuse it until native runtime, checking and hardware gates pass. Source parsing
and code production stay native Omega. Test-only CUDApp encoder and C++ original
source remain independent oracles. A CPU instruction decoder/evaluator tests
finite integer semantics, not warp timing, scheduler behavior or actual hardware.

## Work rules

Keep the working service and existing drivers untouched. Do not consume L408's
dirty mutable compiler or restart another owner. Read source/receipts before
turning an old OPEN label into a missing-feature claim. Record exact source pins
and tests per rung, publish failures as well as passes, and keep the broad request
OPEN until real package/caller retirement is proven. One consolidated implementation
owner per component; independent review is separate read-only work.
