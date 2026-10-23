# L739 current35B optimization consumer

Tracker: [omega-bridge#2](https://github.com/aien-dev/omega-bridge/issues/2).
Status: native host components implemented and tested. **NOT DEPLOYED**.
No model forward pass, GPU submission, tokenizer, HTTP/SSE server or speedup is
claimed. Existing owners retain those interfaces. Source/build/runtime closure
for this executable is handwritten .om -> verified seeded compiler -> static
AArch64 ELF using Linux read/write/exit. No converter or generated C is involved.

Target geometry is the actual qwen3.6-35b-a3b-fp8 checkpoint revision95a723d0:
vocabulary248320,40 layers,256 routed experts/top8 plus shared expert256,
hidden2048. Source is isolated under native/live35b. Existing bridge components
and all compiler/device/model-owner source remain untouched.

## Integrated behavior

- `select.om`: binary32-bit top-K mask using a worst-root heap, bounded by the
  complete current vocabulary. Numeric comparison includes infinities, subnormal
  encodings and signed-zero ties; lower token ID wins ties. Kept bits are exact;
  discarded values become negative infinity. K=0 masks everything. NaNs refuse
  before output. This differs from the legacy Rust NaN full-sort fallback and
  remains an explicit integration gap. This is a native carry of partial
  selection behavior, with O(V log K) worst-case work, not a timing claim.
- `schedule.om`: L689 policy semantics in process, plus current35B host grouping
  and chunk planning. Original policy source is preserved byte-exact in vendor/.
  Integer thresholds and capacity bounds are unchanged. Policy cannot inspect
  expert weights or router scores. It does not add a pager or preparation thread.
- Grouping follows `omega-mv@6de999da86efc6edd9c2554a87ee31f7fa9215ac`,
  `src/omega_gpu_q36_graph.c:pf_group`: counting placement sorts by expert, then
  original token and pick; emits segments, xmap/ymap, shared maps and8 zero pad
  entries. Row counts1..128,8 distinct picks in0..255 per row. Decoder operation2
  keeps its8-row cap. Shared expert256 is separate. No raw device address is
  fabricated: native device owner must bind each logical expert segment to its
  checked weight/scale handles and construct the existing32-byte Seg32 records.
- Chunks stop at128 tokens, the next tool/prefix/snapshot mark, the final prompt
  token or context cap49152. Already-complete prompt returns0; stale marks and
  invalid context return a refusal. This does not claim cache save/restore.
- `wire.om`, `consumer.om`, `main.om`: one framed consumer, bounded static pools,
  partial reads/writes, block-buffered vocabulary input/output and per-frame
  validation. Invalid input terminates; there is no silent fallback or state
  reuse after failure. One billion frames is a declared lifetime bound, not
  a tested lifetime claim. Caller serializes access; no concurrency API exists.

## Protocol v1

All fields are little-endian. Request/response headers contain four u64 words:
`version=1, operation, count, argument`. No text or JSON wrapper.

| Operation | Request count / argument | Input | Reply count / argument | Output |
|---|---|---|---|---|
|0 select|V / K|V binary32 u32 bits|V / K|V masked binary32 u32 bits|
|1 flow|10 /0|10 u64 WFL1 fields|2 /0|depth,calm as u64|
|2 decode grouping|rows1..8 /0|rows*8 expert u32 IDs|rows*8 /0|original row/pick indices as u32|
|3 chunk|4 /0|position,total,next_mark,context as u64|1 /0|chunk length u64|
|4 prefill grouping|rows1..128 /0|rows*8 expert u32 IDs|word_count / rows|u32 plan described below|

WFL1 fields: version,mode,capacity,depth,wait_ns,compute_ns,previous_compute_ns,
calm,pressure,reserved. Version1; mode0 sync,1 fixed,2 adaptive; cap1..32;
depth1..cap; timing values0..i64::MAX; calm0..3; pressure0/1; reserved0.
L689 cap is an expert preparation queue limit, not a conversation count.

Operation4 output: segment_count; then segment_count triples of
`expert_id,row_start,row_count`; then xmap[rows*8+8],ymap[rows*8+8],
shared_xmap[rows+8],shared_ymap[rows+8]. Routed xmap is token index, routed ymap
is token*9+pick. Shared ymap is token*9+8. All pad entries are zero.
The shared segment is implicit: expert256,start0,count=rows. Weight and scale
handles are intentionally absent from this logical schedule protocol.

EOF at a complete header boundary exits0. Truncation/domain/unknown operation
exits65; read/write failure exits74. Signals such as SIGPIPE remain possible.
No bytes for a failed input frame are published, but previous completed frames
remain visible. Failed output transport can leave a partial reply; the caller
must discard it. The protocol is unauthenticated; bind inputs to model/build
identities outside it and do not restore unrelated row state.

## Build and positive replay

Linux AArch64. Use a private copy of the qualified seeded compiler; verify its
SHA256 before compiling. Shell and existing OS tools only orchestrate files,
compilation, process pipes and evidence. All new executable logic is .om.

```sh
mkdir -p build/live35b
SEED=build/live35b/input/omc
printf '%s  %s\n' 191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9 "$SEED" | sha256sum -c -
cat native/live35b/select.om native/live35b/schedule.om native/live35b/wire.om native/live35b/consumer.om native/live35b/main.om > build/live35b/integrator.om
nice -n5 "$SEED" < build/live35b/integrator.om > build/live35b/integrator.tmp
file build/live35b/integrator.tmp
chmod +x build/live35b/integrator.tmp
mv build/live35b/integrator.tmp build/live35b/integrator
cat native/live35b/select.om native/live35b/tests/select.om > build/live35b/select-test.om
nice -n5 "$SEED" < build/live35b/select-test.om > build/live35b/select-test
chmod +x build/live35b/select-test
timeout 60 build/live35b/select-test
cat native/live35b/schedule.om native/live35b/tests/schedule.om > build/live35b/schedule-test.om
nice -n5 "$SEED" < build/live35b/schedule-test.om > build/live35b/schedule-test
chmod +x build/live35b/schedule-test
timeout 60 build/live35b/schedule-test
```

Require each command to succeed and each compiler output to be a nonempty
AArch64 ELF before chmod/execute. A failed compile must never run a stale file.
Private replay inputs are explicit; there is no compiler download or installation.

To build a protocol producer/golden, concatenate wire.om,tests/frames.om and the
chosen tests/{write,golden,full-write,full-golden,plan-write,plan-golden}.om.
Compile each with the same verified seed and require successful nonempty ELF.
`write` emits four operations repeated1000 times; `golden` emits their independent
stored expected responses. `full-*` covers the entire248320 vocabulary; `plan-*`
covers128-token prefill and every256 expert segment. Pipe producer through
integrator, then compare with golden bytes. `invalid.om` reads one ASCII digit
1..9 and emits an invalid request. Policy differential uses vendor/weight-flow-v1.om
as immutable reference and tests/flow-write.om plus tests/flow-raw.om as caller.
Detailed actual outcomes and preserved failures are in
[evidence](../../evidence/live35b-L739/RESULTS.md).

## Remaining end-to-end acceptance

The verified seed has no floating scalar syntax, native device allocation/mapping/
launch/readback interface, filenames/model-scale mappings or HTTP socket words.
L605's23 qualified native device cases cover openat/close/ioctl; its lab capsule
refuses launch. L408/L605/L690 retain ownership. A native plan or instruction
encoding is insufficient to run a GPU model. Requests are preserved in L739's
parent-actions.md and native-serving-consumer-request.md; parent acknowledged
relay, not completed interfaces.

Full checkpoint goldens/routes; GPU negative controls; actual concurrent-row
state isolation; long-context prefill; warm shared prefix; next-turn state;
HTTP/SSE tools and tool-result continuation; controlled serial baseline/candidate
and ablation timing; independent frozen-source review; hardware admission and
exact live cutover remain NOT_RUN. Keep issue2 open. Do not launch this stdin
consumer on18139 or substitute a legacy C/Rust server as the native candidate.
