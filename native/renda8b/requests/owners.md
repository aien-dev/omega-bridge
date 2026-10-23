# Exact dependency requests, L720

This is a consumer request to existing owners, not authorization for another
compiler, device, gateway project, worker or restart. No owner tree was changed.
Shared request/ledger files are read-only here, so coordinator publication is
pending. Existing ledger L408/L605/L690 records were inspected2026-10-23.

## L408: existing FR4 and FR16/17

The immutable compiler SHA256191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9
refuses both tests/float-required.om and tests/socket-required.om with
exit3, line3 error3. Reproduce with `inputs/omc < SOURCE > candidate`, using the
private compiler in the L720 handoff directory. Do not execute failed output.

Need immutable qualified native floating scalar/array and GPU consumer interfaces
with exact IEEE rounding, NaN/subnormal and conversion contracts; and bounded
socket/listen/accept/readiness/close with error returns and signal handling for
the eventual chat-completions endpoint. Existing L690 owns JSON/gateway codecs.
The supplied seed's fixed loop fuel and register limit also constrain long-lived
services and large tokenization loops; explicit supported runtime policy needed.
Native portable FP8/BF16 bits and descriptor gates exist here meanwhile.

## L605: existing native device/launcher continuation

Inspected omega-bridge42fd206269744fb806f6ef09f950b0836a4e61fb and independent
device review L622. Candidate compiler e60af9f70edf2c2c50b3160902faff1eb7eba104463bb29a15217f71dce3c77f
qualifies openat/close/ioctl,23 cases. It does not supply GPU allocation, mappings,
module upload, launch, completion wait or readback. The existing sm121-lab target
explicitly prohibits launch. The old seed vector receipt uses a foreign launcher
and cannot qualify this request's product closure.

Need an immutable seeded-native consumer ABI and launcher artifact for checked
host/device buffers, mapping lifetime, cancellation, launch, completion and copy
back. Native/renda8b/kernels.om emits two fixed VECTOR_1D LAB capsules (f32 add and
multiply), using the existing descriptor/block/a/b/out/n ABI and original bounds
predicate. Inputs/outputs are separate, contiguous aligned f32 buffers; no alias
assumption may be introduced without qualification. Exact capsule and instruction
hashes will be in the artifact receipt. Preserve LAB launch refusal until a
qualified immutable runtime accepts a separately reviewed production artifact.

First required hardware gate under /tmp/aien-gb10.lock: boundary sizes0/1/31/32/
33/127/128/129/4096 with independent frozen float goldens, canaries, nontrivial
signs and magnitudes, and a compiled add-to-multiply mutant that must fail. Then
full model operators and immutable host-model goldens. No inference/performance
claim follows from disassembly or byte comparison.

## L690: existing codec and native transport owner

Imported only JSON source from30762489ee1fc4e0ceed02310bb6f19b0d128b00, byte-exact
SHA2565dbdd1fbc9996ff1aad5b2a2e05e58af2d3f343108eac5d241e79f956a844191.
Need qualified HTTP transport/SSE provider integration after FR16, not a duplicate
gateway. Actual Hermes chat_completions requires tool_calls, streamed deltas and
assistant/tool-result continuity, not only JSON-RPC or a ping exchange.

## Sole coordinator / Renda owner

Sandbox cannot write shared ledger, top-level handoff, profile config, shared Git
metadata or state directory; cannot establish network health/port availability.
This is separate from missing implementation. Future deployment must recheck
memory under admission lock with>=12GiB spare, port18128 availability, actual
tools and follow-up requests, and source/process-map closure. No GPU work or
model loading has been performed here. No server PID/start command exists.

renda1/renda2/work-control readback still names35B on18091. Existing renda-harness
separately hardcodes18091, discovers model ID and sends nonstreamed temperature0
requests. Preserve publication policy and sole owner. Replacing this caller's
first-party routing needs Omega work and coordinator-controlled worker reload;
changing only Hermes profiles is insufficient. Do not touch Work Control.
