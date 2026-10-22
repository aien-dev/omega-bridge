#!/usr/bin/env python3
"""Independent review regression: standard-version names and CR line endings."""
from pathlib import Path
import json,os,struct,subprocess
R=Path(__file__).resolve().parents[2]
O=Path(os.environ.get('CUDA_CPP_REVIEW_OUT',R/'build/cuda-cpp-review-tests'));O.mkdir(parents=True,exist_ok=True)
rows=[]
def run(args,data=b''):
    return subprocess.run(list(map(str,args)),input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
def record(name,ok,**kw):rows.append({'name':name,'pass':bool(ok),**kw})
base=(R/'tests/cuda-cpp/vector.cu').read_bytes()
variants=[('CR-only',base.replace(b'\n',b'\r')),('mixed-CR',base.replace(b'unsigned int index =',b'// line comment\r    unsigned int index ='))]
for keyword in ['concept','requires','consteval','constinit','co_await','co_return','co_yield']:
    for role in ['vector_add','out','left','count','index']:
        variants.append((keyword+'-'+role,base.replace(role.encode(),keyword.encode())))
shim=b'#define __global__\nstruct Dim { unsigned int x; };\nDim blockIdx,blockDim,threadIdx;\n'
data=struct.pack('<'+'I'*12,2,2,3,100,101,102,1,0xffffffff,3,4,2,5)
expected=struct.pack('<III',5,1,8)
for j,(label,source) in enumerate(variants):
    p=run(['g++','-std=c++17','-x','c++','-fsyntax-only','-'],shim+source)
    record(label+' independently valid C++17',p.returncode==0,rc=p.returncode,stderr=p.stderr.decode())
    p=run([R/'build/native/cuda-cpp'],source)
    record(label+' frontend accepts',p.returncode==0 and p.stdout,rc=p.returncode,stderr=p.stderr.decode())
    if p.returncode!=0:continue
    q=run([R/'build/bootstrap/omc'],p.stdout)
    record(label+' native compile',q.returncode==0 and q.stdout,rc=q.returncode,stderr=q.stderr.decode())
    if q.returncode!=0:continue
    exe=O/(str(j)+'.native');exe.write_bytes(q.stdout);exe.chmod(0o700)
    p=run([R/'tools/verify-elf.sh',exe]);record(label+' qualified ELF',p.returncode==0)
    if p.returncode!=0:continue
    p=run([exe],data);record(label+' expected unsigned32 output',p.returncode==0 and p.stdout==expected and not p.stderr,rc=p.returncode)
(O/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
summary={'variants':len(variants),'checks':len(rows),'passed':sum(r['pass'] for r in rows),'failed':sum(not r['pass'] for r in rows)}
print(json.dumps(summary))
raise SystemExit(bool(summary['failed']))
