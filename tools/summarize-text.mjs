// Evidence summary only; never called by installation or runtime.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
const read=p=>fs.readFileSync(p,'utf8'),json=p=>JSON.parse(read(p)),last=p=>JSON.parse(read(p).trim().split('\n').at(-1));
const sha=p=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const log=read('evidence/native-commands/converter.log');assert.ok(log.includes('ALL SUITES RC=0'));
function cases(pattern){const m=log.match(pattern);assert.ok(m);return Number(m[1]);}
const inherited={differential:cases(/^cases=(\d+) failures=0 RC=0$/m),refusals:cases(/^refusal cases=(\d+) failures=0 RC=0$/m),callers:cases(/^attachment cases=(\d+) failures=0 RC=0$/m),controls:cases(/^control cases=(\d+) failures=0 RC=0$/m),robustness:cases(/^robustness cases=(\d+) .* failures=0 RC=0$/m)};
const text=json('evidence/text-native/differential.json'),controls=json('evidence/text-native/controls.json'),red=json('evidence/text-native/baseline-red.json');
assert.equal(text.requested,text.executed);assert.equal(text.executed,text.source_cases*2);assert.equal(text.failed,0);assert.equal(text.passed,text.executed);
assert.equal(controls.requested,controls.executed);assert.equal(controls.failed,0);assert.ok(controls.rows.every(r=>r.compile_status===0&&r.executed));
assert.equal(red.requested,red.executed);assert.equal(red.failed,12);assert.equal(red.passed,6);
const math={};for(const name of ['gate','oracle','sign-fixtures','whitespace','robustness']){const r=last('evidence/native-commands/math-'+name+'.log');assert.equal(r.requested,r.executed);if('failed'in r)assert.equal(r.failed,0);math[name]=r;}
math.checks=last('evidence/native-commands/math-checks.log');assert.equal(math.checks.compiledValidMutants,math.checks.detectedMutants);
const native={};for(const [name,p] of [['commands','evidence/native-commands/commands.json'],['provenance','evidence/native-commands/provenance.json'],['paths','evidence/native-path-safety/full-gate-paths.json'],['developer','evidence/native-developer-commands/results.json']]){const r=json(p);if('failed'in r)assert.equal(r.failed,0);if('executed'in r)assert.equal(r.executed,r.passed);native[name]=r.passed;}
native.reviewRegression=last('evidence/native-commands/review-regression.log');assert.equal(native.reviewRegression.failed,0);assert.equal(native.reviewRegression.requested,native.reviewRegression.executed);
const sourceCases=Object.values(inherited).reduce((a,b)=>a+b,0)+text.source_cases+controls.executed;
assert.ok(read('evidence/text-native/full-native.log').includes('PASS converter, native math, installed commands, source provenance, path safety and native development'));
const report={ledger:'L551',converter:{suite_cases:sourceCases,inherited, text:{source_cases:text.source_cases,requested_target_checks:text.requested,executed_target_checks:text.executed,passed:text.passed},new_controls:{requested:controls.requested,executed:controls.executed,valid_compiled_mutants:controls.valid_compiled_mutants,library_callers:controls.library_callers},failures:0},red:{requested:red.requested,executed:red.executed,expected_failures:red.failed,preserved_refusals:red.passed},math,native,hashes:{}};
for(const p of ['src/toc.om','provenance/pins','provenance/sources.sha256','provenance/lock.sha256','tools/verify-sources.sh','build/bootstrap/omc','build/native/omc','build/native/bridge','build/native/math','evidence/text-native/parent-baseline.json','evidence/text-native/full-native.log','evidence/native-commands/converter.log'])report.hashes[p]=sha(p);
if(fs.existsSync('evidence/text-native/replay/result.json')){report.replay=json('evidence/text-native/replay/result.json');assert.equal(report.replay.ok,true);const again=json('evidence/text-native/replay/text-native/differential.json');assert.equal(again.executed,text.executed);assert.equal(again.failed,0);}
fs.writeFileSync('evidence/text-native/summary.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({...report,math:undefined,hashes:undefined,replay:report.replay?.commit}));
