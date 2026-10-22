# Native Developer Commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** add check/build/run to the single native om implementation and its omg alias.
**Architecture:** retain pinned native compiler and validated source snapshot; use the existing ELF verifier as owned host glue, atomic output for build, inherited program I/O for run.
**Tech Stack:** existing POSIX shell, seed-built Omega compiler, readelf metadata qualification; Node tests only.
**Spec:** docs/superpowers/specs/2026-10-22-native-developer-commands-design.md

## Global Constraints

- om primary; omg only alias, one implementation/state.
- Source pins unchanged; no first-party C/Rust or interpreter fallback.
- check/build never execute source; run explicitly executes native code, no sandbox claim.
- Existing status codes, prefix transaction/uninstall/path safety retained.
- Isolated fixture HOME/prefix only; no services/GPU/global account changes.

## Review Focus

- Compilation accidentally consumes program stdin: assert exact echo stream after source snapshot.
- Invalid/nonempty wrong ELF is accepted: substitute a different native payload compiler and require refusal.
- Successful compilation mistakenly runs during check/build: observable output marker must remain silent.
- Failed output publication destroys unrelated data: preserve destination hash/mode and symlink target.
- New owned helper is omitted from integrity/uninstall: modify it, require refusal, restore and verify removal.

### Task 1: Native checking and atomic build

Files: tools/om, tools/install.sh, tools/uninstall.sh, tools/HELP.txt;
new tests/native/developer-commands.mjs.
Consumes installed omc and tools/verify-elf.sh; produces check/build contracts from the spec.
- [ ] Write installed regressions for silent checking, static native artifact, malformed-source refusal, bad-ELF refusal, output preservation/permissions and quoting.
- [ ] Run on795009f; expect unknown-command64 where success is required, preserving actual RED.
- [ ] Implement check/build and ship/hash/uninstall the verifier with executable mode700; keep converter/math code paths unchanged.
- [ ] Run the same tests; require correct native artifact and no execution output.
- [ ] Commit the source milestone with evidence.

### Task 2: Native execution and final integration

Files: tools/om, tests/native/developer-commands.mjs, tools/test-native.sh,
README.md, docs/NATIVE-COMMANDS.md and evidence/native-developer-commands/.
Consumes the same snapshot/native artifact; produces run with caller stdin and native status.
- [ ] Write run tests for stdout, stdin echo, nonzero exit, malformed source, extra-argument refusal, both aliases and temp cleanup; observe RED before implementation.
- [ ] Implement native child execution with inherited streams, status propagation and ordinary cleanup; no foreign engine.
- [ ] Run focused tests, full tools/test-native.sh and fresh committed-source installation/replay including execution trace.
- [ ] Publish exact source/binary/test identities, independently review the whole feature, fix important findings by RED/GREEN before acceptance.

Pre-flight: tasks share the snapshot/native ELF pipeline; both must validate using
exact installed compiler bytes and verifier. Run must not redirect inherited stdin
to the source file. No other compiler/math-source interface changes.

Ruling: the user's standing decide/act/report instruction replaces approval prompts;
implementation is inline, with one fresh whole-feature review after passing tests.
