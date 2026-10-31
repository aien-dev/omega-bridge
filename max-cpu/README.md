# max-cpu: Omega kernel as a MAX CPU custom op

- `omatmul.om` — the kernel (seeded Omega, OM-2), built by `tools/native`.
- `kernels/__init__.mojo` — MAX custom-op glue `omega_matmul` (`OwnedDLHandle` + dlsym).
- `omega_max.py` — graphs, numeric check, negative controls, measurements.
- `run.sh` — the single reproduce target; `mogg-cache-repro.sh` — the MAX cache observation.

Status EXERCISED(host CPU). Evidence, pins, results and gaps: [../evidence/MAX-CPU/README.md](../evidence/MAX-CPU/README.md).

Each `run.sh` invocation writes fresh evidence to a new directory under
`$TMPDIR` (or `/tmp`) and prints `evidence=<path>`. To select a destination,
set `EV` to a path that does not yet exist, with an existing writable parent.
`EV` must not contain or be inside `BUILD`; the default evidence parent
(`TMPDIR` or `/tmp`) must be outside `BUILD`. Checks resolve symlink and `..`
aliases with GNU `realpath` before any build reset. An existing destination is
also refused. Paths must be stable during the run; this is not a sandbox
against concurrent filesystem renames. The committed
`evidence/MAX-CPU/raw` directory remains the immutable original run of record.

Host-only filesystem regression, without Omega, MAX or devices:
`python3 max-cpu/test_run_evidence.py`.
