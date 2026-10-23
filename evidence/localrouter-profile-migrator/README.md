# L749 migrator author evidence

- LocalRouter source: `jayleaton/localrouter` exact upstream commit `7caf022157c7aba57d19452bed9002967da6a67a`; foundation selection input is `deploy/jarvis/config.json.in` (the install renderer resolves its placeholders before JSON parsing).
- Omega source branch starts from `release/developer-download-L584@d2010ab927b608931800c20d73a4c2b25f00a9fa`.
- Compiler binary reused unchanged: `/home/drakestapleton/workspace/omega-bridge-final-qualification/build/native/omc`, SHA-256 `191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9`.
- TDD: compiled stub + direct-core harness RED (status 1, expected migration refusal); handwritten implementation compiled and same intended successful case returned 0. Final direct-core Omega suite returned 0 across exact replacement/preservation plus duplicate target, malformed delimiters, invalid argv descriptor, output-overflow and failure-buffer preservation checks. A compiled one-byte-key mutant returned 15 (test failed as intended).
- Public framed stdin/stdout replay on the rendered upstream config returned 0. `jq` parsed source and output and confirmed the chat model id/default, voice speech model and five-tool list are unchanged; byte diff shows only `options.server` replaced. Replaying the frozen source/descriptor produced byte-identical output (`cmp` 0).
- Duplicate-target CLI run returned 25 and emitted zero stdout bytes. Malformed-frame CLI run returned 17 and emitted zero stdout bytes.
- The replacement executable `/opt/omega/bin/omega-chat-server` is caller-provided planned text, not a service verified to exist. This evidence is config transformation only, NOT foundation/runtime/lifecycle/parity qualification.
