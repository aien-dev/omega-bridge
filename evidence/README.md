# L483 local qualification

Final command: `quiet-build tools/test.sh`, exit 0. Raw output: `20-final-suite.log`.

| Gate | Cases | Failures |
|---|---:|---:|
| native seed versus generated C (GCC UBSan) versus actual Python | 113 | 0 |
| shared frontend and target capability refusals | 49 | 0 |
| real C and Python application callers | 2 | 0 |
| six damaged-output controls plus nonempty repeatability | 7 | 0 |
| byte-prefix truncations and hostile/capacity source inputs | 225 | 0 |
| Total | 396 | 0 |

The 113 programs include all 20 inherited accepted program-mode fixtures and 93 added numeric/order/array/loop/I/O probes. The three other inherited files are two refusals and a function-mode fixture; they are not silently counted as executable programs. The original forward function-mode fixture is retained for provenance, not claimed as an executable native program gate. Library forward calls share the names pass; callable library behavior is exercised separately.

`differential-results.json` binds every executed program to its source/input digests, generated C/Python digests, and native/C/Python exit status and raw stdout/stderr encoded as hex. Known answers additionally check echo, reverse bytecopy, Fibonacci, observable operand order, and trap precedence. C builds use `gcc -std=gnu11 -O1 -fsanitize=undefined -fno-sanitize-recover=all`. Bounds mutants additionally use AddressSanitizer. `control-results.json` records intentionally broken artifact hashes and observed failures. These are damaged test outputs, not failures of the final compiler.

Source replay: `quiet-build tools/bootstrap.sh`, exit 0, `19-fetch-bootstrap.log`. It fetches commit `29b12760f4c962606411d6bf25032aedef063301`; no original checkout or precompiled seed is needed. Three Omega compiler stages are byte-identical. `02-bootstrap.log` also records replay using a read-only local source archive. This is a fixpoint, not independent diverse double compilation.

RED history is preserved: the recovered compiler failed 8/20 inherited tests (`01-recovered-red.log`); the expanded recovered run failed 70/113 (`15-expanded-recovered-red.log`); the recovered refusal implementation failed 40/48 (`08-refusals-red.log`). Intermediate new tests found 12 shift defects, integer-not refusal, missing attachment exports, result/input overlap, and missing copy export. Each has its actual failing and subsequent passing log. Intermediate red logs are development traces; the source-bound final qualification is the final manifest plus final gate output. Existing behavior that already passed a new probe is not represented as an invented failure.

Measurements: `quiet-build python3 tests/measure.py`, exit 0; `21-final-measurements.log` and `measurements.json`. These are three conversion samples and five process/call samples per row on a shared host. C output was slower than native in these small observed process workloads; Python was substantially slower. No speedup, isolated benchmark, universal conversion or broad language-adapter claim follows. The separate Python-module and ctypes caller loops have different marshalling/allocation costs, recorded in the JSON; they are not a fair language speed comparison.

Limits are part of the result: 128 active generated calls and 32 KiB local arrays per function, conservative compile capacities, text/float/GPU and other features refused, only experimental library ABI v0. t_stack compares eventual trap status, not equal exhaustion thresholds. No independent checker2 receipt, independent compiler audit, DDC, cross-architecture verification, installer or public-release qualification is claimed. Review remains required. See docs/CAPABILITIES.md and docs/ABI.md.

Log paths have been normalized to `<repo>` to avoid embedding the build account's directory. Other tool results are retained. `manifest.json` records the exact source/tool/binary hashes, tool versions and commands. No binaries are committed.
