# L622 — independent native device compiler boundary review

**Target:** `omega-cuda-cpp-frontend` HEAD `0dee6994ed10b51dc30b4ab1ff7665202ecaec56` (base `71a70de1a92e7640919c263cf5dac36862296721`). Reviewed `src/device/omc.om` and build/gate/qualification harnesses. No implementation or ledger changes.

## Findings

No source correctness defect reproduced in this review. In particular, the syscall paths preserved caller values across nested expression use; byte-array validation rejected empty, out-of-range, unterminated, embedded-NUL, and wrapping ranges before issuing `openat`/`ioctl`. This is a bounded compiler/API contract, **not** a security sandbox: compiled programs can request their supported host syscalls and compiler validation does not confer kernel/device safety.

## Independent evidence

- Verified immutable HEAD and the qualified source-born parent compiler SHA-256 `191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9`; rebuilt candidate to a nonempty static AArch64 ELF. Candidate SHA-256 `e60af9f70edf2c2c50b3160902faff1eb7eba104463bb29a15217f71dce3c77f`.
- Ran `tests/device/gate.py` against that candidate: **23/23** cases passed, including real `/dev/null` open/close, invalid-fd close/ioctl, ENOENT, local/global/view arrays, nested call preservation, repeated opens, and malformed/overflowing ranges.
- Ran `tests/device/qualify.py`: **116** inherited compile-equivalent fixtures, **23** device cases, and **3/3** behavioral mutants caught; status PASS.
- Independent syscall trace confirmed one process exec and exact `openat(AT_FDCWD, "/dev/null", O_RDWR|O_CLOEXEC) = 3`, then `close(3) = 0`. No GPU or device node was accessed.

## Artifacts

- Private reprobes, logs, outputs, and candidate: `/home/drakestapleton/handoffs/cuda-cpp-L605/device-review/probes/`
- Raw trace: `/home/drakestapleton/handoffs/cuda-cpp-L605/device-review/probes/syscalls.trace`

Review stops at this immutable native I/O boundary. Mapping/launcher and real-device integration remain out of scope and are not claimed complete.
