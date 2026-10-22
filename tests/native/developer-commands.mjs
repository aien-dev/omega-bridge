// L543 real installed developer-command checks; Node is test infrastructure only.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const work=fs.mkdtempSync(path.join(os.tmpdir(),'omega-developer-'));
const home=work+'/home',tmp=work+'/tmp',cwd=work+'/unrelated';
for(const p of [home,tmp,cwd])fs.mkdirSync(p);
const prefix=home+'/prefix space',payload=prefix+'/lib/omega-native';
const env={...process.env,HOME:home,TMPDIR:tmp,LC_ALL:'C'};delete env.OMEGA_SEED;delete env.OMEGA_SOURCE;
const rows=[];
function run(exe,args=[],input){const r=spawnSync(exe,args,{cwd,env,input,encoding:null,timeout:60000,maxBuffer:16*1024*1024});assert.ifError(r.error);assert.equal(r.signal,null);return r;}
function result(r,n,out=''){assert.equal(r.status,n,r.stderr.toString());assert.equal(r.stdout.toString(),out);}
function check(name,fn){try{fn();assert.deepEqual(fs.readdirSync(tmp),[],'private request directories leaked');rows.push({name,ok:true});}catch(e){rows.push({name,ok:false,error:e.message});}}
function hash(p){return createHash('sha256').update(fs.readFileSync(p)).digest('hex');}
const source=cwd+'/program with space.om',echo=cwd+'/echo.om',bad=cwd+'/bad.om';
fs.writeFileSync(source,'text msg "NATIVE\\n"\nfn main to int\nw = write 1 msg 0 len msg\nret 23\nend\n');
fs.writeFileSync(echo,'global buf uchar 4096\nfn main to int\nn = long 1\nwhile gt n 0\nn = read 0 buf 0 4096\nif gt n 0\nw = write 1 buf 0 ulong n\nend\nend\nret 0\nend\n');
fs.writeFileSync(bad,'fn main to int\nret unknown\nend\n');
let installed=false;
try{
 const installation=run(repo+'/tools/install.sh',['--offline','--prefix',prefix]);assert.equal(installation.status,0,installation.stderr.toString());installed=true;
 const om=prefix+'/bin/om',omg=prefix+'/bin/omg';
 const call=(name,args,input)=>run(prefix+'/bin/'+name,args,input);
 check('one implementation for both names',()=>assert.equal(fs.realpathSync(om),fs.realpathSync(omg)));
 for(const name of ['om','omg']){
  check(name+' checks without execution',()=>result(call(name,['check',source]),0));
  check(name+' rejects invalid source',()=>result(call(name,['check',bad]),65));
  check(name+' refuses missing input',()=>result(call(name,['check',cwd+'/missing']),66));
  check(name+' rejects extra arguments',()=>result(call(name,['run',source,'argument']),64));
  check(name+' runs native stdout and status',()=>result(call(name,['run',source]),23,'NATIVE\n'));
  check(name+' preserves raw program stdin',()=>{const input=Buffer.concat([Buffer.from('input\0\xff\n','binary'),Buffer.alloc(12000,97)]);const r=call(name,['run',echo],input);assert.equal(r.status,0,r.stderr.toString());assert.deepEqual(r.stdout,input);});
  check(name+' builds silent executable output',()=>{const out=cwd+'/'+name+' native output';result(call(name,['build',source,'-o',out]),0);assert.equal(fs.statSync(out).mode&0o777,0o700);const bytes=fs.readFileSync(out);assert.equal(bytes.subarray(0,4).toString('hex'),'7f454c46');assert.equal(bytes.readUInt16LE(18),183);result(run(out),23,'NATIVE\n');});
 }
 check('leading-dash source is literal after --',()=>{fs.copyFileSync(source,cwd+'/-source.om');result(call('om',['check','--','-source.om']),0);});
 check('literal dash source is not stdin',()=>{fs.copyFileSync(source,cwd+'/-');result(call('om',['check','--','-'],Buffer.from('not source')),0);});
 check('literal dash run preserves program stdin',()=>{fs.copyFileSync(echo,cwd+'/-');result(call('omg',['run','--','-'],Buffer.from('program input')),0,'program input');});
 check('conversion snapshots literal dash file instead of caller stdin',()=>{fs.copyFileSync(repo+'/tests/fixtures/fib.om',cwd+'/-');const a=call('om',['convert','--to','python',repo+'/tests/fixtures/fib.om']),b=call('omg',['convert','--to','python','--','-'],Buffer.from('invalid source'));assert.equal(a.status,0,a.stderr.toString());assert.equal(b.status,0,b.stderr.toString());assert.deepEqual(a.stdout,b.stdout);});
 check('shell metacharacters are literal filenames',()=>{const p=cwd+'/$(touch PWNED); program.om';fs.copyFileSync(source,p);result(call('omg',['run',p]),23,'NATIVE\n');assert.ok(!fs.existsSync(cwd+'/PWNED'));});
 check('check accepts a source symlink snapshot',()=>{const p=cwd+'/source link';fs.symlinkSync(source,p);result(call('om',['check',p]),0);});
 check('directory is not an input file',()=>result(call('om',['check',cwd]),66));
 check('build needs explicit destination',()=>result(call('om',['build',source]),64));
 check('failed compilation preserves existing output and mode',()=>{const p=cwd+'/keep';fs.writeFileSync(p,'UNRELATED');fs.chmodSync(p,0o640);const before=hash(p);result(call('om',['build',bad,'-o',p]),65);assert.equal(hash(p),before);assert.equal(fs.statSync(p).mode&0o777,0o640);});
 check('failed compilation creates no output',()=>{const p=cwd+'/absent';result(call('om',['build',bad,'-o',p]),65);assert.ok(!fs.existsSync(p));});
 check('successful explicit build atomically replaces regular file',()=>{const p=cwd+'/replace';fs.writeFileSync(p,'old');result(call('om',['build',source,'-o',p]),0);result(run(p),23,'NATIVE\n');assert.equal(fs.statSync(p).mode&0o777,0o700);});
 check('build never follows an output symlink',()=>{const victim=cwd+'/victim',out=cwd+'/output link';fs.writeFileSync(victim,'PRESERVE');fs.symlinkSync(victim,out);const before=hash(victim);result(call('om',['build',source,'-o',out]),73);assert.equal(hash(victim),before);assert.ok(fs.lstatSync(out).isSymbolicLink());});
 check('build rename preserves a hardlink peer',()=>{const victim=cwd+'/hardlink victim',out=cwd+'/hard output';fs.writeFileSync(victim,'PRESERVE');fs.linkSync(victim,out);const before=hash(victim);result(call('om',['build',source,'-o',out]),0);assert.equal(hash(victim),before);result(run(out),23,'NATIVE\n');});
 check('unavailable destination refuses without residue',()=>{result(call('om',['build',source,'-o',cwd+'/no-parent/program']),73);assert.ok(!fs.existsSync(cwd+'/no-parent'));});
 check('nonregular destination is preserved',()=>result(call('om',['build',source,'-o',cwd]),73));
 const manifest=fs.readFileSync(payload+'/files.sha256','utf8');
 function rehash(){fs.writeFileSync(payload+'/files.sha256',manifest.split('\n').filter(Boolean).map(line=>{const name=line.slice(66);return hash(payload+'/'+name)+'  '+name;}).join('\n')+'\n');}
 check('ELF verifier is owned and hash-checked',()=>{const helper=payload+'/verify-elf.sh';assert.ok(fs.existsSync(helper),'installed ELF helper missing');assert.equal(fs.statSync(helper).mode&0o777,0o700);const original=fs.readFileSync(helper);try{fs.appendFileSync(helper,'\n# changed\n');result(call('om',['check',source]),65);}finally{fs.writeFileSync(helper,original);}});
 check('wrong native compiler cannot publish or run non-ELF',()=>{const compiler=fs.readFileSync(payload+'/omc');try{fs.copyFileSync(payload+'/math',payload+'/omc');rehash();for(const cmd of [['check',source],['run',source],['build',source,'-o',cwd+'/bad-elf']])result(call('om',cmd),65);assert.ok(!fs.existsSync(cwd+'/bad-elf'));}finally{fs.writeFileSync(payload+'/omc',compiler);fs.writeFileSync(payload+'/files.sha256',manifest);}});
 check('actual run uses no foreign compiler/interpreter fallback',()=>{const trace=work+'/run.trace',r=run('strace',['-f','-e','trace=execve','-o',trace,om,'run',source]);result(r,23,'NATIVE\n');const text=fs.readFileSync(trace,'utf8');assert.doesNotMatch(text,/execve\("[^"\n]*\/(?:gcc|cc|clang|rustc|cargo|python3?|node|aien-calc|ld|as)"/);assert.ok(text.includes('/omc'));assert.ok(text.includes('/native'));fs.mkdirSync(repo+'/evidence/native-developer-commands',{recursive:true});fs.writeFileSync(repo+'/evidence/native-developer-commands/run-exec.trace',text);});
 check('build never overwrites its own source',()=>{const p=cwd+'/preserve source.om';fs.copyFileSync(source,p);const before=hash(p),r=call('om',['build',p,'-o',p]);assert.equal(hash(p),before,'successful build destroyed its own source');result(r,73);});
 check('invalid run never prints program output',()=>result(call('omg',['run',bad]),65));
 check('help documents native developer commands',()=>{const r=call('om',['help']);assert.equal(r.status,0);for(const s of ['om check','om build','om run'])assert.ok(r.stdout.toString().includes(s),s);});
} finally {
 if(installed)check('uninstall removes all new owned files and both aliases',()=>{const r=run(prefix+'/bin/om',['uninstall']);assert.equal(r.status,0,r.stderr.toString());assert.ok(!fs.existsSync(prefix+'/bin/om'));assert.ok(!fs.existsSync(prefix+'/bin/omg'));assert.ok(!fs.existsSync(payload));});
 fs.rmSync(work,{recursive:true,force:true});
}
for(const row of rows)console.log(JSON.stringify(row));
const failed=rows.filter(x=>!x.ok).length;
const report={source:process.env.NATIVE_DEVELOPER_SOURCE||'working-tree',executed:rows.length,passed:rows.length-failed,failed,rows};
fs.mkdirSync(repo+'/evidence/native-developer-commands',{recursive:true});
fs.writeFileSync(process.env.NATIVE_DEVELOPER_REPORT||repo+'/evidence/native-developer-commands/results.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({executed:rows.length,passed:rows.length-failed,failed}));
assert.ok(rows.length>=30,'developer checks were skipped');
if(failed)process.exit(1);
