# LocalRouter profile foundation argv migrator (L749)

**Intermediate artifact, not a deployed foundation replacement.** Replaces only `options.server` in the single explicitly `"kind":"chat"` entry of the root `tools` array. Tool ordering does not select the target. Unrelated server arrays, voice settings, other models, defaults, model IDs and unknown fields are retained byte-for-byte. The command is caller-supplied; this tool does not start or verify it.

## Input and bounds

One stdin frame: decimal source byte length + LF, exact already-rendered JSON bytes, decimal descriptor byte length + LF, exact compact JSON argv string-array bytes, then EOF. No signs or CR in length headers. Source <=4096 bytes, descriptor <=256 bytes, whole frame <8192 bytes, output <=4096 bytes. There is no eval, filesystem, network, service or GPU operation.

The source must already be valid rendered JSON. A bounded structural scanner traverses the root object, tools entries and selected options object. It is **not a complete JSON validator**. Nested containers are checked with a 128-entry delimiter stack. Relevant duplicate keys, ambiguous/multiple chat entries, missing paths and non-array server targets refuse. For safety this version refuses escaped property names at traversed root/tool/selected-options scopes and escaped `kind` values, rather than silently overlooking an equivalent target. This is a disclosed compatibility limitation, not full arbitrary-config support. Untraversed values are copied without normalization.

Replacement argv must be a compact, nonempty array of JSON strings. The first string cannot be empty. Escapes must be valid JSON escapes; Unicode hex escapes must represent nonzero Unicode scalars or valid surrogate pairs. Raw non-ASCII strings must be valid UTF-8 (no overlong encodings, surrogate scalars or values above U+10FFFF). NUL is refused because process argv cannot represent it. Whitespace inside strings is preserved; formatting whitespace outside strings is not accepted in the compact descriptor. These checks do not establish executable existence, flags, model compatibility or successful process startup.

All core refusal paths preserve the output pool and its published length. CLI parser/refusal paths emit no stdout. A failed/partial stdout write cannot be rolled back and returns nonzero; this is not a filesystem transaction or crash-durability claim.

## Native builds and verification

Use the immutable final-qualification seed `build/native/omc`, SHA-256 `191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9`. Concatenate core plus the selected test/CLI source into compiler stdin; require successful compile and nonempty static AArch64 executable before running. No compiler rebuild is needed.

- `src/profile_migrator_core.om` + `tests/profile_migrator_test.om`: inherited direct-core assertions. Stdin is `{"tools":[{"kind":"chat","id":"qwen3.8-27b","options":{"server":["old"]},"voice":true}]}`. This updates the older no-kind fixture to the explicit chat-selection contract; refusal/buffer/overflow checks remain.
- Core + `tests/profile_migrator_l760.om`: no stdin; L760 regressions, reordered tools and unrelated server preservation, Unicode escapes/pairs, malformed escapes, ambiguity and complete output-pool preservation.
- Core + `src/profile_migrator.om`: public framed CLI. Replay the frozen upstream fixture and require output byte equality with the original planned config; refuse the original review counterexamples with empty stdout.

Original independent review and probes are preserved under `evidence/localrouter-profile-migrator/L760/`. Correction evidence/disposition is distinct from the original review. All newly authored executable implementation and test assertions are handwritten Omega; existing Linux host tools orchestrate compilation and inspect files.

## Open acceptance

`/opt/omega/bin/omega-chat-server` remains planned text, not a verified existing service. Do not deploy this planned config. Actual native server, model compatibility, supervised lifecycle, OpenAI/MCP/voice/realtime/image/video behavior, same-workload parity and speed, final integration/release and full foundation replacement remain open.
