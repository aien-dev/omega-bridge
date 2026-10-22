# CUDA C++ frontend qualification

**Latest GPU lab candidate:** source `0e0b486c300c78ed335b26e86b1fed29d858adad`, with [offline GPU receipts](gpu-lab/receipt.json) and the [whole-replacement programme](../../docs/PROGRAM.md). It emits real sm121 code but does not launch it; scheduling, hardware, native runtime and full CUDA C++ remain unqualified. [Independent review and parent verification](gpu-lab/review/disposition.md) passed for the offline source/command scope; no hardware or full replacement qualification is implied.

**Earlier CPU-only candidate:** source [`d36abe7`](https://github.com/aien-dev/omega-bridge/commit/d36abe7e94bafce9a20d1be00f9405b23e3f05e2), with its evidence in [`final/receipt.json`](final/receipt.json).

## Earlier CPU-only qualification

This is a bounded CUDA C++17 unsigned-integer elementwise frontend, handwritten
in seeded Omega and integrated with the existing `om` installer and aliases.
It builds actual static AArch64 **CPU-simulator** executables. It is not full
CUDA C++ support, GPU compilation, a CUDA runtime, or production retirement.

## Executed CPU-only gates

| Gate | Result | Raw record |
|---|---|---|
| Native parser/lowering, original-source C++ differentials, limits and compiled mutants | 549/549 checks PASS; three semantic mutants caught | [native results](final/native-results.json) |
| Installed aliases, check/build/run, explicit target refusal, stdin, output safety, integrity and uninstall | 33/33 PASS | [command results](final/commands-results.json) |
| Independent-review regressions | 37 valid C++17 variants, 185/185 assertions PASS | [review results](final/review_regressions-results.json) |
| Entire inherited project suite plus these new gates | Exit 0 | [suite output](final/final-full-suite.log), [component logs](final/suite/) |
| Clean committed-source export, seed bootstrap, full suite, isolated install and actual command execution | Exit 0; compiler/frontend hashes retained | [replay script](final/final-replay.sh), [hashes](final/final-binaries.sha256) |
| Actual installed final `om run` from an unrelated directory | Exit 0, uint32 output `[5,1,8]` | [input, output and command](final/demo.json) |

The independent [review](final/review.md) covered source `9ac729a` and found two
valid-source over-refusals. Both were reproduced before changes and fixed in
`d36abe7`: CR-only line comments, and C++20-only keywords used as identifiers in
C++17. [Adjudication and limits](final/review-adjudication.md) separate review from
the author's red-green fix verification; no second independent review is claimed.

The top-level `receipt.json`, `cold-suite/` and development logs retain the earlier
source freeze and original failures; **they are not the current final receipt**.
Only explicitly produced current log files were collected under each cold-suite
label. Imported historical evidence from the base repository is not new testing.
Python, GCC and Node are test/orchestration tools; the production frontend and
compilation path are native Omega with the documented POSIX command glue.

## Usable candidate on the Spark

`/home/drakestapleton/handoffs/cuda-cpp-L605/final-candidate/bin/om`

```sh
OM="$HOME/handoffs/cuda-cpp-L605/final-candidate/bin/om"
"$OM" check --from cuda-cpp tests/cuda-cpp/vector.cu
"$OM" build --from cuda-cpp --target cpu-sim tests/cuda-cpp/vector.cu -o vector-sim
```

Source syntax, binary stdin framing, refusal behavior and installation commands:
[docs/CUDA-CPP.md](../../docs/CUDA-CPP.md).

## Open acceptance

L605 remains OPEN for the user's full request. Seed-native GPU/IR lowering remains
L408's existing compiler scope; a concrete frontend-consumer handoff was appended
and read back in `handoffs/omega-feature-requests.md`, with no duplicate worker or
compiler restart. No live motor, driver or GPU state was changed. General C++, CUDA
host APIs, GPU runtime attachment and physical GB10 execution remain unimplemented
or NOT_RUN. No speed or full-support claim is made.
