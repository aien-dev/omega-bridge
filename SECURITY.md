# Security policy

## Reporting a vulnerability

Report privately. Do not open a public issue, pull request or discussion about it.

1. GitHub: open this repository's Security tab and choose "Report a vulnerability". This
   creates a private advisory that only the maintainers can see. If that option is not shown,
   private vulnerability reporting has not been enabled for this repository yet; use email.
2. Email: drake@aienos.com with the subject `[omega-bridge] security report`.

Include the commit or release you tested, the component (path), steps to reproduce, and what an
attacker gains. If the report involves a secret, say where it was exposed and do not send the
secret itself. Encrypted mail is not required; do not post proof-of-concept payloads publicly.

## Response targets

This project has one maintainer; the targets below are best effort and stated honestly.

- Acknowledgement: within 3 working days.
- Triage and severity: within 7 days of acknowledgement.
- Fix or mitigation for confirmed issues: aim for 30 days for high and critical, 90 days
  otherwise, with a status update at least every 14 days until closed.
- Disclosure: coordinated. An advisory is published with credit (unless you ask otherwise)
  once the fix is on the default branch. Default embargo 90 days, negotiable.

## Scope

In scope:

- `src/toc.om` emitting C or Python whose behaviour differs from native Omega in a way that
  drops a bounds check, an overflow trap or a loop guard (for example generated C that reads or
  writes outside an array).
- An Omega input that makes the converter publish partial output, write outside stdout, or
  accept a feature `docs/CAPABILITIES.md` says is refused.
- `tools/bridge` validating one version of the input and generating from another, or running
  when `build/compiler.sha256` does not match.
- `src/native.om` generating a C binding that lets a caller pass a wrong length, alias inputs
  and results, or violate the native call ABI in `docs/NATIVE-ABI.md`.
- `src/gpu_adapter.om` returning `ACCEPT` for a request the wire format in
  `docs/GPU-ADAPTER.md` requires it to refuse.
- `tools/bootstrap.sh` accepting a seed whose sha256 is not the pinned one.

Out of scope:

- The Python test code under `tests/` and `conformance/` (infrastructure, not shipped).
- The upstream Omega compiler at the pinned commit; report it to `aien-dev/omega-mv`.
- Modular MAX, CUDApp and the NVIDIA driver.
- Resource exhaustion thresholds that differ between native and generated code; the
  capability document states they are not equivalence claims.

## Supported versions

Only the default branch `main`; there is no release. Reports against older commits are welcome
but fixes land on the default branch only.

## Status

The README states that independent review remains required before release and that no universal
conversion or speedup is claimed. GPU hardware load and execution are NOT_RUN. There is no
certification and no bug bounty. See AUDIT_SCOPE.md for what to review and how to build and test
it.
