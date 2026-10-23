# Numeric codec contract

`numeric.om` operates on IEEE binary32 bit patterns stored in ulong cells. Inputs
must fit the stated 8/32 bit widths. This is portable host-native codec work,
not GPU inference or a replacement arithmetic engine.

E4M3FN: bias7, three mantissa bits, subnormal unit 2^-9, maximum finite448.
Codes127/255 are NaNs. Decode preserves the sign and canonicalizes the payload.
Encode uses round-to-nearest, ties-to-even, finite saturation, and signed zero.
Infinity saturates to +/-448; NaNs map to the sign's NaN code.
BF16 conversion rounds binary32 ties to even and preserves infinity/zero;
NaNs become a signed canonical quiet NaN, never infinity.

Tests use hand-calculated, frozen IEEE bit patterns for boundary values, midpoint
ties and their immediate neighbors; roundtrips additionally cover all254 finite
FP8 encodings. These are not an independent full-model numerical golden.
The initial test mistakenly used3/512 where its expected result described1.5/512.
The input was corrected to994050048 before the positive implementation run;
the original RED output and source snapshot are retained. The test executable's
exit now reports boolean failure rather than wrapping the failure count at256.
