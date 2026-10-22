// L551 source-only replay: export committed files, rebuild seed, run every gate.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const repo=process.cwd(),scratch=fs.mkdtempSync('/tmp/omega-l551-replay-'),source=scratch+'/source',home=scratch+'/home',tmp=scratch+'/tmp',cwd=scratch+'/unrelated';
for(const p of [source,home,tmp,cwd])fs.mkdirSync(p);
const env={...process.env,HOME:home,TMPDIR:tmp,LC_ALL:'C'};delete env.OMEGA_SEED;delete env.OMEGA_SOURCE;
function run(exe,args=[],options={}){const r=spawnSync(exe,args,{cwd,env,timeout:600000,maxBuffer:64*1024*1024,...options});assert.ifError(r.error);assert.equal(r.signal,null);return r;}
function okay(r){assert.equal(r.status,0,r.stderr.toString());return r;}
const hash=p=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const commit=okay(run('git',['-C',repo,'rev-parse','HEAD'])).stdout.toString().trim(),report={commit,source_only:true,commands:[],hashes:{}};
const out=repo+'/evidence/text-native/replay';fs.mkdirSync(out,{recursive:true});
try{
 const archive=okay(run('git',['-C',repo,'archive',commit]));okay(run('tar',['-x','-C',source],{input:archive.stdout}));
 assert.ok(!fs.existsSync(source+'/build'));
 // Run the complete test entry from an exported tree with no Git or sibling dependency.
 const gate=run(source+'/tools/test-native.sh',[],{cwd:source});fs.writeFileSync(out+'/full.log',Buffer.concat([gate.stdout,gate.stderr]));okay(gate);report.commands.push({command:'source/tools/test-native.sh',status:gate.status});
 for(const p of ['native-commands','native-path-safety','native-developer-commands','text-native'])fs.cpSync(source+'/evidence/'+p,out+'/'+p,{recursive:true,filter:q=>!q.includes('/replay')});
 for(const n of ['omc','bridge','math']){const expected=hash(repo+'/build/native/'+n),actual=hash(source+'/build/native/'+n);assert.equal(actual,expected);report.hashes[n]={expected,actual};}
 const prefix=home+'/prefix space',payload=prefix+'/lib/omega-native',trace=out+'/install.trace';
 const installed=okay(run('strace',['-f','-e','trace=execve','-o',trace,source+'/tools/install.sh','--offline','--prefix',prefix]));report.commands.push({command:'strace source/tools/install.sh --offline --prefix isolated-HOME/prefix-space',status:installed.status});
 const calls=fs.readFileSync(trace,'utf8');assert.doesNotMatch(calls,/execve\("[^"\n]*\/(?:gcc|cc|clang|rustc|cargo|python3?|node|aien-calc|ld|as)"/);
 for(const n of ['seed0','hex1','asm2','om4','stage1','bootstrap/omc'])assert.ok(calls.includes(n));
 for(const n of ['omc','bridge','math']){report.hashes[n].installed=hash(payload+'/'+n);assert.equal(report.hashes[n].installed,report.hashes[n].expected);}
 assert.equal(fs.realpathSync(prefix+'/bin/om'),fs.realpathSync(prefix+'/bin/omg'));
 const program=cwd+'/text.om';fs.writeFileSync(program,Buffer.concat([Buffer.from('text t "A'),Buffer.from([0,255]),Buffer.from('\\n"\nfn main to int\nw = write 1 t 0 len t\nret 23\nend\n')]));
 for(const target of ['c','python']){
  const args=['convert','--to',target,program],a=okay(run(prefix+'/bin/om',args)),alias=okay(run(prefix+'/bin/omg',args));assert.deepEqual(alias.stdout,a.stdout);
  const file=cwd+'/text.'+(target==='c'?'c':'py');fs.writeFileSync(file,a.stdout);
  let got;if(target==='c'){okay(run('gcc',['-std=gnu11',file,'-o',cwd+'/text']));got=run(cwd+'/text');}else got=run('python3',[file]);
  assert.equal(got.status,23);assert.equal(got.stdout.toString('hex'),'4100ff0a');assert.equal(got.stderr.length,0);
  report.commands.push({command:'om/omg convert --to '+target+' raw-byte-text.om; actual target execution',status:0,program_status:got.status,stdout_hex:got.stdout.toString('hex')});
 }
 okay(run(prefix+'/bin/omg',['uninstall']));assert.deepEqual(fs.readdirSync(home),[]);report.ok=true;
}catch(e){report.ok=false;report.error=e.message;throw e;}
finally{fs.writeFileSync(out+'/result.json',JSON.stringify(report,null,2)+'\n');fs.rmSync(scratch,{recursive:true});}
console.log('PASS committed source-only full gate, isolated installation, byte-identical executables and actual text targets');
