# L739 current35B native optimization integration

NOT A MASTER PLAN. Scoped execution under L739 and existing owner contracts.

Target: qwen3.6-35b-a3b-fp8 revision95a723d0, 40 layers, hidden2048,
256 routed experts/top8 plus shared expert, vocabulary248320, GB10.
Read checkpoint config directly. Existing bin19173f9e is a Rust serving program
linked with legacy C GPU code, irrespective of its engine label. It is an oracle.
A complete .om candidate requires seeded model loading, forward compute, device
submission and HTTP/SSE transport; none is supplied by this bridge checkout.
L408/L605/L690 own these foundations. Exact requests are in parent-actions.md.
No owner source, existing test, runtime lock or service is modified here.

First native consumer slice in native/live35b:

1. Exact top-K selection on raw binary32 bits for the complete current vocabulary.
   Integer-only comparison preserves finite/infinite numeric order, signed zero
   ties and lower-token-id ties. Bounded worst-root heap costs O(V log K), retains
   original selected bits and emits -infinity for discarded logits. This carries
   the measured partial-selection behavior, not Rust's implementation. No claim
   that the heap is faster until measured. NaNs refuse before publication: the
   old comparator is nontransitive and its library-sort output is not a portable
   numeric contract. Native NaN compatibility remains a recorded integration gap.
2. Current35B route grouping: at most128 prefill rows (8 decode rows), each8 distinct expert IDs in0..255;
   stable counting placement by expert while preserving row/rank identity. This is host-side
   schedule construction, not GPU expert execution. All validation precedes work.
3. Reuse L689's immutable scheduling policy semantics, with fixed limits and
   strict integer thresholds, independent of expert identities and weight bytes.
   Reusing policy does not import its historical OWN30B Rust pager.
4. Native prefill/checkpoint planner clips128-token chunks at state/tool/prefix
   boundaries and context limits. It never changes forward arithmetic.
5. One framed native command consumer integrates these operations. Fixed pools,
   partial read/write handling, invalid/truncated input refusals and no inherited
   row state between requests. Publication starts only after input validation and
   computation. Broken output pipe can still expose a partial response; caller
   must treat that as failed transaction. No socket or runtime fallback exists.

All new implementation and test/harness source is handwritten .om. Existing
shell/OS commands concatenate modules, invoke the hash-verified seed and capture
receipts. No transpilation or generated C in this build path. The private seed
copy is verified against191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9.

Verification: semantic RED first; stored independent bit-pattern vectors;
small exhaustive rank-count oracle; full248320 boundary cases; row identity
and duplicates; exact adaptive threshold and pressure cases; checkpoint127/128/
129 and context boundaries; compiled tie/row/pressure mutants must fail the
unchanged native test entry points. Separate .om protocol fixture writer and
verifier test real executable pipes, consecutive frames and truncations.
Full-model/goldens/concurrency/tool HTTP/SSE and all GPU gates remain NOT_RUN
until the missing owned foundations and parent admission exist. Component
success cannot promote inventory rows to enabled on live.
