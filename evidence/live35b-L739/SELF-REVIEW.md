# L739 author source review

Author review only. Independent review through parent remains required.
Reviewed source frozen at46b10c8ba82b2c5cf81fbfcc49c249a9fea4bd67.

- TopK bounds before global access; IEEE key normalizes both zeros, reverses
  negative finite/infinite ordering, and keeps lower token ID ties. NaNs refuse
  before publication. Heap height bound19 exceeds the current vocabulary tree
  height. Masks reset over exactly the new frame's range. Kept bits are original.
- Group validates all rows/IDs/duplicates before counting. Expert counts/starts/
  cursors reset each request; stable placement preserves input row/pick order.
  Segments max256 and768 scalar fields. Routed maps max1024+8 entries,shared
  maps128+8 entries. All fields exposed by each response are overwritten.
  Separate shared expert256 has count=rows,start0; weight addresses are absent.
- Queue policy validates signed-range timings before its strict integer arithmetic.
  previous+previous/4 fits the unsigned range for admitted inputs. Growth clamps
  to cap,pressure resets calm,capacity1 yields depth1/calm0. Original policy
  differential uses byte-exact vendor source, not a rewritten expected formula.
- Chunk validates pos<=total<=context<=49152 and next mark before subtraction;
  complete prompt has explicit0 result; stale marks refuse. It is a planner,
  not a proof of restored model state.
- Every parser requires complete fields. EOF is clean only before a new version
  word; body EOF is65. V is validated before filling arrays. Buffer loops bound
  each positive partial transfer by its byte capacity. Input failures publish no
  current-frame bytes; output failures can leave a partial frame, as documented.
  No filename,process-spawn,socket,device,foreign call or credential path exists.
- Current positive source rebuilt from an exact commit in a fresh export and
  matches final manifest and executable. Original compile failures,weak chunk
  test,failed empty-input run and stale first-package hash remain in evidence.

Open functional gaps: legacy NaN fallback compatibility; device tensor-handle
binding; native checkpoint loader/forward kernels; tokenizer/HTTP/SSE/tools;
model-route/golden/state/concurrency/quality/timing and live qualification.
Nothing in this source supports marking those gates passed. No speed threshold
was changed and no failed approximate quantizer was adopted.
