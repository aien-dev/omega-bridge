# Native binary32 multiplication reference, L720

This is an intermediate reference primitive for the Omega-native 8B kernel work, not an 8B forward pass, GPU implementation, deployment or compiler extension. Source and executable tests are handwritten Omega `.om`, built by qualified seed compiler SHA256191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9. No first-party foreign-language floating runtime is linked or called.

`mul32` takes binary32 bit patterns in ulong slots and returns a binary32 bit pattern. It implements round-to-nearest ties-to-even, gradual underflow, signed zeros and infinities. All NaNs become positive canonical quiet NaN. Input slots are masked to32bits. Integer significand products fit48bits. This finite corpus is not exhaustive proof.

Evidence: meaningful missing-behavior RED compiled successfully then failed13 of15 assertions, exit1. Implementation passed15 focused assertions. Separate native corpus runner executed9505 paired cases with0 mismatches, exit0. Corpus includes17edge values crossed with each other,8192 deterministic random pairs, and1024 edge/random pairs, seed720. The external expected-value oracle used Python standard-library IEEE unpack/pack: binary32 inputs multiply exactly in binary64 before rounding once tobinary32; overflow maps to signed infinity and NaNs are canonicalized. Python is an external qualification oracle, not part of building or running the reference. Corpus raw SHA256ca1559d3458459d18bfc9360883402c1d1db8798ccb00bb8cf2ccefc1b2a1b27.

A first compile refused a deeply nested final packing expression at the seed compiler's16-slot limit. Splitting that expression into assignments fixed the source; original failure is retained, not counted as behavioral RED.

Reproduce on Linux AArch64, with the pinned compiler at `$COMPILER`:

```sh
cat native/ref32/mul32.om native/ref32/report.om native/ref32/tests.om > /path/to/private/focused.om
"$COMPILER" < /path/to/private/focused.om > /path/to/private/focused
chmod +x /path/to/private/focused
/path/to/private/focused
cat native/ref32/mul32.om native/ref32/report.om native/ref32/corpus.om > /path/to/private/corpus.om
"$COMPILER" < /path/to/private/corpus.om > /path/to/private/corpus
chmod +x /path/to/private/corpus
/path/to/private/corpus < native/ref32/corpus.bin
```

The paths are caller-owned private outputs. Use `quiet-build` for shared Spark compilation. Report actual compiler and child exit codes separately. `report.om` is reused verbatim from the existing L720 native test utility. Build outputs are not committed.

## Addition milestone

`add32.om` adds native binary32 addition using integer guard/round/sticky arithmetic, signed zeros, canonical NaNs, infinities, cancellation and gradual underflow. Meaningful missing-behavior baseline compiled and failed13of16checks with exit1. Implementation passed16focused checks and a separate9505case corpus with0mismatches. Its external oracle unpacks binary32 to binary64, adds and packs once tobinary32, canonicalizing NaNs and overflow; it is qualification-only. Corpus seed721; same17edge cross product,8192random pairs and1024edge/random pairs. Corpus SHA2561f18fb897d13f56747e8a9c51aacd25b121a489ab066a79f374b36ffbac87b3e. Raw addition logs are retained beside multiplication logs. Concatenate add32.om,report.om,add-tests.om for focused checks, or add32.om,report.om,add-corpus.om and feed add-corpus.bin for corpus checks.

An over-nested rounding condition initially exceeded the pinned compiler's16-slot limit. Nested equivalent branches removed the temporary-register excess; the original refusal remains in add-register-limit.log. It is not behavioral RED and no gate was weakened.

NOT_READY for product integration: independent source review, broader model arithmetic, full repository qualification, immutable clean-source replay and GPU numerical/caller gates remain open. These primitives remove dependence on native compiler f32 support for reference addition and multiplication only; division, square root and nonlinear functions are not implemented here. Do not claim the compiler, device mapping/launch, HTTP server or Renda model replacement is finished.
