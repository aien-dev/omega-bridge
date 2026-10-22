# Provenance

AGPL-3.0 is retained. Recovered src/toc.om originated in omega seed/toc/toc.om, uncommitted source on base 29b12760f4c962606411d6bf25032aedef063301. Original digest is in RECOVERY.json. Lexer, type/name tables and signature scan are retained and extended. Typed expression nodes and target emitters replace unchecked emission.

Inherited fixtures: omega seed/rung4/tests/*.om and *.want at that same commit. Pinned seed source: seed/omc/omc.om at that commit. No seed binary is committed here.

The shell CLI uses the pinned Omega-written seed compiler as the shared whole-unit checker, before the Omega-written target compiler parses typed expression nodes. Native differential tests share that checker; they independently exercise machine-code, C and Python execution, not independent frontend implementations. This is not a checker2 receipt or diverse double compilation claim.

The inherited seed/omc/tests/text.om program is preserved in tests/fixtures/text_program.om at the same source pin. L551 moves it unchanged from the old unsupported path into positive native/C/Python
differential execution. The original text_target refusal source is also preserved
verbatim in tests/text-promoted.json. Only these now-supported negative
classifications change; malformed/readonly refusals retain their seeded codes.
