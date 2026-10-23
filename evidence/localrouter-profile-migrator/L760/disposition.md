# L760 correction disposition (parent implementation)

Original review: `original-review.md`, frozen source `81bc0120957de1d8d4337541e8e8d70e76ef1018`. Both findings were confirmed. The first attempted delegated correction did not compile and produced no published fix; no GREEN result is attributed to it.

## P1: wrong server field

Replaced global literal-key selection with structural traversal of root `tools`, each tool's explicit `kind`, and the unique chat tool's `options.server`. Root and speech-tool server arrays remain unchanged. Missing/ambiguous chat targets and relevant duplicate keys refuse before compose. Escaped property names at traversed scopes and escaped kind values conservatively refuse to avoid ambiguity; arbitrary escaped-config compatibility remains unsupported and is disclosed.

Parent authored `tests/profile_migrator_l760.om`. It compiled against unchanged source and exited 1 because the wrong-scope case was accepted. The corrected implementation compiled and returned 0. A subsequent escaped-kind ambiguity regression compiled and returned 1 before its guard; the same final suite returned 0 after correction. These are runtime failures of successfully compiled tests, not compile errors counted as caught faults.

## P2: invalid replacement JSON

Replacement validation now accepts only the JSON escape set and valid four-digit Unicode escapes, requiring proper surrogate pairs and valid raw UTF-8. It rejects NUL and an empty executable string because those cannot be meaningful process argv. Public CLI replay of the exact invalid-escape frame returns 22 with empty stdout; wrong-scope frame returns 25 with empty stdout. The native suite verifies invalid escapes, bad Unicode hex, unpaired surrogates, successful Unicode/scalar-pair descriptors, exact valid replacement, and unchanged full output pool/length on refusal.

## Preserved behavior and qualification boundary

The final native CLI replays the original pinned upstream frame with status 0 and output byte-identical to the original committed planned config. Thus all non-target fixture bytes remain unchanged. Reordered chat/speech tools with unrelated server arrays pass native exact-output assertions. The inherited direct-core suite still passes after deliberately updating its successful/overflow fixtures to an explicit chat entry; duplicate-property refusal is now the dedicated structural ambiguity status 7 instead of global-target-count status 5. Its transactional and overflow assertions are retained.

Compiler: immutable SHA-256 `191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9`. Parent replay source and command outputs are under Spark `~/handoffs/localrouter-L749/parent-replay/`. Final committed source hashes and executed gate output are provided separately. The original independent report remains unchanged; this disposition is author/parent correction evidence, not a new independent review.

No service, model, driver, GPU launch or deployment was changed. The foundation replacement, actual server availability, full feature parity, lifecycle and measured speed remain OPEN. Do not deploy the planned config.
