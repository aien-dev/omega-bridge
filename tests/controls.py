"""Deliberately damage emitted programs: the execution comparisons must notice."""
import pathlib, subprocess, os, sys, hashlib, json
root=pathlib.Path(__file__).resolve().parents[1];os.chdir(root)
b=root/'build/controls';b.mkdir(exist_ok=True)
seed=os.environ.get('OMEGA_SEED','build/bootstrap/omc')
def run(cmd,data=b''):
    env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:exitcode=86:abort_on_error=0')
    return subprocess.run([str(x) for x in cmd],input=data,capture_output=True,timeout=20,env=env)
def native(name):
    src=pathlib.Path(f'tests/fixtures/{name}.om').read_bytes()
    p=run([seed],src);assert p.returncode==0 and p.stdout[:4]==b'\x7fELF'
    path=b/'native';path.write_bytes(p.stdout);path.chmod(0o755)
    return run([path])
def result(p):return (p.returncode,p.stdout,p.stderr)
count=0; receipts=[]
for target,name,old,new in [
    ('c','num_ulong_add','(a+b)&mask','(a-b)&mask'),
    ('python','num_ulong_add','elif op == 1: z=x+y','elif op == 1: z=x-y'),
    ('c','t_bounds','if(i>=n)o_trap(3);switch','switch'),
    ('python','t_bounds','if i>=n: o_trap(3)','if False: o_trap(3)'),
    ('c','order_calls','o_op(2, 5, _a,_b)','o_op(2, 5, _b,_a)'),
    ('python','order_calls','o_op(2, 5, v1, v0)','o_op(2, 5, v0, v1)'),
]:
    expected=native(name)
    p=run(['tools/bridge',target,f'tests/fixtures/{name}.om']);assert p.returncode==0
    text=p.stdout.decode();assert old in text,(target,name,'mutation did nothing')
    text=text.replace(old,new)
    path=b/('mut.c' if target=='c' else 'mut.py');path.write_text(text)
    if target=='c':
        exe=b/'mut';cc=run(['gcc','-std=gnu11','-O1','-fsanitize=address,undefined','-fno-sanitize-recover=all',path,'-o',exe]);assert cc.returncode==0,cc.stderr
        got=run([exe])
    else: got=run([sys.executable,path])
    assert result(expected)!=result(got),('undetected mutant',target,name)
    count+=1;print('PASS detected',target,name,'native_exit',expected.returncode,'mutant_exit',got.returncode)
    receipts.append(dict(target=target,case=name,native_exit=expected.returncode,mutant_exit=got.returncode,mutant_sha256=hashlib.sha256(text.encode()).hexdigest(),stderr=got.stderr.decode(errors='replace').replace(str(root),'<repo>')[:1500]))
# Positive comparison cannot silently accept an empty target artifact or wrong output.
a=run(['tools/bridge','c','tests/fixtures/r5b_fwd.om']);z=run(['tools/bridge','c','tests/fixtures/r5b_fwd.om'])
assert a.returncode==0 and a.stdout==z.stdout and a.stdout
assert a.stdout != b''
count+=1;print('PASS deterministic nonempty output')
pathlib.Path('build/control-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
print(f'control cases={count} failures=0 RC=0')
