<!-- github-native-navigation -->
[Source](https://github.com/aien-dev/omega-bridge) · [Replay receipt](docs/teaching-replay.txt) · [Issues](https://github.com/aien-dev/omega-bridge/issues)
<!-- /github-native-navigation -->

# Omega Bridge

Pre-alpha. An Omega-first interoperability project: conversion targets and language bindings, so existing applications can adopt Omega without rewriting their visible interface.

At the pinned `main` revision, the recovered Omega-to-C compiler is unqualified source. A separate pending implementation at `feat/c-python-bridge@77376b1941a020dba441a14fce8eaadea692a5b7` now has a bounded Omega-to-C/Python conversion path and experimental caller ABI. **[Follow one real conversion, refusal and C/Python caller exercise](docs/BRIDGE_TUTORIAL.md)**. The parent repeated that branch's source-only bootstrap, compared 26 Fibonacci output lines across native/C/Python, observed unsupported-text refusal exit24 and ran both caller tests. This does not claim the implementation is merged, universally supported or faster.

Product goal: replace invisible internals, attach to familiar tools, and stay out of the user’s way. Installation and replacement must be opt-in, inspectable and reversible.

See docs/DESIGN.md for scope and safety.

## How I recovered the converter

The [recovery record](docs/RECOVERY.json) identifies the preserved Omega source and digest; [the design](docs/DESIGN.md) calls for checked semantics and target adapters rather than arbitrary text substitution. Current [converter source](src/toc.om) reads Omega from stdin, scans function signatures in `namescan`, emits a C header and functions in `emit_all`, and reports errors through `fail`. It carries array length beside address and emits bounds and conversion traps. Its fixed buffers and limited token grammar are an actual subset, not general Omega support.

### Read-only recovered-source check

At full source commit `614f4ba56487ad420f43980b12e48b66768d6d21`, Python 3 alone can verify preservation and locate an error-reporting function. That source inspection does not execute a refusal:

```sh
python3 - <<'PYCODE'
import hashlib,json
from pathlib import Path
r=json.loads(Path('docs/RECOVERY.json').read_text())
s=Path('src/toc.om').read_bytes()
assert hashlib.sha256(s).hexdigest()==r['source_sha256']
assert b'fn fail code ulong' in s and b'fn emit_all to void' in s
print('recovered source digest: PASS; conversion NOT_RUN')
PYCODE
```

Expected exit 0. A changed source byte is a safe negative case for the digest comparison, not execution of the converter. No emitted C, caller or Python backend is qualified on this older `main` source. The [separately pinned branch tutorial](docs/BRIDGE_TUTORIAL.md) supplies a source bootstrap and actual conversion/refusal exercise without pretending that integration has happened. Opt-in adoption and rollback are design requirements, not an implemented system installer in this older checkout. [Original recovery-check receipt](docs/teaching-replay.txt).


### Parent fresh-checkout replay

A separate coordination replay is retained in [the parent receipt](docs/parent-replay-2026-10-22.txt). Its scope and observed exit are explicit; source review and final desk qualification remain separate. A recorded absence or expected failing baseline is not a passing implementation.
