# Independent review: CUDA C++ frontend and `om` CPU-simulator integration

Reviewed commit: `9ac729a73bd036633ffccc0c23783fc104866132` (base `d2010ab927b608931800c20d73a4c2b25f00a9fa`). Read-only review. I inspected the source frontend, command dispatcher, build/install/uninstall integration, documented contract, and focused test harness. No repository files were changed. I did not run the shared-output test suites.

## Findings

### Minor — CR-only line endings are documented as accepted but line comments consume the rest of the file

- **Location:** `src/cuda-cpp.om:60-70` (`linecom` advances until byte 10/LF only); `src/cuda-cpp.om:88` treats CR as whitespace outside comments. Contract: `docs/CUDA-CPP.md:50` says CR is accepted.
- **Reproduction:** Convert every LF in `tests/cuda-cpp/vector.cu` to CR and feed it to `build/native/cuda-cpp`. The frontend exits 65 (`CUDA_CPP_REFUSED`) with no lowered output. The same bytes, prefixed with a minimal CUDA builtin host shim, pass `g++ -std=c++17 -fsyntax-only`; GNU C++ treats CR as a line terminator here. The fixture begins with a `//` comment, so `linecom` skips all later declarations when it fails to stop on CR.
- **Impact:** Valid source using CR-only line endings and line comments is refused despite the stated whitespace contract. LF and CRLF are separately covered; CR-only is not.

### Minor — C++20 keywords are rejected as identifiers despite the advertised C++17 source profile

- **Location:** `src/cuda-cpp.om:26` includes `concept`, `requires`, `consteval`, `constinit`, and coroutine keywords in `Words`; `src/cuda-cpp.om:235-243` rejects every name matching that list.
- **Reproduction:** Replace `vector_add` with `concept` in the fixture. `build/native/cuda-cpp` exits 65 with no output, while the source plus the CUDA builtin host shim passes `g++ -std=c++17 -fsyntax-only`. `requires`, `consteval`, and `co_await` behave the same way.
- **Impact:** Legal C++17 identifiers that are reserved only in later standards cannot be used for the kernel name (and similarly for other declarations). This conflicts with the C++17 profile and renameable-identifier contract; it is an over-rejection, not unsafe acceptance.

## Integration/security review

I found no concrete correctness or security defect in the inspected `tools/om` CUDA dispatch path or the fixed install/integrity/uninstall lists. The dispatch requires explicit `--target cpu-sim` for build/run, snapshots the source before compiling, passes caller stdin only to the executable, and the output staging logic retains the existing same-file/symlink safeguards. The frontend emits no source names into generated Omega identifiers. These are inspection findings only; I did not rerun the full shared-output gates.

## Artifacts and limits

- Report: `/home/drakestapleton/handoffs/cuda-cpp-L605/review.md`
- Private reproducer sources are under `/home/drakestapleton/handoffs/cuda-cpp-L605/review/`.
- No repository source, build artifacts, or evidence files were modified by this review.
