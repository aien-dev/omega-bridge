# MAX CPU evidence destination regression

Status: EXERCISED host filesystem behavior, Linux x86_64, Python 3.12.14.
Base: `6ec6dab7668a0ca60835f8ac26996544c90b16f0` (merged #47).
Date: 2026-10-31 UTC. Related coordination: #5.

## Exact source identity

SHA256:

```text
793996f12bde5ffa2b3e3ecd552dd23074da2b0188383d5c33edbb12377cd98c  max-cpu/run.sh
800ef073631b70e10926a30ab1b916b0c04458395e1771a079f11ce806ebda68  max-cpu/test_run_evidence.py
9ea29b5a6f9f6281c65a7412535d7388aa153e1e27d623814b02eaf202b34df3  max-cpu/README.md
dd2f5f2d832f2d2088c6172896b92eab94f4f6d48b9b387fa08289ca2596df49  baseline run.sh
```

MEASURED: `python3 max-cpu/test_run_evidence.py` passed all 11 test methods.
The identical tests against the original source failed 17 subcases. A private
mutant disabling only the containment predicate failed eight subcases. Raw
outputs and exit statuses are adjacent; no earlier evidence was rewritten.
The two red logs are losslessly compressed with `gzip -n` to preserve unittest's
trailing spaces without introducing whitespace errors into the source diff.
`gzip -dc baseline-red.log.gz` recovers the raw log with SHA256
`041943afab73d5176ca1caf516453b68a68aa5d74ee4adebfcb8d1d8500c87b1`;
`gzip -dc no-overlap-mutant-red.log.gz` recovers SHA256
`2883ca95a3b893556222653bfc0f8af921dc5a8eb7acfbe3dbea58bf1ee1aa4a`.
Both decoded streams were compared byte-for-byte with the original logs.

The test executes an unchanged copy of the selected shell script in a private
temporary fixture. `git`, `sha256sum`, and `tools/native` are explicit test
doubles. The native double exits 73 so the tests can observe the first output
redirection even when a build fails. This does not exercise or change compiler
admission, a MAX graph, an Omega unit, or a device.

## Reproduction

From the repository root with the source identities above:

```sh
python3 max-cpu/test_run_evidence.py
sh -n max-cpu/run.sh
python3 -m py_compile max-cpu/test_run_evidence.py
git diff --check
```

The recorded red/green run used byte-identical copies under a fresh generic
temporary directory so failure traces contain no private workspace paths:

```sh
T=$(mktemp -d /tmp/bridge-max-cpu-public.XXXXXXXX)
mkdir "$T/max-cpu"
cp max-cpu/run.sh max-cpu/test_run_evidence.py "$T/max-cpu/"
git show 6ec6dab7668a0ca60835f8ac26996544c90b16f0:max-cpu/run.sh >"$T/base-run.sh"
python3 - "$T" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = (p / 'max-cpu/run.sh').read_text()
old = '    case "$1/" in "${2%/}/"*) return 0 ;; *) return 1 ;; esac'
assert s.count(old) == 1
(p / 'no-overlap-mutant.sh').write_text(s.replace(old, '    return 1'))
PY
(cd "$T"; RUN_SCRIPT="$T/base-run.sh" python3 max-cpu/test_run_evidence.py)
# Expected exit 1: baseline-red.log
(cd "$T"; RUN_SCRIPT="$T/no-overlap-mutant.sh" python3 max-cpu/test_run_evidence.py)
# Expected exit 1: no-overlap-mutant-red.log
(cd "$T"; python3 max-cpu/test_run_evidence.py)
# Expected exit 0: patched-green.log
```

Source review was performed independently of the writer, including containment,
outward symlinks, dangling symlinks and missing-parent handling. It was a static
review with inspection of execution receipts, not a second independent runtime
execution. The exact source-only patch also passed a clean-base archive replay.

## Limits

- `sh tools/bootstrap.sh`: exit 1, `bootstrap requires Linux AArch64`.
- `env -u OMEGA_SEED sh tools/test.sh`: exit 1, missing pinned bootstrap compiler.
  The native aggregate suite is NOT_RUN, not PASS.
- Full MAX CPU reproduction and device execution: NOT_RUN. No MAX installation
  or required AArch64 environment was used. This is not a numeric, performance,
  GPU, qualification or deployment receipt.
- Paths must remain stable during the run, and BUILD remains caller-owned,
  disposable build storage. This is not a concurrent-filesystem security sandbox.
- The regression has an explicit documented host-only command. It is not added
  to the native aggregate suite or recursively invoked from its own fixture.
- Compiler pins, gates, MAX glue, Omega kernel and original MAX-CPU records are
  unchanged. Runtime shape-binding concerns are outside this patch.
