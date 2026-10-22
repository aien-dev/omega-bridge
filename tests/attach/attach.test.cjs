// SPDX-License-Identifier: AGPL-3.0-only
// Tests use Node only as a host test harness. Shipping binaries need no Node/Python.
const {test, after} = require('node:test');
const a = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const cp = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const bin = process.env.ATTACH_BINARY || path.join(root, 'build/attach-test/omega');
const prod = path.join(root, 'build/attach/omega');
const homes = [];
function fixture() {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'omega attach ')); homes.push(home);
  const tools = path.join(home, 'tools with spaces'); fs.mkdirSync(tools);
  const env = {HOME:home, PATH:tools, OMEGA_ATTACH_INTERVAL_MS:'150', OMEGA_ATTACH_DEBOUNCE_MS:'50'};
  return {home, tools, env, state:path.join(home,'.local/state/omega-attach')};
}
function run(f, args, opt={}) {
  const r = cp.spawnSync(opt.bin || bin, args, {env:f.env, cwd:opt.cwd || '/', encoding:'utf8', timeout:15000});
  if (opt.fail) { a.notEqual(r.status,0, r.stdout+r.stderr); return r; }
  a.equal(r.status,0, r.error?.message || r.stdout+r.stderr); return r.stdout;
}
function json(f,args=['discover'],opt) {return JSON.parse(run(f,args,opt));}
function script(p,text) {fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,'#!/bin/sh\n'+text+'\n',{mode:0o755});}
function tool(f,name,body='echo "runtime 3.12.1"') {const p=path.join(f.tools,name);script(p,body);return p;}
function snap(dir) {
 const out={}; if(!fs.existsSync(dir))return out;
 for(const n of fs.readdirSync(dir).sort()) {const p=path.join(dir,n),s=fs.lstatSync(p);out[n]=s.isDirectory()?['dir',s.mode&511,snap(p)]:s.isSymbolicLink()?['link',fs.readlinkSync(p)]:['file',s.mode&511,fs.readFileSync(p).toString('base64')];}return out;
}
async function until(fn) {let last;const end=Date.now()+7000;while(Date.now()<end){try {if(fn())return;}catch(e){last=e;}await new Promise(r=>setTimeout(r,60));}throw last||new Error('watcher did not converge');}
const inv = j=>j.inventory;
function fixtureRuntime(f) {
 return tool(f,'omega-fixture',`case "$1" in
 --version) echo 'omega-fixture 1.0';;
 --omega-attach-probe-v1) echo 'OMEGA_ATTACH_FIXTURE_V1 native 1';;
 --run) active=0; for h in "$HOME"/.local/state/omega-attach/hooks/*; do [ -f "$h" ] && active=1; done; if [ "$active" = 1 ]; then echo OMEGA_FIXTURE_ACTIVE; else echo ORIGINAL; fi;;
 *) exit 4;; esac`);
}
after(()=>{for(const home of homes){try{cp.spawnSync(bin,['disable'],{env:{HOME:home,PATH:'/nonexistent'},timeout:5000});}catch{}fs.rmSync(home,{recursive:true,force:true});}});

test('arbitrary cwd, read-only discovery, aliases and hardlinks deduplicated',()=>{
 const f=fixture(),p=tool(f,'python3');fs.symlinkSync(p,path.join(f.tools,'python'));fs.linkSync(p,path.join(f.tools,'python3.12'));
 const before=snap(f.home),j=json(f);a.equal(inv(j).length,1);a.equal(inv(j)[0].aliases.length,3);a.equal(inv(j)[0].detection,'DETECTED');a.equal(inv(j)[0].state,'UNSUPPORTED');a.match(inv(j)[0].reason,/verified.*hook/);a.equal(j.converter,'NOT_AVAILABLE');a.deepEqual(snap(f.home),before);
});
test('empty and relative PATH components are skipped, never cwd executables',()=>{const f=fixture();tool(f,'python3');f.env.PATH='.:relative::'+f.tools;const j=json(f, ['discover'],{cwd:f.home});a.equal(inv(j).length,1);a.ok(j.warnings.some(x=>/relative PATH/.test(x)));});
test('manager inventories, venv identity, spaces and manager symlinks',()=>{
 const f=fixture(),p=tool(f,'python3'); const managers=[['.pyenv/versions/3.12/bin/python3','python'],['.nvm/versions/node/v22/bin/node','node'],['.rustup/toolchains/stable/bin/rustc','rust'],['go/bin/go','go'],['.sdkman/candidates/java/21/bin/java','jvm'],['.dotnet/dotnet','dotnet'],['.rbenv/versions/3/bin/ruby','ruby'],['.asdf/installs/php/8/bin/php','php'],['.local/share/mise/installs/lua/5/bin/lua','lua'],['miniconda3/envs/demo/bin/python','python']];
 for(const [n] of managers)script(path.join(f.home,n),'echo "runtime 3.12.1"');
 const v=path.join(f.home,'venv space');fs.mkdirSync(path.join(v,'bin'),{recursive:true});fs.symlinkSync(p,path.join(v,'bin/python'));f.env.VIRTUAL_ENV=v;
 const j=json(f); for(const [,lang] of managers)a.ok(inv(j).some(x=>x.language===lang),lang);a.equal(inv(j).filter(x=>x.language==='python').length,4);a.ok(inv(j).some(x=>x.environment===v));
});
test('all registry families discovered; unrelated commands never executed',()=>{
 const f=fixture();for(const n of ['python3','node','rustc','go','java','dotnet','ruby','php','gcc','g++','clang','swift','julia','lua','perl','R','zig','elixir','erl','ghc','ocaml','dart','deno','bun'])tool(f,n);tool(f,'definitely-not-a-runtime','exit 98');a.equal(new Set(inv(json(f)).map(x=>x.language)).size,23);
});
test('broken, hanging, oversized and versionless probes are ERROR, never attached',()=>{
 const f=fixture();tool(f,'python3','exit 4');tool(f,'node','while :; do :; done');tool(f,'ruby','echo unknown');tool(f,'go','i=0; while [ "$i" -lt 5000 ]; do printf x; i=$((i+1)); done');
 const t=Date.now(),j=json(f);a.ok(Date.now()-t<6000);a.equal(inv(j).length,4);a.ok(inv(j).every(x=>x.state==='ERROR'));a.ok(!fs.existsSync(f.state));
});
test('no privileges, no network, unsupported enrollment changes no foreign config',()=>{
 const f=fixture();tool(f,'python3');fs.writeFileSync(path.join(f.home,'.profile'),'untouched\n',{mode:0o640});fs.mkdirSync(path.join(f.home,'.config'));fs.writeFileSync(path.join(f.home,'.config/user.conf'),'foreign\n');
 const before=snap(f.home);const j=json(f,['attach']);a.equal(j.enrolled,true);a.equal(j.watcher,'RUNNING');a.equal(inv(j)[0].state,'UNSUPPORTED');a.ok(!fs.existsSync(path.join(f.state,'hooks'))||fs.readdirSync(path.join(f.state,'hooks')).length===0);run(f,['uninstall']);a.deepEqual(snap(f.home),before);
});
test('watcher detects added and removed installations without rerunning attach',async()=>{
 const f=fixture();json(f,['attach']);const p=tool(f,'node');await until(()=>inv(json(f,['status'])).some(x=>x.language==='node'));fs.unlinkSync(p);await until(()=>inv(json(f,['status'])).length===0);run(f,['disable']);a.equal(json(f,['status']).watcher,'STOPPED');
});
test('watcher notices a newly created manager tree and invalidates executable version cache',async()=>{
 const f=fixture();json(f,['attach']);const p=path.join(f.home,'.nvm/versions/node/v25/bin/node');script(p,'echo "node v25.0.0"');await until(()=>inv(json(f,['status'])).some(x=>x.version.includes('25.0.0')));script(p,'echo "node v25.1.0"');await until(()=>inv(json(f,['status'])).some(x=>x.version.includes('25.1.0')));run(f,['notify']);run(f,['disable']);
});
test('repeated enrollment, disable, enable and uninstall are reversible and idempotent',()=>{
 const f=fixture();tool(f,'gcc');const before=snap(f.home);json(f,['attach']);const desktop=fs.readFileSync(path.join(f.home,'.config/autostart/omega-attach.desktop'),'utf8');a.match(desktop,/\[Desktop Entry\]/);const s1=json(f,['status']);json(f,['attach']);a.equal(json(f,['status']).watcher_pid,s1.watcher_pid);run(f,['disable']);a.equal(json(f,['status']).enabled,false);run(f,['enable']);a.equal(json(f,['status']).watcher,'RUNNING');run(f,['uninstall']);run(f,['uninstall']);a.deepEqual(snap(f.home),before);
});
test('fixture handshake gates SUPPORTED and actual reversible fixture integration',async()=>{
 const f=fixture(),p=fixtureRuntime(f);a.equal(inv(json(f))[0].state,'SUPPORTED');a.equal(cp.spawnSync(p,['--run'],{env:f.env,encoding:'utf8'}).stdout.trim(),'ORIGINAL');a.equal(inv(json(f,['attach']))[0].state,'ATTACHED');a.equal(cp.spawnSync(p,['--run'],{env:f.env,encoding:'utf8'}).stdout.trim(),'OMEGA_FIXTURE_ACTIVE');run(f,['disable']);a.equal(cp.spawnSync(p,['--run'],{env:f.env,encoding:'utf8'}).stdout.trim(),'ORIGINAL');run(f,['enable']);a.equal(inv(json(f,['status']))[0].state,'ATTACHED');fs.unlinkSync(p);await until(()=>inv(json(f,['status'])).length===0);a.equal(fs.readdirSync(path.join(f.state,'hooks')).length,0);
});
test('new supported fixture installs attach automatically after enrollment',async()=>{
 const f=fixture();json(f,['attach']);fixtureRuntime(f);await until(()=>inv(json(f,['status'])).some(x=>x.state==='ATTACHED'));run(f,['uninstall']);
});
test('incompatible fixture ABI is refused without any hooks',()=>{const f=fixture();tool(f,'omega-fixture','case "$1" in --version) echo "fixture 2.0";; *) echo "OMEGA_ATTACH_FIXTURE_V2 alien 2";; esac');a.equal(inv(json(f))[0].state,'UNSUPPORTED');json(f,['attach']);a.equal(fs.readdirSync(path.join(f.state,'hooks')).length,0);run(f,['uninstall']);});
test('attachment write failure rolls back enrollment and owned hook completely',()=>{
 const f=fixture();fixtureRuntime(f);const before=snap(f.home);f.env.OMEGA_ATTACH_FAIL='hook';run(f,['attach'],{fail:true});a.deepEqual(snap(f.home),before);
});
test('preexisting desktop entry refuses enrollment and is never overwritten',()=>{const f=fixture();const p=path.join(f.home,'.config/autostart/omega-attach.desktop');fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,'foreign');const before=snap(f.home);run(f,['attach'],{fail:true});a.deepEqual(snap(f.home),before);});
test('symlinked writable state parent refuses without touching external destination',()=>{const f=fixture(),other=fs.mkdtempSync(path.join(os.tmpdir(),'omega outside '));homes.push(other);fs.mkdirSync(path.join(f.home,'.local'));fs.symlinkSync(other,path.join(f.home,'.local/state'));const before=snap(f.home);run(f,['attach'],{fail:true});a.deepEqual(snap(other),{});a.deepEqual(snap(f.home),before);});
test('bootstrap and uninstall restore exact prior filesystem, even from spaces',()=>{const f=fixture();const before=snap(f.home);run(f,['bootstrap']);const installed=path.join(f.home,'.local/bin/omega');a.ok(fs.lstatSync(installed).isSymbolicLink());json(f,['attach'],{bin:installed});run(f,['uninstall'],{bin:installed});a.deepEqual(snap(f.home),before);});
test('existing omega anywhere on PATH blocks bootstrap without overwrites',()=>{const f=fixture();tool(f,'omega','echo original');const before=snap(f.home);run(f,['bootstrap'],{fail:true});a.deepEqual(snap(f.home),before);});
test('bootstrap rollback restores exact filesystem',()=>{const f=fixture();const before=snap(f.home);f.env.OMEGA_ATTACH_FAIL='bootstrap';run(f,['bootstrap'],{fail:true});a.deepEqual(snap(f.home),before);});
test('modified owned desktop entry is preserved and uninstall refuses',()=>{const f=fixture();json(f,['attach']);run(f,['disable']);const p=path.join(f.home,'.config/autostart/omega-attach.desktop');fs.writeFileSync(p,'user changed');run(f,['uninstall'],{fail:true});a.equal(fs.readFileSync(p,'utf8'),'user changed');});
test('production build excludes fixture integration entirely',()=>{const f=fixture();fixtureRuntime(f);a.equal(inv(json(f,['discover'],{bin:prod})).length,0);});
test('missing native Omega policy fails closed without any enrollment',()=>{const f=fixture();const isolated=path.join(f.home,'omega');fs.copyFileSync(bin,isolated);fs.chmodSync(isolated,0o755);tool(f,'gcc');const before=snap(f.home);run(f,['attach'],{bin:isolated,fail:true});a.deepEqual(snap(f.home),before);});
