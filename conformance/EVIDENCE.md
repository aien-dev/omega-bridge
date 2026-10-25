# Conformance evidence

Fixtures are deterministic (`gen_fixtures.py`, splitmix64) and are hashed in
`artifacts.sha256`. The independent judge is `oracle.py`; `verify.py` also
mutates an accepted output and the wrong head map and requires both to fail.

Latest host run (2026-10-23, CPU):

```
sh conformance/run.sh
{"checks": 12, "fixture": "gqa-causal-v1", "fail": 0, "max_abs_error": 2.6951e-07}
{"checks": 11, "fixture": "matmul-v1", "fail": 0, "max_abs_error": 0}
DEVICE RUNS: NOT_RUN (pass --device inside an authorized spark-window)
CONFORMANCE HARNESS PASS
```

The 4x5x3 matmul fixture is exact in fp32, so it does not distinguish fp32 from
fp64 accumulation. GPU runs are NOT_RUN; the chip is reserved. Every GPU result
must carry a `SPARK_WINDOW` id and is not independently attested beyond that.
