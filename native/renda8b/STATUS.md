# L720: Qwen3-8B native consumer

Work in progress. No native 8B endpoint or Renda cutover is qualified.
Implemented codecs, descriptor admission, geometry/greedy helpers and two
handwritten offline sm121 kernels. Committed-source replay passes289 numeric,
21 descriptor,188 geometry and1022 encoding checks; all651 real tensor
descriptors and12 external file hashes pass; six compiled mutants are rejected.
See ../../evidence/renda8b-L720/RESULTS.md for limits and preserved failures.

1. Verify the immutable seeded compiler, checkpoint and existing owner interfaces.
2. Implement portable consumer components and handwritten kernel work in Omega.
3. Require GPU numerical, full inference, tool and caller gates before deployment.

Owned checkout: omega-bridge, feat/renda-8b-native-L720, base
77376b1941a020dba441a14fce8eaadea692a5b7. Compiler SHA256:
191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9.
Verified and copied read-only to the L720 private inputs directory.

The repository's existing C/Python converter is not the build path for this work.
All new executable implementation, test and harness sources are .om. Shell and
existing OS tools perform inspection, concatenation, compilation and evidence
capture. No new shell/Python/Rust/C implementation is introduced.

Inspected L408, L605, L690 ledger records and handoffs. The native compiler lacks
floating-point types and socket/mapping words. L605's reviewed device extension
provides openat/close/ioctl, not a qualified native allocation/mapping/launch path.
Its sm121 capsule explicitly forbids launch. L690 provides bounded JSON and
WebSocket codecs, not a qualified transport. Those owners' trees remain untouched.

Sandbox currently refuses shared-ledger locking, GitHub DNS and loopback access.
Normal Git metadata is read-only. Local commits use private Git metadata with
the same worktree; no second checkout or worker was created. Push failed DNS.
Shared 35B health and candidate port availability cannot be established here.
Profile readback: renda1, renda2 and work-control all still use the 35B model on
18091. renda-harness separately hardcodes that endpoint and discovers model ID.
No profile/process/port changes have been made. No workers have been spawned.

Evidence and pending ledger notes are saved in the permitted directory
/home/drakestapleton/handoffs/renda8b-L720. The brief's top-level handoff path and
shared ledger are outside writable roots; do not interpret local notes as
successful shared-ledger publication. L720 remains open.
