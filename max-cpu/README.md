# max-cpu: Omega kernel as a MAX CPU custom op

- `omatmul.om` — the kernel (seeded Omega, OM-2), built by `tools/native`.
- `kernels/__init__.mojo` — MAX custom-op glue `omega_matmul` (`OwnedDLHandle` + dlsym).
- `omega_max.py` — graphs, numeric check, negative controls, measurements.
- `run.sh` — the single reproduce target; `mogg-cache-repro.sh` — the MAX cache observation.

Status EXERCISED(host CPU). Evidence, pins, results and gaps: [../evidence/MAX-CPU/README.md](../evidence/MAX-CPU/README.md).
