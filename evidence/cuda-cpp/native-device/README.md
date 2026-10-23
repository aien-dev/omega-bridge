# Native device boundary

Source `0dee6994ed10b51dc30b4ab1ff7665202ecaec56` adds direct AArch64 Linux openat/close/ioctl code generation in a separately built native Omega compiler. The imported seed compiler and public installed command are unchanged.

Cold exact-source full inherited suite, source-born compiler fixpoint, 116 byte-exact inherited compiler fixtures, 23 device/error/refusal cases and 3 successfully compiled behavioral mutants passed. `qualification/syscalls.trace` records a real /dev/null open with O_RDWR|O_CLOEXEC and close, with no subprocess. Tests also execute FIONREAD on a real pipe, including checked output offsets and preserved guard bytes.

`devopen` accepts a byte array, offset and count including exactly one terminal NUL. `devshut` accepts an int descriptor. `devctl` accepts an int descriptor, literal uint request, writable byte array, offset and exact request size; currently only FIONREAD and encoded NVRM read/write F requests are admitted. These are an explicit native OS boundary, not a sandbox or proof of arbitrary driver behavior. No raw scalar-to-pointer conversion is introduced.

No device mapping, NVRM allocation/channel or GPU launch is qualified by this receipt. No GPU device was opened. The broader implementation continues under L605. Independent review L622 is pending.

History is append-only: device-red originally had malformed program/loop syntax; device-red-corrected is the meaningful missing-word baseline. device-green2 preserved the mistaken trap expectation 131; the existing `tests/fixtures/t_bounds.want` fixes the contract at 103. device-ioctl-red isolates the missing ioctl word. None of those old failures is a current PASS.
