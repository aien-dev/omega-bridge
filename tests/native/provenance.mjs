// Negative source/lock controls operate only on disposable copied source trees.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
const repo=process.cwd(),tmp=fs.mkdtempSync('/tmp/omega-provenance-'),copy=tmp+'/source';
fs.mkdirSync(copy);fs.mkdirSync(tmp+'/home');
for(const p of ['tools','src','seed','provenance','docs','LICENSE','evidence'])fs.cpSync(repo+'/'+p,copy+'/'+p,{recursive:true});
const rows=[];
function run(exe,args=[],cwd=copy){const r=spawnSync(exe,args,{cwd,env:{...process.env,HOME:tmp+'/home'},encoding:'utf8',timeout:60000});assert.ifError(r.error);assert.equal(r.signal,null);return r;}
function check(name,fn){fn();rows.push({name,ok:true});console.log('PASS '+name);}
function eq(r,n){assert.equal(r.status,n,r.stderr);}
check('dynamic host ELF refused by build qualification gate',()=>eq(run('tools/verify-elf.sh',['/bin/true']),65));
check('empty executable refused',()=>{fs.writeFileSync(tmp+'/empty','');eq(run('tools/verify-elf.sh',[tmp+'/empty']),65);});
check('copied source has valid immutable provenance',()=>eq(run('tools/verify-sources.sh'),0));
for(const [name,p,change] of [
 ['dirty native math','seed/math/core.om',s=>s+'\nnote changed\n'],
 ['dirty converter','src/toc.om',s=>s+'\nnote changed\n'],
 ['dirty seed compiler','seed/omc/omc.om',s=>s+'\nnote changed\n'],
 ['malformed pin','provenance/pins',s=>s.replace(/^math [0-9a-f]{40}$/m,'math $(touch PWNED)')],
 ['different pin','provenance/pins',s=>s.replace(/^math [0-9a-f]{40}$/m,'math '+'0'.repeat(40))],
 ['unsafe import path','provenance/seed.files',s=>s+'../../outside\n'],
 ['forged source manifest','provenance/sources.sha256',s=>s.replace(/^[0-9a-f]/,'z')],
 ['forged lock','provenance/lock.sha256',s=>s+'garbage\n']
])check(name+' fails before build/publication',()=>{
 const file=copy+'/'+p,original=fs.readFileSync(file,'utf8'),changed=change(original);assert.notEqual(changed,original,'negative control must actually mutate '+p);fs.writeFileSync(file,changed);
 const r=run('tools/install.sh',['--offline','--prefix',tmp+'/home/blocked']);eq(r,65);assert.ok(!fs.existsSync(tmp+'/home/blocked'));assert.ok(!fs.existsSync(copy+'/PWNED'));fs.writeFileSync(file,original);eq(run('tools/verify-sources.sh'),0);
});
check('unlisted source include overlay refused',()=>{fs.writeFileSync(copy+'/seed/math/overlay.om','note overlay\n');eq(run('tools/verify-sources.sh'),65);fs.unlinkSync(copy+'/seed/math/overlay.om');});
check('same-byte source symlink refused',()=>{const p=copy+'/seed/math/core.om';fs.renameSync(p,tmp+'/core.om');fs.symlinkSync(tmp+'/core.om',p);eq(run('tools/verify-sources.sh'),65);fs.unlinkSync(p);fs.renameSync(tmp+'/core.om',p);});
check('no installed compiler override or fallback',()=>{
 const r=spawnSync('tools/install.sh',['--offline','--prefix',tmp+'/home/override'],{cwd:copy,env:{...process.env,HOME:tmp+'/home',OMEGA_SEED:'/missing/compiler',OMEGA_SOURCE:'/missing/source'},encoding:'utf8',timeout:60000});eq(r,0);
 eq(run(tmp+'/home/override/bin/om',['math','eval 1/2']),0);eq(run(tmp+'/home/override/bin/om',['uninstall']),0);
});
check('offline missing upstream pin refused',()=>{fs.mkdirSync(tmp+'/cache');eq(run('git',['init','-q',tmp+'/cache']),0);const r=run('tools/import-sources.sh',['--offline',tmp+'/cache']);eq(r,65);assert.match(r.stderr,/offline source pin missing/);});
check('dirty upstream cache refused before import',()=>{fs.writeFileSync(tmp+'/cache/dirty','changed');const r=run('tools/import-sources.sh',['--offline',tmp+'/cache']);eq(r,65);assert.match(r.stderr,/dirty source cache refused/);});
check('unsupported host rejected before writes',()=>{
 fs.mkdirSync(tmp+'/bin');fs.writeFileSync(tmp+'/bin/uname','#!/bin/sh\nprintf "x86_64\\n"\n',{mode:0o700});
 const r=spawnSync('tools/install.sh',['--offline','--prefix',tmp+'/home/wrong-host'],{cwd:copy,env:{...process.env,HOME:tmp+'/home',PATH:tmp+'/bin:'+process.env.PATH},encoding:'utf8'});eq(r,69);assert.ok(!fs.existsSync(tmp+'/home/wrong-host'));
});
check('source build trace contains no first-party C/Rust toolchain',()=>{
 const r=run('strace',['-f','-e','trace=execve','-o',tmp+'/build.trace','tools/install.sh','--offline','--prefix',tmp+'/home/traced']);eq(r,0);
 const trace=fs.readFileSync(tmp+'/build.trace','utf8');assert.doesNotMatch(trace,/execve\("[^"\n]*\/(?:gcc|cc|clang|rustc|cargo|python3?|node|aien-calc|ld|as)"/);
 for(const exe of ['seed0','hex1','asm2','om4','stage1','bootstrap/omc'])assert.ok(trace.includes(exe),exe);
 fs.writeFileSync(repo+'/evidence/native-commands/build-exec.trace',trace);eq(run(tmp+'/home/traced/bin/om',['uninstall']),0);
});
fs.writeFileSync(repo+'/evidence/native-commands/provenance.json',JSON.stringify({passed:rows.length,results:rows},null,2)+'\n');
console.log(`PASS ${rows.length} source provenance checks`);
fs.rmSync(tmp,{recursive:true});
