import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'omega-name-'));
const home=root+'/home',cwd=root+'/project';
fs.mkdirSync(home);fs.mkdirSync(cwd);
const env={...process.env,HOME:home,LC_ALL:'C'};
const prefix=home+'/prefix space';
const run=(exe,args=[])=>{const r=spawnSync(exe,args,{cwd,env,encoding:'utf8',timeout:60000});assert.ifError(r.error);return r;};
const install=()=>run(repo+'/tools/install.sh',['--offline','--prefix',prefix]);
const rows=[];
function test(name,fn){try{fn();rows.push({name,ok:true});}catch(e){rows.push({name,ok:false,error:e.message});}}
try {
 const r=install();assert.equal(r.status,0,r.stderr);
 test('omega is installed as the identical third alias',()=>{
  assert.ok(fs.existsSync(prefix+'/bin/omega'),'omega command missing');
  for(const name of ['om','omg'])assert.equal(fs.realpathSync(prefix+'/bin/omega'),fs.realpathSync(prefix+'/bin/'+name));
 });
 fs.writeFileSync(cwd+'/hello.om','text msg "OMEGA\\n"\nfn main to int\nw = write 1 msg 0 len msg\nret 0\nend\n');
 test('omega checks builds and runs a real native project',()=>{
  for(const args of [['check','hello.om'],['build','hello.om','-o','hello']]){const r=run(prefix+'/bin/omega',args);assert.equal(r.status,0,r.stderr);assert.equal(r.stdout,'');}
  const built=run(cwd+'/hello');assert.equal(built.status,0);assert.equal(built.stdout,'OMEGA\n');
  const r=run(prefix+'/bin/omega',['run','hello.om']);assert.equal(r.status,0,r.stderr);assert.equal(r.stdout,built.stdout);
 });
 test('all command names preserve matching help and version',()=>{
  for(const verb of ['help','version']){const reference=run(prefix+'/bin/om',[verb]);for(const name of ['omega','omg']){const r=run(prefix+'/bin/'+name,[verb]);assert.equal(r.status,reference.status);assert.equal(r.stdout,reference.stdout);assert.equal(r.stderr,reference.stderr);}}
 });
 test('changed omega alias blocks uninstall and preserves payload',()=>{
  const alias=prefix+'/bin/omega';if(fs.existsSync(alias))fs.unlinkSync(alias);
  fs.symlinkSync('/bin/false',alias);
  try {const r=run(prefix+'/bin/om',['uninstall']);assert.equal(r.status,73);assert.ok(fs.existsSync(prefix+'/lib/omega-native/omc'));}
  finally {fs.unlinkSync(alias);fs.symlinkSync('../lib/omega-native/om',alias);}
 });
 test('omega uninstall removes all three aliases',()=>{
  const r=run(prefix+'/bin/om',['uninstall']);assert.equal(r.status,0,r.stderr);
  for(const name of ['omega','om','omg'])assert.ok(!fs.existsSync(prefix+'/bin/'+name)&&!fs.lstatSync(prefix+'/bin/'+name,{throwIfNoEntry:false}));
  assert.ok(!fs.existsSync(prefix+'/lib/omega-native'));
 });
 // Each collision is a real filesystem object, not a mocked install response.
 for(const kind of ['regular','dangling symlink'])test('existing omega '+kind+' is preserved without partial installation',()=>{
  fs.mkdirSync(prefix+'/bin',{recursive:true});const target=prefix+'/bin/omega';
  if(kind==='regular')fs.writeFileSync(target,'UNRELATED');else fs.symlinkSync('/missing-omega-owned-elsewhere',target);
  const r=install();assert.equal(r.status,73,r.stderr);
  if(kind==='regular')assert.equal(fs.readFileSync(target,'utf8'),'UNRELATED');else assert.equal(fs.readlinkSync(target),'/missing-omega-owned-elsewhere');
  for(const n of ['om','omg'])assert.ok(!fs.lstatSync(prefix+'/bin/'+n,{throwIfNoEntry:false}));
  assert.ok(!fs.existsSync(prefix+'/lib/omega-native'));fs.unlinkSync(target);
 });
} finally {fs.rmSync(root,{recursive:true,force:true});}
for(const row of rows)console.log(JSON.stringify(row));
const failures=rows.filter(r=>!r.ok).length;
console.log(JSON.stringify({executed:rows.length,failed:failures}));
assert.equal(failures,0,'omega command regressions');
