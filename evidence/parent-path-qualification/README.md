# Parent qualification of the filesystem corrections

Exact reviewed/tested source:
`e4e7ed4534aece6bd3ab944094b7eed2a5d05532`.
Parent used a new Git worktree with no preexisting build output; the author's
worktree and evidence were not modified. Both native math/converter source and
the complete immutable provenance lock remain unchanged by the path fix.

Executed independently by the parent on AArch64 Linux:

```sh
timeout 180 quiet-build tools/test-native.sh
timeout 120 quiet-build node tests/native/replay-path-safety.mjs
```

Both returned zero. Full component logs are in `../native-commands/` and the new
path controls/replay logs in `../native-path-safety/`. `full.log`/`full.exit` and
`replay.log`/`replay.exit` preserve the parent's own top-level results.

The parent parsed the actual path-control report: 57 rows executed, all57 passed,
zero failed. The source-only replay exported the committed tree (not dirty source
or cached binaries), rebuilt compiler/converter/math, compared rebuilt and installed
hashes with the independently built parent artifacts, exercised both aliases from
an unrelated directory, reran all57 path controls and uninstalled the isolated
prefix. All three native binary identities matched.

The pre-fix counterexample was real, not a compiler-error proxy: unrelated
synthetic files were overwritten and relocated synthetic payload files/aliases
were deleted. The final tests assert preservation as well as refusal status.
Some rename-published outputs preserved bytes in the baseline but are now
conservatively refused if linked; those are not falsely counted as baseline
clobbers. Direct uninstall and alias entry points remain distinguished.

Review status: the independent corrective-source review of exact `e4e7ed4`
confirmed both original findings resolved for the documented single-user scope,
with no new important destructive-path defect found. Its source-level findings
are saved in `corrective-review.md`; the parent runs above provide runtime proof.
The implementation and test qualification are accepted. Desk publication is a
separate step: no main merge, release or global account installation is claimed.
`om` is primary;
`omg` is its alias, not another command implementation. No real account enrollment,
runtime attachment, production service replacement or performance claim is made.
The disclosed shell/Linux host boundary remains; native computation is seed-born
Omega, not a first-party C/Rust fallback.
