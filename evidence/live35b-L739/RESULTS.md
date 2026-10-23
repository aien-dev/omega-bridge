# L739 native host evidence

Intermediate native components, NOT DEPLOYED. GPU/full-model/HTTP/timing NOT_RUN.

Verified compiler: SHA256191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9,
private immutable copy from omega-bridge/build/bootstrap/omc, source lineage
omega-mv29b12760f4c962606411d6bf25032aedef063301. Read-only original source.

- Initial selection and scheduling consumers fail compilation before implementation
  (01/05); their complete native tests pass after implementation.
- Selection uses independent pairwise numeric ranking on small fixtures, plus
  stored mixed signed-zero/infinity/subnormal/tie cases,257 equal values,
  deterministic rank patterns and the full248320 vocabulary at K1/20/100/V.
- Current35B grouping tests cover per-row distinctness, invalid IDs/row counts,
  complete128-row/1024-pick plan, all256 segments,stable row/rank order,
  shared expert and8 pad entries. Policy tests preserve strict thresholds;
  chunk tests cover127/128/129,255/256/257 boundaries and context cap49152.
- Original L689 policy source is byte-equal to its exact commit and compiled
  independently. Adapted policy output matches on requests92160bytes and replies
  18432bytes (33). Covers all capacities1..32,modes0..2 and twelve timing/pressure
  patterns per pair. No old Rust pager or historical model is run.
- Integrated protocol:4000 completed mixed operations match stored literal expected
  outputs (16/24). Full vocabulary buffered packet matches expected993312 bytes
  (28). Full prefill plan matches12452-byte closed-form expected response (42).
- Nine invalid fixture types each exit65 with0 output (29). Every cut0..328 of
  a complete mixed request set has the expected EOF/refusal status (30).
- Compiled mutants reverse token ties, ignore pressure and corrupt row mapping;
  unchanged tests reject each (13). A129-token chunk mutant originally survived
  because the existing fixture's mark clipped it; the missing unclipped case was
  added and now rejects it with exit40 (18). The original survival stays recorded.

Preserved implementation failures: fixed compiler register-budget refusals by
factoring expressions into helpers, without changing test sizes or semantics;
`break` is unsupported by this pinned seed, so heap ascent uses an early-return
helper. New I/O-buffer generator first failed compilation (25); that invalid
attempt left an empty request and failed golden comparison (26). It is not a
passing protocol result. Fixed the writer's expression register use and required
nonempty input; full original vocabulary then passes (27/28). These are not
compiler fixes or changes to another owner's code.

All product/test/harness source is .om. Existing OS commands orchestrate builds,
pipes, cuts, comparisons and logs; no new shell/Python/C/Rust program is added.
No foreign inference runtime, GPU driver, model payload or private prompt is
included. Artifact/source hashes and final committed-source replay are recorded
at freeze. Native .om host behavior is not GPU execution proof or a serving win.
