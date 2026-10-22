# Developer distribution replay

L584 reuses the reviewed native developer implementation at
`0fc7d8662cb799e7c206b17c18ea4c3ec2b8fea9`. No compiler, converter, math,
installer, dispatcher, native validation helper or seeded source was changed.
This increment adds the entry guide and distribution evidence only.

The exact upstream source archive SHA256 used in both replays was:
`fc8e1080198ee54c7554d0f818924c94db29a7f52a21ba591996e3534d7e3234`.
The final download adds this guide/evidence; its separately supplied SHA256SUMS
identifies that final archive. Source closure is checked against the source pin.

Hosts: DGX Spark GB10 (`Linux aarch64`) and Raspberry Pi 5 Model B Rev 1.0
(`Linux aarch64`, host alias hub). These are real separate machines, not a
container/emulated second host. No GPU, driver, service or account configuration
was changed. The Pi replay stayed in an isolated `/var/tmp` tree and did not
write its user's home. Both installations were removed after the replay;
project files and receipts remain in their isolated test directories.

Run `sh evidence/developer-distribution/replay.sh ABSOLUTE_EMPTY_WORK_DIRECTORY`
with the source distribution saved as `package.tar.gz` in that directory.
The replay creates isolated HOME/TMPDIR, installs from the source-only package,
creates a separate project, checks/builds/runs it, checks the alias, math,
program exit status and invalid-source refusal, verifies output, records native
hashes and uninstalls. This shell is host test orchestration, not the compiler.

Both replays returned status0 with the final PASS sentinel. Logs are
`spark.log` and `pi5.log`. Matching native identities:

| Artifact | SHA256 |
|---|---|
| Seed-built compiler | `191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9` |
| Native converter | `db0847423bec99ba66fdd99e75e5e3b795e2a5386e81ca3ed7b4c9c530a5bd4e` |
| Native math | `aa7906f534ffb63575f5b59be15e3ed93a02fe56d103aa35298beed5a35d7ac6` |
| Hello output, build/run/alias on each host | `658d1a970a8283335948ee80ab670aef4155cc3525db0ebbff4a49c59a4d80ff` |

This is a fresh developer-entry replay, not an independent new whole-compiler
review, a performance benchmark, all-platform qualification or public release.
The inherited whole-feature independent review and broad source replay remain
under `evidence/native-developer-commands/`. macOS/Windows/x86-64/GPU support,
automatic application hooks, hostile concurrent filesystem mutation and
crash-durable installation remain outside the qualified distribution scope.
