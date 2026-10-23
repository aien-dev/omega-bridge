# LocalRouter profile foundation argv migrator (L749)

This is an intermediate, native Omega artifact. It prepares a config byte stream by replacing exactly one uniquely occurring JSON `server` array with a caller-supplied command argv array. It does not start or verify the command, attach a backend, change the model id, or qualify feature/lifecycle parity.

## Input/output contract

`profile-migrator` reads one frame from stdin:

1. ASCII decimal source byte length, then LF (no CR, no sign).
2. Exactly that many bytes of the already-rendered upstream config JSON.
3. ASCII decimal replacement byte length, then LF.
4. Exactly that many bytes of a compact JSON array of one or more strings, followed by EOF.

Bounds are 4096 source bytes, 256 argv-descriptor bytes, 8192 frame bytes, and 4096 output bytes. The array is the complete replacement for the sole `server` property; it is not shell text and no `eval` occurs. Caller owns executable path and argv semantics. `tools[0].id` and every other byte/field remain from the source; the example argv repeats `qwen3.8-27b` without changing the config id.

The core is byte-oriented and stages output in a fixed pool. It refuses invalid framing, malformed/unbalanced quoted/delimited source, a missing/duplicate server-array target, invalid compact string-array descriptors, or capacity overflow before publishing output. It preserves all bytes outside the selected array. It is a bounded structural scanner, not a complete RFC 8259 validator: inputs must already be valid rendered JSON; semantic checks on unrelated fields remain owned by the upstream renderer/parser. Failure statuses are nonzero; parser/refusal paths write no stdout.

## Reproduction

The seed compiler used for native builds is `build/native/omc` from the immutable Omega final-qualification checkout, SHA-256 `191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9`. Build the test and CLI by concatenating the core with respectively `tests/profile_migrator_test.om` or `src/profile_migrator.om`, compiling through that seed, then marking the resulting AArch64 executable mode 0700. No compiler rebuild is part of this task.

Test harness stdin is one compact source fixture. Its `.om` assertions cover exact successful output (including an unrelated `voice` field and model id), unknown-field byte preservation, duplicate target refusal, malformed delimiter refusal, invalid descriptor refusal, output-buffer overflow refusal, and unchanged core output bytes/length on refusal. The compiled caller also processes the exact LocalRouter config template after the upstream install renderer's placeholder substitution, then substitutes only `options.server`; `jq` parsed both input and output and the diff showed only that array changed.

## Open acceptance

This artifact is not the complete L749 foundation swap. `/opt/omega/bin/omega-chat-server` in the recorded output is a planned caller-selected argv only. No such native service availability, startup/shutdown, HTTP/OpenAI compatibility, model load, qualification, voice/realtime/MCP parity, or speed is claimed. The full upstream profile includes native service/user lifecycle details that remain unqualified. Preserve these as open gates; do not deploy this planned config.
