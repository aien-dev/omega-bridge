// Installed boundary regression: the documented CR separator must survive the
// command/alias adapter. Infrastructure only; all calculations run in native Omega.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'omega-parent-review-'));
const home=path.join(root,'home'),tmp=path.join(root,'tmp'),prefix=path.join(root,'prefix');
fs.mkdirSync(home);fs.mkdirSync(tmp);
const env={...process.env,HOME:home,TMPDIR:tmp,LC_ALL:'C'};
function run(command,args=[],input){return spawnSync(command,args,{cwd:os.tmpdir(),env,input,encoding:'utf8',timeout:180000,maxBuffer:32*1024*1024});}
const rows=[];
function check(name,test){try{test();rows.push({name,ok:true});}catch(e){rows.push({name,ok:false,error:e.message});}}
function assert(ok,message){if(!ok)throw Error(message);}
let installed=false;
try{
 const install=run(path.join(repo,'tools/install.sh'),['--offline','--prefix',prefix]);
 assert(!install.error&&install.status===0,'source-only installation failed: '+JSON.stringify(install));installed=true;
 const om=path.join(prefix,'bin/om'),omg=path.join(prefix,'bin/omg');
 check('omg resolves to the same implementation as om',()=>assert(fs.realpathSync(om)===fs.realpathSync(omg),'alias resolves elsewhere'));
 for(const name of ['om','omg']){
  const command=path.join(prefix,'bin',name);
  check(name+' accepts CR command whitespace',()=>{const r=run(command,['math','eval\r1']);assert(r.status===0&&r.stdout==='OK 1\n'&&r.stderr==='',JSON.stringify({status:r.status,stdout:r.stdout,stderr:r.stderr}));});
  check(name+' preserves stream CR and recovery',()=>{const r=run(command,['math'],'eval\r1\neval x/x\neval\r2\n');assert(r.status===0&&r.stdout==='OK 1\nREFUSED 3\nOK 2\n',JSON.stringify({status:r.status,stdout:r.stdout,stderr:r.stderr}));});
 }
 check('both names propagate identical one-shot refusal',()=>{const a=run(om,['math','eval x/x']),b=run(omg,['math','eval x/x']);assert(a.status===65&&b.status===65&&a.stdout===b.stdout&&a.stderr===b.stderr,JSON.stringify({a:{status:a.status,stdout:a.stdout},b:{status:b.status,stdout:b.stdout}}));});
}finally{
 if(installed){const r=run(path.join(prefix,'bin/om'),['uninstall']);check('isolated installation uninstalls both names',()=>assert(r.status===0&&!fs.existsSync(path.join(prefix,'bin/om'))&&!fs.existsSync(path.join(prefix,'bin/omg')),JSON.stringify(r)));}
 fs.rmSync(root,{recursive:true,force:true});
}
for(const row of rows)console.log(JSON.stringify(row));
const failed=rows.filter(x=>!x.ok).length;
console.log(JSON.stringify({requested:7,executed:rows.length,passed:rows.length-failed,failed}));
if(rows.length!==7||failed)process.exit(1);
