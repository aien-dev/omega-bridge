# G1 sample units

- `calc.om`: hand-written, in the translation-v1 section 5 form, with no semantic `note` line.
- `calc.lowered.om`: generated, never edited. It was produced in aien-dev/omega-mv at commit
  `2ef4834754bef95036c9df792fad3d17ebecccbf` (branch `universal/624-g1-integration`). First,
  `make -f mk/translation.mk test-translation-g1 SA_SEED_REPO=~/workspace/omega-bridge` was run (rc 0,
  `TRANSLATION-G1 PASS`), which built `build/L589/c-import` (sha256 `d3cf7793…cb01`) and
  `build/L831/lower` (sha256 `e8ac7f14…6e98`). Then, in that tree:
  `printf '#include <stdint.h>\nuint64_t calc(uint64_t a, uint64_t b) { return (a+b)*(a-b); }\n' | build/L589/c-import | tools/adapters/lower > calc.lowered.om`
  Both stages exited 0. The output sha256 is
  `5a86d68bd0b30a89656552f6075bddbda5b12e39cd96e6ac97d03891b2b0a187`, and the semantic identity is
  `8dc67eafc9e818d649f0cbcc59d226acbb7b2fd7fd4318f2e6b9a4d67a69fd1b`. The extra `put v 5 0` and
  `add` before `ret` come from the section 4 `+0` root normalization.

To run the callers on a unit: `OMEGA_NATIVE_OMC=<seed omc> OMEGA_G1_UNIT=tests/native/g1/calc.lowered.om sh tests/native/g1/run.sh`
