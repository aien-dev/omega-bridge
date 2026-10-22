# Omega Bridge design

## User goal
A standalone repo that enables Omega to attach to existing languages and tools, convert efficiently, replace invisible internals, and leave familiar interfaces intact. Adoption should demand as little change as possible. Target broad language reach, not a false claim that arbitrary languages already translate perfectly.

## Coordinator architecture decision
Use one checked Omega semantic core with target adapters, not N-by-N text replacements. Implement converter logic and emitted runtimes in Omega wherever the existing language can express them. C output provides a native interoperability route; Python source output provides a directly executable first second-language backend. Distinguish source conversion from a language binding: a binding calls qualified Omega code and does not pretend to translate arbitrary host-language programs. Add other languages via a documented adapter/capability contract. New language inputs require their own checked frontends.

## Required semantics
Fixed widths, explicit conversions, bounded arrays with carried lengths, preserved operation order and alias rules, exact observable stdout/exit/trap/refusal behavior within the declared subset. Unsupported dynamic/reflection/concurrency/foreign-runtime semantics must refuse explicitly, with a clear diagnostic. Generated C must avoid undefined behavior; Python must reproduce fixed-width behavior rather than silently use unbounded arithmetic. GCC and Python are target tools/oracles, not dependencies of Omega's seed birth.

## Acceptance
First deliver C and Python for an explicit supported Omega subset and an honest feature matrix. Reuse L440 recovered source without editing its tree. Build converter using the qualified seed, run native Omega and emitted C/Python on the same corpus including forward/mutual calls, fib, bytecopy/echo/sort, signed and unsigned boundaries, bounds/conversion traps and malformed inputs. Add mutation controls and repeatability. Prove a real C caller and a Python caller can invoke a converted Omega function; document copy/ownership/ABI costs. No GPU, driver, live motor or systemwide replacements.

## Adoption and efficiency
CLI first, noninteractive reproducible build, examples a stranger can run without GPU. Defaults inspect or build an isolated candidate, never overwrite another application. Include dry-run, explicit opt-in, rollback path, and compatibility checks before replacing an implementation. Measure conversion time and end-to-end runtime/call overhead against the same workload and record all results, including regressions. Massive speedups are a goal, not a claim. Preserve correctness before any default replacement.

## Scope boundaries
Do not install Jarvis, switch drivers, change 18091, alter other worktrees, or claim arbitrary Python-to-Omega/C-to-Omega conversion. A universal framework is extensible; each actual language support needs its own executable gates. Preserve original AGPL licence and record recovered-source provenance. Audit before any public flip.
