#!/usr/bin/env python3
"""Test-only native compiler differential, syscall trace and mutation gate."""
from pathlib import Path
import hashlib,json,subprocess,sys,os
root=Path(__file__).resolve().parents[2]
parent=root/'build/bootstrap/omc'; candidate=Path(sys.argv[1]).resolve(); out=Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=False)
def run(args,**kw):return subprocess.run(list(map(str,args)),capture_output=True,timeout=60,**kw)
def require(ok,msg):
 if not ok: raise RuntimeError(msg)
source=(root/'src/device/omc.om').read_bytes()
manifest=[]
fixtures=sorted((root/'tests/fixtures').glob('*.om'))
require(bool(fixtures),'missing inherited fixtures')
for p in fixtures:
 data=p.read_bytes(); a=run([parent],input=data);b=run([candidate],input=data)
 require((a.returncode,a.stdout,a.stderr)==(b.returncode,b.stdout,b.stderr),'inherited compiler difference: '+p.name)
 manifest.append({'path':str(p.relative_to(root)),'sha256':hashlib.sha256(data).hexdigest(),'rc':a.returncode,'output_sha256':hashlib.sha256(a.stdout).hexdigest()})
(out/'inherited.json').write_text(json.dumps(manifest,indent=2)+'\n')
gate=root/'tests/device/gate.py'
p=run([sys.executable,gate,candidate,out/'normal'])
(out/'normal.log').write_bytes(p.stdout+p.stderr)
require(p.returncode==0,'normal device gate failed')
mutants=[
 ('close-syscall',b'emit 3531605800\nemit 3556769793',b'emit 3531609480\nemit 3556769793','open-close'),
 ('path-terminator',b'trapsite 3036676112 3',b'note mutant removed path terminator check','path-unterminated'),
 ('ioctl-size',b'trapc 1 3\nsave\nloadarg 0',b'note mutant removed exact ioctl length check\nsave\nloadarg 0','ioctl-short'),
]
mutrows=[]
for name,old,new,catch in mutants:
 require(source.count(old)==1,'nonunique mutant '+name)
 altered=source.replace(old,new);p=run([parent],input=altered)
 require(p.returncode==0 and p.stdout.startswith(b'\x7fELF'),'mutant failed to compile '+name)
 exe=out/name;exe.write_bytes(p.stdout);exe.chmod(0o700)
 p=run([sys.executable,gate,exe,out/(name+'-gate')])
 (out/(name+'.log')).write_bytes(p.stdout+p.stderr)
 rows=json.loads((out/(name+'-gate')/'receipt.json').read_text())['cases']
 caught=[r for r in rows if r['name']==catch]
 require(p.returncode==1 and len(caught)==1 and caught[0]['compile_rc']==0 and not caught[0]['passed'],'mutant not behaviorally caught '+name)
 mutrows.append({'name':name,'catch':caught[0],'sha256':hashlib.sha256(exe.read_bytes()).hexdigest()})
trace=out/'syscalls.trace'
p=run(['strace','-o',trace,'-e','trace=openat,close,ioctl,execve',out/'normal/open-close'],input=b'')
require(p.returncode==0,'syscall trace run failed')
t=trace.read_text(); require('openat(AT_FDCWD, "/dev/null", O_RDWR|O_CLOEXEC)' in t,'open flags or path differ')
require(t.count('execve(')==1,'unexpected subprocess in native device executable')
require(t.count('close(')==1,'unexpected close count')
receipt={'source_sha256':hashlib.sha256(source).hexdigest(),'parent_sha256':hashlib.sha256(parent.read_bytes()).hexdigest(),'candidate_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),'inherited_fixtures':len(manifest),'native_device':json.loads((out/'normal/receipt.json').read_text()),'mutants':mutrows,'syscall_trace':'syscalls.trace','gpu_executed':False}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'inherited_fixtures':len(manifest),'device_cases':receipt['native_device']['total'],'mutants_caught':len(mutrows),'status':'PASS'}))
