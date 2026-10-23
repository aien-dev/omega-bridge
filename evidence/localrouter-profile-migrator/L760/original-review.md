# L760 independent review — exact source 81bc0120957de1d8d4337541e8e8d70e76ef1018

**Verdict:** not approved as a safe config migration primitive yet. Two reproducible contract defects remain. No production source was edited; no service/deployment was touched. The artifact remains an intermediate byte-splice transformer, not a LocalRouter replacement or full foundation acceptance.

## Frozen target and provenance

- Spark worktree: `~/workspace/omega-localrouter-migrator-L749`
- Branch/commit: `feat/localrouter-profile-migrator-L749` @ `81bc0120957de1d8d4337541e8e8d70e76ef1018`; clean at review.
- Seed native compiler: `~/workspace/omega-bridge-final-qualification/build/native/omc`, SHA-256 `191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9`.
- Frozen reviewed source hashes:
  - `src/profile_migrator_core.om`: `ed6a2dbfbb011e01a3fe4797ab293679bf15f135a0774d901f28eb18dc3ba091`
  - `src/profile_migrator.om`: `6f6d366cfd1483c0d9592d01f062e5f73d86baa45cda32efcded698b948cd406`
  - `tests/profile_migrator_test.om`: `82da96fdbc8adbed05552ca9b1b5012546a52b198aeba212731709afdd4758ee`
  - `docs/LOCALROUTER_PROFILE_MIGRATOR.md`: `3dfc4fc2d2b7b9e95cb90115a36dbc7aa73fda72f5596c7fde6ed5cac61eb7f6`
  - rendered upstream fixture `evidence/localrouter-profile-migrator/upstream-rendered-config.json`: `3d0357046912f3e73448afb5c7951c758aba5537d626b95bbe6299ff68440970`
  - replacement descriptor `evidence/localrouter-profile-migrator/replacement-argv.json`: `1bf7aa905ec0303e6b8253f13f271c34f240edbdcb55b31f67796a7f3d6bd1bc`
- Context fixture is pinned to upstream LocalRouter `7caf022157c7aba57d19452bed9002967da6a67a`; it has a chat tool at `tools[0].options.server` and additional speech/transcription/image/video tools. This review does not infer that the planned `/opt/omega/bin/omega-chat-server` exists.

## Severity-ranked findings

### P1 — Replaces any `server` array, not the intended chat `tools[0].options.server`

`src/profile_migrator_core.om:189-216` scans every JSON string in the document and treats any literal key named `server` followed by an array as the target. It does not check object depth or the required path. `docs/LOCALROUTER_PROFILE_MIGRATOR.md` describes a sole `server` property, but the foundation migration target is specifically the chat tool's `options.server`; arbitrary config fields may also use this name.

**Exact valid-JSON reproduction:** source `{"unrelated":{"server":["OLD"]},"tools":[{"options":{}}]}`; replacement ` ["NEW"] ` (without the spaces). The native direct-core `.om` assertion exits 0 after proving the output is `{"unrelated":{"server":["NEW"]},"tools":[{"options":{}}]}` even though there is no `tools[0].options.server`. The compiled CLI also exits 0 and its raw stdout is that mutated JSON. Files: `l760-scope-probe.om`, `scope-probe` (AArch64 ELF), `wrong-scope.frame`, `wrong-scope.out`.

**Impact:** caller can receive successful output while its actual chat command remains unchanged and a different tool/config field is rewritten. If another legitimate `server` array exists, the global uniqueness rule instead rejects the entire config. Path-scoped selection and uniqueness are needed for the stated migration.

### P2 — Replacement validator accepts invalid JSON string escapes and emits invalid config

`src/profile_migrator_core.om:104-162` treats any byte after backslash as an escaped byte; JSON only permits escapes for `"`, `\\`, `/`, `b`, `f`, `n`, `r`, `t`, or a valid `uXXXX`. The function therefore does not establish the documented caller-array validity precondition or the claimed invalid-descriptor refusal.

**Exact reproduction:** valid source `{"tools":[{"options":{"server":["OLD"]}}]}`; replacement descriptor `["x\q"]` (one literal backslash before `q`). The compiled `.om` assertion exits 0, and the compiled CLI exits 0 with 42 bytes of stdout: `{"tools":[{"options":{"server":["x\q"]}}]}`. `jq -e .` rejects that stdout (exit 5). Files: `l760-escape-probe.om`, `escape-probe` (AArch64 ELF), `invalid-escape.frame`, `invalid-escape.out`.

**Impact:** the migrator can report success yet emit bytes that cannot be parsed as JSON. Callers using an invalid/buggy descriptor can fail at config load after accepting migration output.

## Native execution receipts

Both adversarial probes were built by concatenating the pinned core and each `.om` probe into stdin of the pinned native compiler; each result was checked nonempty, `file` identified a statically linked AArch64 ELF, then it was executed. Direct-core assertion exit statuses: scope `0`, escape `0` (success means the unexpected acceptance/mutation was asserted). The real CLI was compiled from `core + src/profile_migrator.om`; invalid-escape CLI status `0`, `jq` status `5`; wrong-scope CLI status `0`. Raw framed inputs and stdout are kept alongside this report.

Positive control: the compiled CLI also processed the exact 3,767-byte pinned upstream rendered fixture with the 113-byte replacement argv. It exited `0`; the 3,488-byte stdout compared byte-for-byte equal to committed `native-planned-config.json` (`cmp` 0). A `jq` projection confirmed only the chat tool's server argv changed, retaining its id and all other tool entries. Raw receipt files: `upstream-fixture.frame` SHA-256 `0f2de6a7637bcb2fdef67f06a2fcc92434ec4dcbb58501a0b786693ef19918af`; `upstream-fixture.out` SHA-256 `eabf6a42ac3b637717f8c6f5ff09d3139a352c9ecc60f66b6b2836a99958e77`.

Rebuild/replay on Spark:

```sh
cd ~/workspace/omega-localrouter-migrator-L749
D=~/handoffs/localrouter-L760
cat src/profile_migrator_core.om "$D/l760-scope-probe.om" | ~/workspace/omega-bridge-final-qualification/build/native/omc > "$D/scope-probe"
test -s "$D/scope-probe" && chmod 700 "$D/scope-probe" && "$D/scope-probe"; printf 'scope_rc=%s\n' "$?"
cat src/profile_migrator_core.om "$D/l760-escape-probe.om" | ~/workspace/omega-bridge-final-qualification/build/native/omc > "$D/escape-probe"
test -s "$D/escape-probe" && chmod 700 "$D/escape-probe" && "$D/escape-probe"; printf 'escape_rc=%s\n' "$?"
```

## Scope checked / remaining

Reviewed the native core, framed CLI, direct-core tests, contract doc, fixture, replacement argv and author evidence. The core suite from the frozen commit compiles; an initial attempt to feed the full upstream JSON fixture to the tiny direct-core test binary exited 2 because that harness expects its small test input, not the fixture (not counted as a code failure or pass). Parent's separate fresh core replay is recorded in L749; this review did not substitute for it.

The source explicitly requires already-valid rendered JSON and says it is only a bounded structural scanner, not an RFC 8259 validator. I did not raise unrelated malformed-source cases absent a demonstrated contract effect. The frame loop reads until EOF/capacity, checks declared frame lengths and stages the transformed core output before stdout; no additional confirmed framing/size/error-wrap finding was established in these probes. Short/failed stdout writes cannot be made atomic by a stdout stream and are not represented as a parser-refusal guarantee. No service, GPU, model, shared checkout or production source was changed.

**Disposition:** return these defects to the L749 parent for correction and fresh independent re-verification. This report is not a merge approval, deployment recommendation, or full LocalRouter acceptance.
