#!/usr/bin/env python3
import hashlib,json,os,struct,subprocess,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[2]
OUT=Path(os.environ.get('CUDA_CPP_COMMAND_OUT',R/'build/cuda-cpp-command-tests'))
OUT.mkdir(parents=True,exist_ok=True)
rows=[]
def call(args,data=b'',cwd=None):
    return subprocess.run(list(map(str,args)),input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=cwd,timeout=90)
def ck(ok,name,**extra):
    rows.append({'name':name,'pass':bool(ok),**extra})
    (OUT/'results.json').write_text(json.dumps(rows,indent=2))
    assert ok,(name,extra)
with tempfile.TemporaryDirectory(prefix='cuda-cpp-install-') as d:
    d=Path(d);prefix=d/'isolated';work=d/'unrelated';work.mkdir()
    p=call([R/'tools/install.sh','--offline','--prefix',prefix]);(OUT/'install.log').write_bytes(p.stdout+p.stderr)
    ck(p.returncode==0,'offline source install',rc=p.returncode)
    om=prefix/'bin/om';omg=prefix/'bin/omg';payload=prefix/'lib/omega-native'
    ck(om.resolve()==omg.resolve(),'aliases same implementation')
    src=work/'kernel ; $(no-eval).cu';src.write_bytes((R/'tests/cuda-cpp/vector.cu').read_bytes())
    data=struct.pack('<'+'I'*12,2,2,3,100,101,102,1,0xffffffff,3,4,2,5)
    expected=struct.pack('<III',5,1,8)
    for command in (om,omg):
        p=call([command,'check','--from','cuda-cpp',src],b'not consumed',work)
        ck(p.returncode==0 and not p.stdout and not p.stderr,'check '+command.name,rc=p.returncode)
        p=call([command,'run','--from','cuda-cpp','--target','cpu-sim',src],data,work)
        ck(p.returncode==0 and p.stdout==expected and not p.stderr,'run '+command.name,rc=p.returncode)
    exe=work/'out executable';p=call([om,'build','--from','cuda-cpp','--target','cpu-sim',src,'-o',exe],b'not consumed',work)
    ck(p.returncode==0 and not p.stdout and exe.exists(),'build',rc=p.returncode)
    ck(call([exe],data).stdout==expected,'built executable')
    ck(exe.stat().st_mode&0o777==0o700,'executable private mode')
    # Lab GPU code is explicit non-executable data, never silently launched.
    capsule=work/'kernel.omgpu'
    p=call([om,'build','--from','cuda-cpp','--target','sm_121-lab',src,'-o',capsule],cwd=work)
    ck(p.returncode==0 and capsule.is_file(),'offline native GPU capsule build',rc=p.returncode)
    body=capsule.read_bytes()
    ck(body[:4]==b'OMGP' and struct.unpack_from('<III',body,4)==(1,121,1),'GPU capsule identity and lab-only flag')
    ck(capsule.stat().st_mode&0o777==0o600,'GPU capsule is non-executable private data')
    p=call([om,'check','--from','cuda-cpp','--target','sm_121-lab',src],cwd=work)
    ck(p.returncode==0 and not p.stdout,'lab GPU check emits no public output')
    p=call([om,'run','--from','cuda-cpp','--target','sm_121-lab',src],data,work)
    ck(p.returncode==69 and not p.stdout,'unqualified lab GPU launch refused')
    # Never silently pretend CPU simulation is GPU compilation.
    for command in ('run','build'):
        for target in ([],['--target','sm_121'],['--target','cuda'],['--target','gpu']):
            args=[om,command,'--from','cuda-cpp',*target,src]
            if command=='build':args+=['-o',exe]
            before=exe.read_bytes();p=call(args,data,work)
            ck(p.returncode==69 and not p.stdout and exe.read_bytes()==before,command+' target refusal '+str(target),rc=p.returncode)
    # Refused source preserves a valuable output, not merely nonzero exit.
    bad=work/'bad.cu';bad.write_bytes(src.read_bytes().replace(b'left[index]',b'out[index]'))
    before=exe.read_bytes();p=call([om,'build','--from','cuda-cpp','--target','cpu-sim',bad,'-o',exe],cwd=work)
    ck(p.returncode==65 and not p.stdout and exe.read_bytes()==before,'bad source transactional')
    for path in (src,):
        before=src.read_bytes();p=call([om,'build','--from','cuda-cpp','--target','cpu-sim',src,'-o',path],cwd=work)
        ck(p.returncode==73 and src.read_bytes()==before,'same input output preserves source')
    hard=work/'hard';os.link(src,hard)
    p=call([om,'build','--from','cuda-cpp','--target','cpu-sim',src,'-o',hard],cwd=work)
    ck(p.returncode==73 and hard.read_bytes()==src.read_bytes(),'hardlinked source refusal')
    link=work/'link';link.symlink_to(exe)
    before=exe.read_bytes();p=call([om,'build','--from','cuda-cpp','--target','cpu-sim',src,'-o',link],cwd=work)
    ck(p.returncode==73 and exe.read_bytes()==before,'symlink destination preserves victim')
    dash=work/'-';dash.write_bytes(src.read_bytes())
    p=call([om,'run','--from','cuda-cpp','--target','cpu-sim','--','-'],data,work)
    ck(p.returncode==0 and p.stdout==expected,'literal dash file caller stdin')
    for data_bad in (data[:-1],data+b'extra',b''):
        p=call([om,'run','--from','cuda-cpp','--target','cpu-sim',src],data_bad,work)
        ck(p.returncode==77 and not p.stdout,'simulator refusal exit status',rc=p.returncode)
    p=call([om,'check','--from','cuda-cpp','--target','cpu-sim',src],cwd=work)
    ck(p.returncode==0,'check explicit simulator target')
    p=call([om,'check','--from','cuda-cpp','--target','sm_121',src],cwd=work)
    ck(p.returncode==69,'check refuses unqualified GPU target')
    p=call([om,'check','--from','rust',src],cwd=work);ck(p.returncode==69,'unknown source language')
    # Original native Omega behavior remains intact.
    plain=work/'plain.om';plain.write_text('fn main to int\nret 23\nend\n')
    p=call([om,'run',plain],cwd=work);ck(p.returncode==23,'original Omega run status')
    p=call([om,'math','eval 1/3+1/6'],cwd=work);ck(p.returncode==0 and p.stdout==b'OK 1/2\n','math unchanged')
    # Integrity refuses a changed native frontend, without executing it.
    frontend=payload/'cuda-cpp';saved=frontend.read_bytes();frontend.write_bytes(saved+b'x')
    p=call([om,'check','--from','cuda-cpp',src],cwd=work)
    ck(p.returncode==65 and not p.stdout,'changed frontend integrity refusal')
    frontend.write_bytes(saved)
    # Installation collision never overwrites the existing installation.
    before=hashlib.sha256(frontend.read_bytes()).hexdigest();p=call([R/'tools/install.sh','--offline','--prefix',prefix])
    ck(p.returncode==73 and hashlib.sha256(frontend.read_bytes()).hexdigest()==before,'install collision preserves candidate')
    p=call([omg,'uninstall'],cwd=work)
    ck(p.returncode==0 and not om.exists() and not frontend.exists() and not prefix.exists(),'uninstall owns frontend and aliases',rc=p.returncode,stderr=p.stderr.decode())
print(json.dumps({'checks':len(rows),'passed':sum(r['pass'] for r in rows)}))
