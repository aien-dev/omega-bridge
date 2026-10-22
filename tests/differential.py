"""Test infrastructure only. No compiler or source translation lives here."""
import os, pathlib, subprocess, sys, hashlib, json, time
ROOT = pathlib.Path(__file__).resolve().parents[1]
os.chdir(ROOT)
SEED = os.environ.get('OMEGA_SEED', 'build/bootstrap/omc')
B = ROOT / 'build/tests'
B.mkdir(parents=True, exist_ok=True)
def run(cmd, data=b''):
    return subprocess.run([str(c) for c in cmd], input=data, capture_output=True, timeout=20)
def elf(path):
    b = path.read_bytes()
    assert len(b) >= 120 and b[:5] == b'\x7fELF\x02' and b[18:20] == b'\xb7\x00', 'not a nonempty AArch64 ELF'
    path.chmod(0o755)
def same(a,b):
    return (a.returncode,a.stdout,a.stderr)==(b.returncode,b.stdout,b.stderr)
fail = count = 0
receipts=[]
started=time.perf_counter()
for f in sorted((ROOT/'tests/fixtures').glob('*.om')):
    if f.stem in ('r5b_cycle','r5b_assign','r5b_fwd_fm'): continue
    count += 1
    try:
        data=f.read_bytes()
        native=run([SEED],data)
        assert native.returncode==0, native.stderr
        exe=B/f'{f.stem}.native'; exe.write_bytes(native.stdout); elf(exe)
        inp=bytes(range(256))*195 if f.stem in ('echo','bytecopy') else b''
        expected=run([exe],inp)
        rec=dict(case=f.stem,source_sha256=hashlib.sha256(data).hexdigest(),input_sha256=hashlib.sha256(inp).hexdigest(),native=dict(exit=expected.returncode,stdout_hex=expected.stdout.hex(),stderr_hex=expected.stderr.hex()))
        if f.stem=='echo': assert expected.stdout==inp
        if f.stem=='bytecopy': assert expected.stdout==inp[::-1]
        if f.stem=='order_calls': assert expected.stdout==b'ABCD' and expected.returncode==1
        if f.stem=='order_trap': assert expected.stdout==b'' and expected.returncode==102
        if f.stem=='fib':
            nums=[0,1]
            for _ in range(24): nums.append(sum(nums[-2:]))
            assert expected.stdout==(''.join(str(x)+'\n' for x in nums)).encode()
        want=f.with_suffix('.want')
        if want.exists(): assert expected.returncode==int(want.read_text()), 'native differs from fixture'
        c=run(['build/toc'],data) if '--baseline' in sys.argv else run(['tools/bridge','c',f])
        assert c.returncode==0 and c.stdout, ('conversion',c.returncode,c.stderr)
        cfile=B/f'{f.stem}.c'; cfile.write_bytes(c.stdout)
        rec['c_sha256']=hashlib.sha256(c.stdout).hexdigest()
        ce=B/f'{f.stem}.c.exe'
        cc=run(['gcc','-std=gnu11','-O1','-fsanitize=undefined','-fno-sanitize-recover=all',cfile,'-o',ce])
        assert cc.returncode==0, ('gcc',cc.stderr[:300])
        got=run([ce],inp)
        rec['c']=dict(exit=got.returncode,stdout_hex=got.stdout.hex(),stderr_hex=got.stderr.hex())
        assert same(expected,got), ('C mismatch',expected.returncode,got.returncode,expected.stdout[:80],got.stdout[:80],got.stderr[:100])
        if '--baseline' not in sys.argv:
            p=run(['tools/bridge','python',f]); assert p.returncode==0 and p.stdout, p.stderr
            py=B/f'{f.stem}.py'; py.write_bytes(p.stdout)
            rec['python_sha256']=hashlib.sha256(p.stdout).hexdigest()
            got=run([sys.executable,py],inp)
            rec['python']=dict(exit=got.returncode,stdout_hex=got.stdout.hex(),stderr_hex=got.stderr.hex())
            assert same(expected,got), ('Python mismatch',expected.returncode,got.returncode,got.stderr[:200])
        receipts.append(rec)
        print('PASS', f.stem)
    except Exception as e:
        fail+=1; print('FAIL',f.stem,str(e))
print(f'cases={count} failures={fail} RC={int(bool(fail))}')
pathlib.Path('build/differential-receipts.json').write_text(json.dumps(dict(cases=count,failures=fail,seconds=time.perf_counter()-started,results=receipts),indent=2)+'\n')
sys.exit(bool(fail))
