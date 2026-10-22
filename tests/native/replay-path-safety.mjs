// L529 committed source-only replay. Node, Git, tar and strace are test tools.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const reportDir=repo+'/evidence/native-path-safety';
const scratch=fs.mkdtempSync(path.join(os.tmpdir(),'omega-l529-replay-'));
const source=scratch+'/source',home=scratch+'/home',cwd=scratch+'/unrelated',tmp=scratch+'/tmp';
for(const p of [source,home,cwd,tmp])fs.mkdirSync(p);
const env={...process.env,HOME:home,TMPDIR:tmp,LC_ALL:'C'};delete env.OMEGA_SEED;delete env.OMEGA_SOURCE;
function run(command,args=[],options={}){const r=spawnSync(command,args,{cwd,env,encoding:'utf8',timeout:300000,maxBuffer:64*1024*1024,...options});assert.ifError(r.error);assert.equal(r.signal,null);return r;}
function success(r){assert.equal(r.status,0,r.stderr);return r;}
function hash(p){return createHash('sha256').update(fs.readFileSync(p)).digest('hex');}
const commit=success(run('git',['-C',repo,'rev-parse','HEAD'])).stdout.trim();
const report={commit,host:success(run('uname',['-sm'])).stdout.trim(),commands:[],hashes:{}};
try{
 const archive=success(run('git',['-C',repo,'archive',commit],{encoding:null}));
 success(run('tar',['-x','-C',source],{input:archive.stdout}));
 assert.ok(!fs.existsSync(source+'/build'),'export must contain source only');
 success(run(source+'/tools/verify-sources.sh'));
 const prefix=home+'/prefix space',payload=prefix+'/lib/omega-native';
 const trace=reportDir+'/replay-build.trace';
 const install=success(run('strace',['-f','-e','trace=execve','-o',trace,source+'/tools/install.sh','--offline','--prefix',prefix]));
 report.commands.push({command:'strace source/tools/install.sh --offline --prefix isolated-HOME/prefix-space',status:install.status,stdout:install.stdout,stderr:install.stderr,cwd:'unrelated'});
 const t=fs.readFileSync(trace,'utf8');
 assert.doesNotMatch(t,/execve\("[^"\n]*\/(?:gcc|cc|clang|rustc|cargo|python3?|node|aien-calc|ld|as)"/);
 for(const n of ['seed0','hex1','asm2','om4','stage1','bootstrap/omc'])assert.ok(t.includes(n));
 for(const n of ['omc','bridge','math']){
  const expected=hash(repo+'/build/native/'+n),built=hash(source+'/build/native/'+n),installed=hash(payload+'/'+n);
  report.hashes[n]={expected,built,installed};assert.equal(built,expected);assert.equal(installed,expected);
  const elf=fs.readFileSync(payload+'/'+n);assert.equal(elf.readUInt16LE(18),183);
  assert.doesNotMatch(success(run('readelf',['-l',payload+'/'+n])).stdout,/INTERP/);
  assert.doesNotMatch(success(run('readelf',['-d',payload+'/'+n])).stdout,/NEEDED/);
 }
 assert.equal(fs.realpathSync(prefix+'/bin/om'),fs.realpathSync(prefix+'/bin/omg'));
 for(const args of [['math','eval 1/2'],['math','eval 1/0'],['convert','--to','c',source+'/tests/fixtures/fib.om'],['version']]){
  const a=run(prefix+'/bin/om',args),b=run(prefix+'/bin/omg',args);
  assert.deepEqual([a.status,a.stdout,a.stderr],[b.status,b.stdout,b.stderr]);
  if(args[1]==='eval 1/2'){assert.equal(a.status,0);assert.equal(a.stdout,'OK 1/2\n');}
  else if(args[1]==='eval 1/0'){assert.equal(a.status,65);assert.equal(a.stdout,'REFUSED 2\n');}
  else assert.equal(a.status,0,a.stderr);
  report.commands.push({command:'om/omg '+args.join(' '),status:a.status,identical:true});
 }
 const paths=run('node',[source+'/tests/native/path-safety.mjs'],{env:{...env,L529_SOURCE:commit,L529_REPORT:reportDir+'/replay-paths.json'}});
 fs.writeFileSync(reportDir+'/replay-paths.log',paths.stdout+paths.stderr);success(paths);
 report.pathChecks=JSON.parse(fs.readFileSync(reportDir+'/replay-paths.json')).passed;
 const uninstall=success(run(prefix+'/bin/omg',['uninstall']));
 report.commands.push({command:'isolated prefix/bin/omg uninstall',status:uninstall.status,stdout:uninstall.stdout,stderr:uninstall.stderr});
 assert.deepEqual(fs.readdirSync(home),[],'aliases, payload and isolated user state must be absent');
 report.ok=true;
} catch(e){report.ok=false;report.error=e.message;throw e;}
finally{
 fs.writeFileSync(reportDir+'/replay.json',JSON.stringify(report,null,2)+'\n');
 fs.rmSync(scratch,{recursive:true});
}
console.log('PASS committed source export, byte-identical native executables, aliases, path controls and uninstall');
