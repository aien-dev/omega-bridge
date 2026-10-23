# Native CUDA runtime attachment implementation plan

> Execute inline with superpowers:executing-plans and test-driven-development.

Goal: finish the entirely Omega source-to-device path specified in docs/PROGRAM.md, starting at its missing native device-I/O boundary. This plan does not reduce the parent acceptance criteria.

Architecture: preserve imported seed/ and L408's compiler worktree. Extend the qualified compiler in src/device/omc.om, built by the existing hash-qualified source-born compiler. Production code remains Omega, syscall lowering emits direct AArch64 Linux instructions. No libc, C launcher, raw pointer decay or silent CPU execution.

Spec: docs/PROGRAM.md and existing seed language buffer/alias contracts.

## Task 1: Device descriptors
- [ ] tests/device/gate.py compiles and executes new source programs; baseline must refuse the new words (error3), not fail on malformed fixtures. Keep initial malformed fixture evidence separately.
- [ ] `devopen A off n -> long`: byte array range checked; n>0; exactly n bytes ending in NUL with no earlier NUL; openat(AT_FDCWD,path,O_RDWR|O_CLOEXEC,0). Return raw Linux result (descriptor or negative errno). No create/truncate flags.
- [ ] `devshut fd:int -> long`: close via syscall57, preserving locals and returning raw Linux result.
- [ ] Tests: actual /dev/null open/close; EBADF; absent path ENOENT; zero length, unterminated, embedded NUL, range overflow; local/global/view buffers; repeated calls and expression nesting; full compiler regression and self-fixpoint.
- [ ] Build through pinned parent 191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9. Preserve original seed files unchanged.

## Task 2: Native device request and mapping boundary
Add only length-checked operations required by the pinned NVRM ABI: ioctl argument blocks, explicit nested-buffer references and bounded opaque mappings; no generic arbitrary-memory dereference. Establish external syscall differentials before issuing device requests. Preserve error and cleanup semantics.

## Task 3: Source-to-GPU execution
Port the pinned NVRM allocation/channel/submission/recovery sequence into native Omega using Task2. Consume only validated capsules with exact supported ABI. Admit correctness through existing chip workflow, never stop the working service or change drivers. Compare actual device output against original-source reference; test repeated launch, tails, errors and broken-code controls. Only then promote the real GPU target in the installed command.

## Task 4: Coverage and delivery
Extend actual caller-driven language/API coverage, attach native IR/checker under the existing owner contract, run clean-package consumer gates, independent whole-source review and desk publication. The parent remains open until docs/PROGRAM.md acceptance is met.

## Review focus
Malformed buffer ranges, stack-save addressing, nested expressions and restored registers, stale handles and cleanup on every failure, unqualified capsule execution. No unrun gate may be reported passing.

## Rulings
Use a source-bound consumer compiler extension rather than editing the other owner's dirty compiler; reconcile upstream after qualification. Keep current installed package unchanged until the extension and runtime integration pass their gates.
