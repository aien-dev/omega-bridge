// Node is test infrastructure only. Every installation is confined to /tmp.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const repo=process.cwd(), scratch=fs.mkdtempSync('/tmp/omega-commands-test-');
const home=path.join(scratch,'home'), cwd=path.join(scratch,'unrelated');
fs.mkdirSync(home);fs.mkdirSync(cwd);
const env={...process.env,HOME:home,LC_ALL:'C'};
delete env.OMEGA_SEED;delete env.OMEGA_SOURCE;
const results=[];
function run(exe,args=[],input='',extra={}) {
 const r=spawnSync(exe,args,{cwd,env,input,encoding:'utf8',timeout:120000,maxBuffer:16*1024*1024,...extra});
 assert.ifError(r.error); assert.equal(r.signal,null,`${exe}: signal ${r.signal}`);return r;
}
function check(name,fn){fn();results.push({name,ok:true});console.log('PASS '+name);}
function eq(r,status,stdout){assert.equal(r.status,status,r.stderr);if(stdout!==undefined)assert.equal(r.stdout,stdout);return r;}
const install=(prefix,extra={})=>run(repo+'/tools/install.sh',['--offline','--prefix',prefix],'',extra);
const prefix=path.join(home,"my prefix's"),om=prefix+'/bin/om',omg=prefix+'/bin/omg',payload=prefix+'/lib/omega-native';
const invoke=(args,input='')=>run(om,args,input);
check('required interfaces',()=>{for(const p of ['tools/install.sh','tools/uninstall.sh','tools/om','provenance/sources.sha256'])assert.ok(fs.existsSync(repo+'/'+p));});
check('isolated source-only installation from unrelated cwd',()=>eq(install(prefix),0));
check('aliases target exactly the same implementation',()=>assert.equal(fs.realpathSync(om),fs.realpathSync(omg)));
check('exact source pins',()=>eq(invoke(['version']),0,fs.readFileSync(repo+'/provenance/pins','utf8')));
check('full help names bounds and shell boundary',()=>{let r=eq(invoke(['help']),0);for(const s of ['128 decimal','degree <=16','POSIX shell','65536','REFUSED 9'])assert.ok(r.stdout.includes(s));});
for(const args of [['help'],['version'],['math','diff (x+1)^5'],['math','eval 1/0'],['wrong'],['status'],['math','eval 1','extra']])check('alias identity '+args.join(' '),()=>{
 const a=invoke(args),b=run(omg,args);assert.deepEqual([a.status,a.stdout,a.stderr],[b.status,b.stdout,b.stderr]);
});
const cases=JSON.parse(fs.readFileSync(repo+'/seed/math/cases.json'));
check('all frozen math vectors through installed streaming command',()=>eq(invoke(['math'],cases.map(c=>c[0]).join('\n')+'\n'),0,cases.map(c=>c[1]).join('\n')+'\n'));
check('one-shot exact differentiation',()=>eq(invoke(['math','diff (x+1)^5']),0,'OK 5+20*x+30*x^2+20*x^3+5*x^4\n'));
for(let i=1;i<=8;i++){
 const c=cases.find(c=>c[1]==='REFUSED '+i);if(c)check('one-shot refusal '+i,()=>eq(invoke(['math',c[0]]),65,c[1]+'\n'));
}
check('stream refusal and recovery preserve native semantics',()=>eq(invoke(['math'],'eval 1/0\neval 7/9\n'),0,'REFUSED 2\nOK 7/9\n'));
check('stream empty EOF',()=>eq(invoke(['math']),0,''));
check('stream partial EOF',()=>eq(invoke(['math'],'eval 2+3'),0,'OK 5\n'));
check('oversize line recovery',()=>eq(invoke(['math'],'x'.repeat(5000)+'\neval 2\n'),0,'REFUSED 4\nOK 2\n'));
check('native transport failure propagated',()=>eq(invoke(['math'],'x'.repeat(65536)),1,'REFUSED 4\n'));
check('newline in one-shot rejected',()=>eq(invoke(['math','eval 1\neval 2']),64,''));
check('shell metacharacters never evaluated',()=>{eq(invoke(['math','eval $(touch OWNED)']),65);assert.ok(!fs.existsSync(cwd+'/OWNED'));});
for(const cmd of ['attach','discover','status'])check(cmd+' explicit unsupported',()=>{const r=eq(invoke([cmd]),69);assert.match(r.stdout,/UNSUPPORTED/);});
const input=cwd+'/- input $(touch OWNED).om';
fs.copyFileSync(repo+'/tests/fixtures/fib.om',input);
for(const target of ['c','python']){
 const output=cwd+'/- output '+target;
 const frozen=eq(run(repo+'/tools/bridge',[target,input]),0).stdout;
 check(target+' output matches frozen converter exactly',()=>eq(invoke(['convert','--to',target,'--',path.basename(input)]),0,frozen));
 check(target+' alias output identity',()=>eq(run(omg,['convert','--to',target,input]),0,frozen));
 check(target+' atomic output with spaces and leading dash',()=>{eq(invoke(['convert','--to',target,input,'-o',path.basename(output)]),0,'');assert.equal(fs.readFileSync(output,'utf8'),frozen);});
 check(target+' actual emitted target execution',()=>{
  const seed=run(payload+'/omc',[],fs.readFileSync(input),{encoding:null});assert.equal(seed.status,0);
  fs.writeFileSync(cwd+'/native',seed.stdout,{mode:0o700});const expected=run(cwd+'/native');
  let actual;
  if(target==='c'){eq(run('gcc',['-std=gnu11','-x','c',output,'-o',cwd+'/emitted']),0);actual=run(cwd+'/emitted');}
  else actual=run('python3',[output]);
  assert.deepEqual([actual.status,actual.stdout,actual.stderr],[expected.status,expected.stdout,expected.stderr]);
 });
}
check('source and destination may be the same file',()=>{const p=cwd+'/same.om';fs.copyFileSync(input,p);eq(invoke(['convert','--to','c',p,'-o',p]),0);assert.match(fs.readFileSync(p,'utf8'),/Emitted by Omega Bridge/);});
for(const [name,src] of [['syntax','fn main to int\nret bogus\nend\n'],['unsupported',fs.readFileSync(repo+'/tests/unsupported/text.om')],['include','include /etc/passwd\n'],['nul',Buffer.from([0,255])]])check('failed '+name+' conversion preserves existing output',()=>{
 const p=cwd+'/bad.om',o=cwd+'/preserved';fs.writeFileSync(p,src);fs.writeFileSync(o,'KEEP');fs.chmodSync(o,0o640);
 const before=fs.statSync(o);const r=eq(invoke(['convert','--to','c',p,'-o',o]),65,'');assert.ok(r.stderr);assert.equal(fs.readFileSync(o,'utf8'),'KEEP');assert.equal(fs.statSync(o).ino,before.ino);assert.equal(fs.statSync(o).mode,before.mode);
});
check('failed conversion creates no destination',()=>{eq(invoke(['convert','--to','python',cwd+'/bad.om','-o',cwd+'/absent']),65,'');assert.ok(!fs.existsSync(cwd+'/absent'));});
check('missing input deterministic',()=>{const a=eq(invoke(['convert','--to','c','missing']),66,'');assert.equal(a.stderr,'omega: input is not a readable regular file\n');});
check('unknown conversion target',()=>eq(invoke(['convert','--to','rust',input]),64,''));
check('output symlink protected',()=>{fs.writeFileSync(cwd+'/victim','KEEP');fs.symlinkSync(cwd+'/victim',cwd+'/link');eq(invoke(['convert','--to','c',input,'-o',cwd+'/link']),73,'');assert.equal(fs.readFileSync(cwd+'/victim','utf8'),'KEEP');});
check('output directory protected',()=>eq(invoke(['convert','--to','c',input,'-o',cwd]),73,''));
check('missing output parent publishes nothing',()=>eq(invoke(['convert','--to','c',input,'-o',cwd+'/none/out']),73,''));
check('temporary output files cleaned',()=>assert.ok(!fs.readdirSync(cwd).some(n=>n.startsWith('.omega-output.'))));
for(const name of ['om','omg'])check(name+' collision refuses before any prefix write',()=>{
 const p=home+'/collision-'+name;fs.mkdirSync(p+'/bin',{recursive:true});fs.writeFileSync(p+'/bin/'+name,'KEEP');
 eq(install(p),73);assert.deepEqual(fs.readdirSync(p),['bin']);assert.deepEqual(fs.readdirSync(p+'/bin'),[name]);assert.equal(fs.readFileSync(p+'/bin/'+name,'utf8'),'KEEP');
});
check('dangling alias collision',()=>{const p=home+'/dangling';fs.mkdirSync(p+'/bin',{recursive:true});fs.symlinkSync('/does-not-exist',p+'/bin/omg');eq(install(p),73);assert.equal(fs.readlinkSync(p+'/bin/omg'),'/does-not-exist');});
check('repeat installation preserves installed files',()=>eq(install(prefix),73));
check('rollback after second alias failure restores absent prefix',()=>{
 const bin=scratch+'/fault-bin';fs.mkdirSync(bin);fs.writeFileSync(bin+'/ln','#!/bin/sh\ncase "$3" in */omg) exit 71;; esac\nexec /usr/bin/ln "$@"\n',{mode:0o700});
 const p=home+'/rollback';eq(install(p,{env:{...env,PATH:bin+':'+env.PATH}}),71);assert.ok(!fs.existsSync(p));
});
check('rollback preserves existing empty directories and unrelated data',()=>{
 const p=home+'/rollback-existing';fs.mkdirSync(p+'/bin',{recursive:true});fs.mkdirSync(p+'/lib');fs.writeFileSync(p+'/keep','KEEP');
 eq(install(p,{env:{...env,PATH:scratch+'/fault-bin:'+env.PATH}}),71);assert.deepEqual(fs.readdirSync(p).sort(),['bin','keep','lib']);assert.deepEqual(fs.readdirSync(p+'/bin'),[]);assert.deepEqual(fs.readdirSync(p+'/lib'),[]);
});
check('changed file permissions prevent uninstall',()=>{const p=payload+'/HELP.txt',m=fs.statSync(p).mode;fs.chmodSync(p,0o644);eq(run(repo+'/tools/uninstall.sh',['--prefix',prefix]),65);assert.ok(fs.existsSync(om));fs.chmodSync(p,m);});
check('owned file replaced with equal-content symlink is preserved',()=>{const p=payload+'/HELP.txt',b=fs.readFileSync(p),m=fs.statSync(p).mode;fs.writeFileSync(cwd+'/help-copy',b);fs.unlinkSync(p);fs.symlinkSync(cwd+'/help-copy',p);eq(run(repo+'/tools/uninstall.sh',['--prefix',prefix]),65);assert.ok(fs.lstatSync(p).isSymbolicLink());fs.unlinkSync(p);fs.writeFileSync(p,b,{mode:m});});
check('changed owned file prevents uninstall',()=>{
 const p=payload+'/HELP.txt',b=fs.readFileSync(p);fs.appendFileSync(p,'USER CHANGE');eq(run(repo+'/tools/uninstall.sh',['--prefix',prefix]),65);assert.ok(fs.existsSync(om));fs.writeFileSync(p,b);
});
check('changed alias prevents uninstall',()=>{fs.unlinkSync(omg);fs.symlinkSync('user-command',omg);eq(run(repo+'/tools/uninstall.sh',['--prefix',prefix]),73);assert.equal(fs.readlinkSync(omg),'user-command');fs.unlinkSync(omg);fs.symlinkSync('../lib/omega-native/om',omg);});
check('missing native executable fails closed',()=>{fs.renameSync(payload+'/math',payload+'/math.saved');eq(invoke(['math','eval 1']),65,'');fs.renameSync(payload+'/math.saved',payload+'/math');});
check('tampered installed native executable fails closed',()=>{const p=payload+'/math',b=fs.readFileSync(p);fs.appendFileSync(p,'bad');eq(invoke(['math','eval 1']),65,'');fs.writeFileSync(p,b);});
check('ELF closure absent for all installed Omega executables',()=>{for(const n of ['omc','bridge','math']){
 const p=payload+'/'+n,b=fs.readFileSync(p);assert.equal(b.subarray(0,4).toString('hex'),'7f454c46');assert.equal(b.readUInt16LE(18),183);
 assert.doesNotMatch(eq(run('readelf',['-l',p]),0).stdout,/INTERP/);assert.doesNotMatch(eq(run('readelf',['-d',p]),0).stdout,/NEEDED/);
}});
check('traced installed math executes native component and no foreign engine',()=>{
 const trace=scratch+'/math.trace';eq(run('strace',['-f','-e','trace=execve','-o',trace,om,'math','eval 1/2']),0,'OK 1/2\n');const t=fs.readFileSync(trace,'utf8');assert.ok(t.includes(payload+'/math'));assert.doesNotMatch(t,/execve\("[^"\n]*\/(?:gcc|cc|clang|rustc|cargo|python3?|node|aien-calc)"/);fs.copyFileSync(trace,repo+'/evidence/native-commands/math-exec.trace');
});
check('traced conversion executes native checker then native converter',()=>{
 const trace=scratch+'/convert.trace';eq(run('strace',['-f','-e','trace=execve','-o',trace,om,'convert','--to','c',input]),0);const t=fs.readFileSync(trace,'utf8');assert.ok(t.includes(payload+'/omc'));assert.ok(t.includes(payload+'/bridge'));assert.doesNotMatch(t,/execve\("[^"\n]*\/(?:gcc|cc|clang|rustc|cargo|python3?|node|aien-calc)"/);fs.copyFileSync(trace,repo+'/evidence/native-commands/convert-exec.trace');
});
check('native math dispatch negative control is caught by output assertion',()=>{
 const p=payload+'/om',original=fs.readFileSync(p,'utf8'),manifest=fs.readFileSync(payload+'/files.sha256','utf8');
 assert.ok(original.includes('"$root/math" <'));
 fs.writeFileSync(p,original.replace('"$root/math" <','"$root/bridge" <'));
 const h=createHash('sha256').update(fs.readFileSync(p)).digest('hex');fs.writeFileSync(payload+'/files.sha256',manifest.replace(/^[a-f0-9]{64}  om$/m,h+'  om'));
 const r=invoke(['math','diff x^2']);assert.notDeepEqual([r.status,r.stdout],[0,'OK 2*x\n']);
 fs.writeFileSync(p,original);fs.writeFileSync(payload+'/files.sha256',manifest);eq(invoke(['math','diff x^2']),0,'OK 2*x\n');
});
check('uninstall from alias preserves unrelated files and user data',()=>{
 fs.writeFileSync(prefix+'/bin/user-command','KEEP');fs.writeFileSync(payload+'/user-data','DATA');fs.mkdirSync(home+'/.config');fs.writeFileSync(home+'/.config/user','USER');
 eq(run(omg,['uninstall']),0);assert.ok(!fs.existsSync(om));assert.ok(!fs.existsSync(omg));assert.equal(fs.readFileSync(payload+'/user-data','utf8'),'DATA');assert.equal(fs.readFileSync(prefix+'/bin/user-command','utf8'),'KEEP');assert.equal(fs.readFileSync(home+'/.config/user','utf8'),'USER');assert.deepEqual(fs.readdirSync(payload),['user-data']);
});
check('uninstall restores previously absent prefix',()=>{const p=home+'/remove-all';eq(install(p),0);eq(run(p+'/bin/om',['uninstall']),0);assert.ok(!fs.existsSync(p));});
check('uninstall preserves previously existing directories',()=>{const p=home+'/preserve-dirs';fs.mkdirSync(p+'/bin',{recursive:true});fs.mkdirSync(p+'/lib');eq(install(p),0);eq(run(p+'/bin/om',['uninstall']),0);assert.deepEqual(fs.readdirSync(p).sort(),['bin','lib']);});
fs.writeFileSync(repo+'/evidence/native-commands/commands.json',JSON.stringify({passed:results.length,results},null,2)+'\n');
console.log(`PASS ${results.length} native command integration checks`);
fs.rmSync(scratch,{recursive:true});
