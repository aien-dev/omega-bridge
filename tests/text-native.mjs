// L551 test infrastructure: byte fixture generation and actual native/C/Python oracles.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const root=process.cwd(),b=root+'/build/text-native';fs.mkdirSync(b,{recursive:true});
const hash=x=>createHash('sha256').update(x).digest('hex');
function run(exe,args=[],input){const r=spawnSync(exe,args,{input,timeout:20000,maxBuffer:16*1024*1024});assert.ifError(r.error);assert.equal(r.signal,null);return r;}
const obs=r=>({status:r.status,stdout_hex:r.stdout.toString('hex'),stderr_hex:r.stderr.toString('hex')});
const rows=[],cases=[];
const base=JSON.parse(fs.readFileSync('evidence/text-native/parent-baseline.json'));
assert.equal(hash(fs.readFileSync('build/bootstrap/omc')),base.seed_sha256);
for(const r of base.cases)cases.push({name:'parent-'+r.name,src:Buffer.from(r.source),error:r.native_compile_rc||undefined,out:r.expected_stdout_hex,status:0});
const lit=data=>Buffer.concat([Buffer.from('"'),...Array.from(data,v=>({10:Buffer.from('\\n'),9:Buffer.from('\\t'),34:Buffer.from('\\"'),92:Buffer.from('\\\\')})[v]||Buffer.from([v])),Buffer.from('"')]);
const prog=(data,body='w = write 1 t 0 len t\nret 0',prefix=Buffer.alloc(0))=>Buffer.concat([prefix,Buffer.from('text t '),lit(data),Buffer.from('\nfn main to int\n'+body+'\nend\n')]);
function positive(name,src,out='',status=0,error){cases.push({name,src:Buffer.from(src),out:Buffer.isBuffer(out)?out.toString('hex'):Buffer.from(out).toString('hex'),status,error});}
positive('all-256-bytes',prog(Buffer.from(Array.from({length:256},(_,i)=>i))),Buffer.from(Array.from({length:256},(_,i)=>i)));
for(let i=0;i<256;i++)positive('byte-'+i,prog(Buffer.from([i])),Buffer.from([i]));
positive('raw-cr-tab',Buffer.concat([Buffer.from('text t "A'),Buffer.from([13,9]),Buffer.from('Z"\nfn main to int\nw = write 1 t 0 len t\nret int len t\nend\n')]),Buffer.from([65,13,9,90]),4);
positive('target-injection',prog(Buffer.from('"; _os._exit(99) # \\xFA0123\n*/ int main(){return 99;}')),Buffer.from('"; _os._exit(99) # \\xFA0123\n*/ int main(){return 99;}'));
positive('read-only-view', 'text t "A\\nB"\nfn pass a view uchar 3 to long\nret write 1 a 0 len a\nend\nfn main to int\nn = pass t\nret int n\nend\n','A\nB',3);
positive('view-forward', 'text t "A\\tB"\nfn pass a view uchar 3 to uchar\nret get a 1\nend\nfn more a view uchar 3 to uchar\nret pass a\nend\nfn main to int\nret int more t\nend\n','',9);
positive('empty-view', 'text t ""\nfn size a view uchar 0 to ulong\nret len a\nend\nfn main to int\nret int size t\nend\n','',0,8);cases.at(-1).nativeError=8;
positive('prefix-names', 'text abc "A"\ntext abcdefgh "B"\ntext ab "C"\nfn main to int\nw = write 1 abc 0 len abc\nw = write 1 abcdefgh 0 len abcdefgh\nw = write 1 ab 0 len ab\nret 0\nend\n','ABC');
positive('texts-after-function', 'text t "A"\nfn main to int\nw = write 1 t 0 len t\nret 0\nend\ntext last "B"\n','A');
positive('texts-and-globals', 'text t "A"\nglobal g uchar 1\ntext u "B"\nfn main to int\nput g 0 get u 0\nw = write 1 t 0 1\nw = write 1 g 0 1\nret 0\nend\n','AB');
for(const n of [8,9])positive('combined-table-'+n,Array.from({length:n},(_,i)=>i%2?`global g${i} uchar 1\n`:`text t${i} "${i}"\n`).join('')+'fn main to int\nret 0\nend\n','',0,n===9?14:undefined);
for(const n of [32768,32769])positive('pool-'+n,prog(Buffer.alloc(n,65),'ret int len t'),'',n%256,n===32769?14:undefined);
positive('shared-pool-limit',Buffer.concat([Buffer.from('text a '),lit(Buffer.alloc(16384,65)),Buffer.from('\ntext t '),lit(Buffer.alloc(16385,66)),Buffer.from('\nfn main to int\nret 0\nend\n')]),'',0,14);
positive('dynamic-last',prog(Buffer.from([0,255]),'i = ulong 1\nret int get t i'),'',255);
positive('dynamic-bounds',prog(Buffer.from('AB'),'i = ulong 2\nret int get t i'),'',103);
positive('empty-bounds',prog(Buffer.alloc(0),'i = ulong 0\nret int get t i'),'',103);
positive('write-slice',prog(Buffer.from([1,0,255,2]),'w = write 1 t 1 2\nret int w'),Buffer.from([0,255]),2);
positive('empty-write-at-end',prog(Buffer.from('ABC'),'w = write 1 t len t 0\nret int w'));
positive('write-bounds',prog(Buffer.from('AB'),'w = write 1 t 1 2\nret 0'),'',103);
positive('write-overflow',prog(Buffer.from('AB'),'w = write 1 t ulong 18446744073709551615 2\nret 0'),'',103);
positive('stderr-bytes',prog(Buffer.from('ABC'),'w = write 2 t 0 len t\nret 0'));cases.at(-1).errout='414243';
positive('bad-fd',prog(Buffer.from('ABC'),'w = write int -1 t 0 len t\nret int neg w'),'',9);
for(const r of JSON.parse(fs.readFileSync('tests/text-promoted.json')))positive(r.name,r.source,r.name==='inherited_text_program'?Buffer.from('a\tb\\c"d\ne'):Buffer.alloc(0),r.name==='inherited_text_program'?204:0);
// The existing native developer fixture becomes an actual conversion case.
positive('NATIVE-developer-fixture','text msg "NATIVE\\n"\nfn main to int\nw = write 1 msg 0 len msg\nret 23\nend\n','NATIVE\n',23);
const refusals=[
 ['escape-zero','text t "\\0"\n',22],['escape-hex','text t "\\x41"\n',22],['escape-cr','text t "\\r"\n',22],
 ['quote-adjacent','text t "ab"x\n',22],['quote-backslash-eof','text t "ab\\',22],['quote-eof','text t "ab',22],
 ['duplicate','text t "a"\ntext t "b"\n',10],['global-collision','global t uchar 1\ntext t "b"\n',10],
 ['long-name','text abcdefghi "a"\n',13],['missing-literal','text t abc\n',16],['raw-lf','text t "a\nb"\n',22],
 ['outside-zero',Buffer.from([0]),16],['outside-control',Buffer.from([1]),16],['after-quote-control',Buffer.concat([Buffer.from('text t "a"'),Buffer.from([1]),Buffer.from('\n')]),16],
];
for(const [name,prefix,code] of refusals)cases.push({name,src:Buffer.concat([Buffer.from(prefix),Buffer.from('fn main to int\nret 0\nend\n')]),error:code,nativeError:code});
for(const [name,body,code] of [
 ['readonly-put','put t 0 1',20],['readonly-read','n = read 0 t 0 1',20],['readonly-edit','touch t',20],
 ['constant-bounds','x = get t 2',21],['inline-get','x = get "ab" 0',16],['inline-write','x = write 1 "ab" 0 2',16]
])cases.push({name,src:Buffer.from('text t "ab"\nfn touch a edit uchar 2 to void\nend\nfn main to int\n'+body+'\nret 0\nend\n'),error:code,nativeError:code});
// Every source-byte prefix: exercise escaped quotes, raw zero and mid-escape EOF.
const trunc=prog(Buffer.from([65,0,34,92,10,255]));
for(let i=0;i<=trunc.length;i++)cases.push({name:'prefix-'+i,src:trunc.subarray(0,i),probe:true});
positive('note-quote',prog(Buffer.from('A'), 'w = write 1 t 0 len t\nret 0',Buffer.from('note unmatched " and \\q\n')),'A');
positive('note-raw-zero',prog(Buffer.from('A'),'ret 0',Buffer.from([110,111,116,101,32,0,255,10])));
if(process.env.TEXT_BASELINE_ONLY)cases.splice(base.cases.length);
const requested=cases.length*2;
for(const c of cases){
 const native=run('build/bootstrap/omc',[],c.src),n=obs(native);
 let expected;
 if(native.status===0){fs.writeFileSync(b+'/native',native.stdout,{mode:0o700});expected=obs(run(b+'/native'));}
 for(const target of ['c','python']){
  const row={case:c.name,target,source_sha256:hash(c.src),native_compile:n.status};
  try{
   if(c.nativeError!==undefined)assert.equal(native.status,c.nativeError,'native refusal code');
   if(!c.probe&&!c.nativeError&&!c.name.startsWith('parent-'))assert.equal(native.status,0,native.stderr.toString());
   if(c.name.startsWith('parent-'))assert.equal(native.status,c.error||0);
   fs.writeFileSync(b+'/input.om',c.src);
   const p=process.env.TEXT_PARENT_EMITTER ? (native.status ? native : run(process.env.TEXT_PARENT_EMITTER,[],Buffer.concat([Buffer.from(target==='c'?'C':'P'),c.src]))) : run('tools/bridge',[target,b+'/input.om']);row.convert=obs(p);
   const refusal=native.status||c.error;
   if(refusal){assert.equal(p.status,refusal,p.stderr.toString());assert.equal(p.stdout.length,0);assert.ok(p.stderr.includes(Buffer.from('error '+refusal)));}
   else{
    assert.equal(p.status,0,p.stderr.toString());assert.ok(p.stdout.length);
    const file=b+'/emitted.'+(target==='c'?'c':'py');fs.writeFileSync(file,p.stdout);row.output_sha256=hash(p.stdout);
    let got;
    if(target==='c'){
     const cc=run('gcc',['-std=gnu11','-O1','-Werror=discarded-qualifiers','-fsanitize=undefined','-fno-sanitize-recover=all',file,'-o',b+'/emitted']);assert.equal(cc.status,0,cc.stderr.toString());got=run(b+'/emitted');
    }else got=run('python3',[file]);
    row.native=expected;row.actual=obs(got);assert.deepEqual(row.actual,expected);
    if(!c.probe){assert.equal(expected.status,c.status);assert.equal(expected.stdout_hex,c.out);assert.equal(expected.stderr_hex,c.errout||'');}
   }
   row.ok=true;
  }catch(e){row.ok=false;row.error=e.message;console.log('FAIL',c.name,target,e.message.slice(0,180));}
  rows.push(row);
 }
}
const report={requested,executed:rows.length,passed:rows.filter(r=>r.ok).length,failed:rows.filter(r=>!r.ok).length,source_cases:cases.length,rows};
assert.equal(report.requested,report.executed);
fs.writeFileSync(process.env.TEXT_REPORT||'evidence/text-native/differential.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({...report,rows:undefined}));process.exitCode=report.failed?1:0;
