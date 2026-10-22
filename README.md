<!-- github-native-navigation -->
[Source](https://github.com/aien-dev/omega-bridge) · [Replay receipt](docs/teaching-replay.txt) · [Issues](https://github.com/aien-dev/omega-bridge/issues)
<!-- /github-native-navigation -->

# Omega Bridge

Pre-alpha. An Omega-first interoperability project: conversion targets and language bindings, so existing applications can adopt Omega without rewriting their visible interface.

The recovered Omega-to-C compiler is unqualified source, not a completed converter. C and Python are the first qualification targets. Other languages are planned extensions, not supported claims. No performance improvement is claimed without an end-to-end receipt.

Product goal: replace invisible internals, attach to familiar tools, and stay out of the user’s way. Installation and replacement must be opt-in, inspectable and reversible.

See docs/DESIGN.md for scope and safety.

## How I recovered the converter

The [recovery record](docs/RECOVERY.json) identifies the preserved Omega source and digest; [the design](docs/DESIGN.md) calls for checked semantics and target adapters rather than arbitrary text substitution. Current [converter source](src/toc.om) reads Omega from stdin, scans function signatures in `namescan`, emits a C header and functions in `emit_all`, and reports errors through `fail`. It carries array length beside address and emits bounds and conversion traps. Its fixed buffers and limited token grammar are an actual subset, not general Omega support.

### Read-only recovered-source check

At commit `614f4ba`, Python 3 alone can verify preservation and one explicit refusal path:

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

Expected exit 0. A changed source byte is a safe negative case: digest comparison fails. Building this Omega source requires the original qualified seed toolchain, which is absent here; no emitted C, C caller, Python backend, binding or performance result is qualified on `main`. Opt-in adoption and rollback are requirements in DESIGN.md, not implemented installer behavior. [Replay receipt](docs/teaching-replay.txt).
