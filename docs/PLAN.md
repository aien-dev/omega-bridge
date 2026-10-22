# L483 execution plan

1. Verify recovered source and pinned seed. Add isolated build and differential harness. Capture failures before changes.
2. Retain recovered token/name machinery in src/toc.om. Replace unchecked expression emission with typed nodes and ordered target emitters. Gate C against native seed output, exit and traps.
3. Add Python emitter in the same Omega compiler using the same checked nodes and capability limits. Run the same cases under actual Python.
4. Add C and Python callers, explicit ABI/ownership limits, mutation controls, repeatability, tool/source hashes and timing receipts. Push working milestones.

Commands: tools/build.sh, tools/test.sh, tools/bootstrap.sh. Build products stay in build/. Fixture origins are recorded in docs/PROVENANCE.md. Tests and shell build glue are infrastructure; compiler decisions and both target writers live in Omega.

Tests first: all inherited program fixtures, each width and overflow, conversions, div/rem, ordered calls and traps, length/ownership refusals, malformed and unsupported syntax, empty/truncated input, output mutants and caller failures. Newly added cases are run against the preceding implementation before their fix and kept in evidence/.

# L551 follow-on

1. [x] Read seeded text grammar, required studies and existing bridge contracts.
2. [x] Freeze TEXT-CONVERSION.md and preserve the parent baseline unchanged.
3. [x] Record failing tests, implement bounded Omega text pool/tokenizer and both writers.
4. [x] Run text parity, valid compiled mutants, view callers and full converter suite.
5. [ ] Full native/math/command/path/provenance gate; committed-only replay.
6. [ ] Push source/evidence and hand off awaiting independent core review.
