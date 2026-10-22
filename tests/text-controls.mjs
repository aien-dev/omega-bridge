// Valid compiled mutant execution controls, plus actual library view callers.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const b=process.cwd()+'/build/text-controls';fs.mkdirSync(b,{recursive:true});
const hash=x=>createHash('sha256').update(x).digest('hex');
function run(exe,args=[],input){const r=spawnSync(exe,args,{input,timeout:20000,maxBuffer:16*1024*1024});assert.ifError(r.error);assert.equal(r.signal,null);return r;}
const obs=r=>({status:r.status,stdout_hex:r.stdout.toString('hex'),stderr_hex:r.stderr.toString('hex')});
function okay(r){assert.equal(r.status,0,r.stderr.toString());return r;}
function execute(target,text,name,probe=false){
 const file=b+'/'+name+(target==='c'?'.c':'.py');fs.writeFileSync(file,text);
 let compiled,got;
 if(target==='c'){
  compiled=okay(run('gcc',['-std=gnu11','-O1','-Werror=discarded-qualifiers','-fsanitize=undefined','-fno-sanitize-recover=all',file,'-o',b+'/out']));got=run(b+'/out');
 }else{
  compiled=okay(run('python3',['-m','py_compile',file]));
  got=probe?run('python3',['-c',`import runpy,sys
m=runpy.run_path(sys.argv[1])
p=m['g0']
if type(p) is not bytes: sys.exit(77)
try: p[0]=1
except TypeError: sys.exit(0)
sys.exit(78)`,file]):run('python3',[file]);
 }
 return {compile_status:compiled.status,executed:true,actual:obs(got),sha256:hash(text)};
}
const src=Buffer.from('text t "A\\n\\"\\\\\\tB"\nfn main to int\nw = write 1 t 0 len t\nret int w\nend\n');
fs.writeFileSync(b+'/input.om',src);
const native=okay(run('build/bootstrap/omc',[],src));fs.writeFileSync(b+'/native',native.stdout,{mode:0o700});
const expected=obs(run(b+'/native'));assert.deepEqual(expected,{status:6,stdout_hex:'410a225c0942',stderr_hex:''});
const original=fs.readFileSync('src/toc.om','utf8'),rows=[];
for(const [name,old,replacement] of [
 ['decoded-byte','put textbuf u b','put textbuf u xor b uchar 1'],
 ['decoded-length','put g_len i sub get textuse 0 get g_pos i','put g_len i sub sub get textuse 0 get g_pos i 1'],
 ['escape-decoding','b = uchar 10','b = uchar 13'],
]){
 assert.ok(original.includes(old));const source=original.replace(old,replacement);assert.notEqual(source,original);
 const compiled=okay(run('build/bootstrap/omc',[],Buffer.from(source)));const emitter=b+'/'+name;fs.writeFileSync(emitter,compiled.stdout,{mode:0o700});
 okay(run('tools/verify-elf.sh',[emitter]));
 for(const target of ['c','python']){
  const emitted=okay(run(emitter,[],Buffer.concat([Buffer.from(target==='c'?'C':'P'),src])));
  const result=execute(target,emitted.stdout,name+'-'+target);
  assert.notDeepEqual(result.actual,expected,'mutant must execute and differ');
  // These deliberately valid changes preserve the program's ordinary exit path.
  assert.equal(result.actual.status,name==='decoded-length'?5:6);assert.equal(result.actual.stderr_hex,'');
  rows.push({name,target,mutant_source_sha256:hash(source),mutant_emitter_sha256:hash(compiled.stdout),emitter_compile_status:0,expected,...result,caught:true});
 }
}
for(const target of ['c','python']){
 const emitted=okay(run('tools/bridge',[target,b+'/input.om'])).stdout.toString();
 let text=emitted;
 if(target==='c')text='#define OMEGA_LIBRARY\n'+text+'\nint main(void){return _Generic(&g0[0],const uint8_t*:0,default:77);}\n';
 const baseline=execute(target,text,'readonly-good-'+target,true);assert.equal(baseline.actual.status,0);assert.equal(baseline.actual.stderr_hex,'');
 const old=target==='c'?'static const uint8_t g0':'g0=bytes((',replacement=target==='c'?'static uint8_t g0':'g0=bytearray((';assert.ok(text.includes(old));
 const mutant=text.replace(old,replacement),result=execute(target,mutant,'readonly-mutant-'+target,true);
 assert.equal(result.actual.status,77);assert.equal(result.actual.stderr_hex,'');
 rows.push({name:'immutable-storage',target,expected:baseline.actual,...result,caught:true});
}
// Const propagation changed shared view signatures. Qualify real host callers too.
const library='fn pick a view uchar 4 to uchar\nret get a 2\nend\n';fs.writeFileSync(b+'/library.om',library);
for(const target of ['c','python']){
 const emitted=okay(run('tools/bridge',[target,b+'/library.om'])).stdout;
 const module=b+'/library.'+(target==='c'?'c':'py');fs.writeFileSync(module,emitted);
 let code;
 if(target==='c')code='#include "library.c"\nint main(void){static const uint8_t a[]={1,0,255,4};uint64_t out=99;if(omega_pick(&out,a,4)||out!=255)return 1;if(omega_pick(&out,a,3)!=8)return 2;return omega_pick(&out,a,4);}\n';
 else code='from library import omega_pick\na=bytearray([1,0,255,4])\nassert omega_pick(a,4)==(0,255)\nassert omega_pick(a,3)==(8,None)\nassert omega_pick(a,4)==(0,255)\nassert a==bytearray([1,0,255,4])\n';
 const result=execute(target,code,'caller-'+target);assert.deepEqual(result.actual,{status:0,stdout_hex:'',stderr_hex:''});rows.push({name:'readonly-library-caller',target,...result,ok:true});
}
const report={requested:10,executed:rows.length,valid_compiled_mutants:rows.filter(r=>r.caught).length,library_callers:rows.filter(r=>r.ok).length,failed:0,rows};assert.equal(report.executed,report.requested);
fs.writeFileSync('evidence/text-native/controls.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({...report,rows:undefined}));
