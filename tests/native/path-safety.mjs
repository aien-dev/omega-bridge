// L529: real filesystem boundary regressions, disposable source/HOME only.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const scratch=fs.mkdtempSync(path.join(os.tmpdir(),'omega-path-safety-'));
const copy=scratch+'/source',home=scratch+'/home',cwd=scratch+'/unrelated';
for(const p of [copy,home,cwd])fs.mkdirSync(p);
for(const p of ['tools','src','seed','provenance','docs','LICENSE','evidence/math-native'])fs.cpSync(repo+'/'+p,copy+'/'+p,{recursive:true});
const env={...process.env,HOME:home,LC_ALL:'C'};delete env.OMEGA_SEED;delete env.OMEGA_SOURCE;
const rows=[];
function run(exe,args=[]){const r=spawnSync(exe,args,{cwd,env,encoding:'utf8',timeout:180000,maxBuffer:32*1024*1024});assert.ifError(r.error);assert.equal(r.signal,null);return {status:r.status,stdout:r.stdout,stderr:r.stderr};}
function hash(p){return fs.existsSync(p)?createHash('sha256').update(fs.readFileSync(p)).digest('hex'):null;}
function check(name,fn){const row={name};try{fn(row);row.ok=true;}catch(e){row.ok=false;row.error=e.message;}rows.push(row);console.log(JSON.stringify(row));}
const install=prefix=>run(copy+'/tools/install.sh',['--offline','--prefix',prefix]);
const exists=p=>{try{fs.lstatSync(p);return true;}catch{return false;}};
// Every case must assert victim bytes, not merely a compiler/command exit.
for(const link of ['symlink','hardlink'])for(const output of ['bootstrap/seed0','bootstrap/seed0.self','bootstrap/stage1','bootstrap/omc','bridge.tmp','bridge','math-native/math.om','math-native/omega-math.tmp','math-native/omega-math','native/omc','native/bridge','native/math','native.sha256']){
 check(link+' build/'+output,row=>{
  const victim=scratch+'/victim';fs.writeFileSync(victim,'UNRELATED USER FILE\n');fs.chmodSync(victim,0o600);
  fs.mkdirSync(path.dirname(copy+'/build/'+output),{recursive:true});
  if(link==='symlink')fs.symlinkSync(victim,copy+'/build/'+output);else fs.linkSync(victim,copy+'/build/'+output);
  row.before=hash(victim);row.command=install(home+'/blocked');row.after=hash(victim);
  // Capture both symptoms even when old installer succeeds and destroys content.
  row.prefixCreated=exists(home+'/blocked');
  const preserved=row.before===row.after,refused=row.command.status===73&&!row.prefixCreated;
  fs.rmSync(copy+'/build',{recursive:true,force:true});fs.rmSync(home+'/blocked',{recursive:true,force:true});
  assert.ok(preserved,'victim content was overwritten');assert.ok(refused,'unsafe output was not refused before installation');
 });
}
for(const output of ['build','build/bootstrap','build/math-native','build/native'])check('directory symlink '+output,row=>{
 const outside=scratch+'/outside';fs.mkdirSync(outside);fs.writeFileSync(outside+'/seed0','UNRELATED USER FILE\n');
 fs.mkdirSync(path.dirname(copy+'/'+output),{recursive:true});fs.symlinkSync(outside,copy+'/'+output);
 row.before=hash(outside+'/seed0');row.command=install(home+'/blocked');row.after=hash(outside+'/seed0');row.outside=fs.readdirSync(outside);
 const safe=row.before===row.after&&row.outside.length===1;
 fs.rmSync(copy+'/build',{recursive:true,force:true});fs.rmSync(home+'/blocked',{recursive:true,force:true});fs.rmSync(outside,{recursive:true});
 assert.ok(safe,'build wrote through directory link');assert.equal(row.command.status,73);
});
// Prepare one actual installation, retain its valid manifest and modes in clones.
const template=home+'/template';
check('ordinary clean installation and rebuild',row=>{row.install=install(template);assert.equal(row.install.status,0);row.rebuild=run(copy+'/tools/build-native.sh');assert.equal(row.rebuild.status,0);});
const baseline=scratch+'/payload-template';fs.cpSync(template+'/lib/omega-native',baseline,{recursive:true,preserveTimestamps:true});
for(const parent of ['lib','bin','prefix','ancestor'])for(const entry of ['script','om','omg'])check(entry+' uninstall with linked '+parent,row=>{
 const root=home+'/case space '+parent+' '+entry,prefix=root+'/prefix',outside=scratch+'/moved '+parent+' '+entry;fs.mkdirSync(prefix+'/lib',{recursive:true});fs.mkdirSync(prefix+'/bin');
 fs.cpSync(baseline,prefix+'/lib/omega-native',{recursive:true});
 for(const n of ['om','omg'])fs.symlinkSync('../lib/omega-native/om',prefix+'/bin/'+n);
 if(parent==='prefix'){fs.renameSync(prefix,outside);fs.symlinkSync(outside,prefix);}
 else if(parent==='ancestor'){fs.renameSync(root,outside);fs.symlinkSync(outside,root);}
 else if(parent==='bin'){
  fs.mkdirSync(outside);fs.renameSync(prefix+'/bin',outside+'/bin');fs.symlinkSync(prefix+'/lib',outside+'/lib');fs.symlinkSync(outside+'/bin',prefix+'/bin');
 } else {fs.renameSync(prefix+'/'+parent,outside);fs.symlinkSync(outside,prefix+'/'+parent);}
 const victim=prefix+'/lib/omega-native/math';row.before=hash(victim);
 row.command=entry==='script'?run(copy+'/tools/uninstall.sh',['--prefix',prefix+'///']):run(prefix+'/bin/'+entry,['uninstall']);
 row.after=hash(victim);row.aliases=['om','omg'].map(n=>exists(prefix+'/bin/'+n));
 const safe=row.before===row.after&&row.aliases.every(Boolean);
 // Remove only this test's synthetic trees, avoiding traversing symlinks.
 fs.rmSync(root,{recursive:true,force:true});fs.rmSync(outside,{recursive:true,force:true});
 assert.ok(safe,'uninstall deleted relocated payload or aliases');assert.equal(row.command.status,73);
});
check('dangling prefix refuses without changes',row=>{const p=home+'/dangling';fs.symlinkSync(scratch+'/missing',p);row.command=run(copy+'/tools/uninstall.sh',['--prefix',p+'/']);assert.equal(row.command.status,73);assert.ok(fs.lstatSync(p).isSymbolicLink());});
check('normal aliases, refusal, payload integrity and uninstall',row=>{
 const om=template+'/bin/om',omg=template+'/bin/omg';assert.equal(fs.realpathSync(om),fs.realpathSync(omg));
 for(const args of [['math','eval 1/2'],['math','eval 1/0'],['version']])assert.deepEqual(run(om,args),run(omg,args));
 row.integrity=run('sh',['-c','cd "$1" && sha256sum --status -c files.sha256','sh',template+'/lib/omega-native']);assert.equal(row.integrity.status,0);
 row.command=run(omg,['uninstall']);assert.equal(row.command.status,0);assert.ok(!exists(om)&&!exists(omg));assert.ok(!exists(home+'/.config'));
});
const report={source:process.env.L529_SOURCE||'working-tree',passed:rows.filter(r=>r.ok).length,failed:rows.filter(r=>!r.ok).length,rows};
if(process.env.L529_REPORT)fs.writeFileSync(process.env.L529_REPORT,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({passed:report.passed,failed:report.failed}));
fs.rmSync(scratch,{recursive:true});
if(report.failed)process.exitCode=1;
