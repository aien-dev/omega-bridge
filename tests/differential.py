"""Test infrastructure only. No compiler or source translation lives here."""
import os, pathlib, subprocess, sys, hashlib
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
        want=f.with_suffix('.want')
        if want.exists(): assert expected.returncode==int(want.read_text()), 'native differs from fixture'
        c=run(['build/toc'],data) if '--baseline' in sys.argv else run(['tools/bridge','c',f])
        assert c.returncode==0 and c.stdout, ('conversion',c.returncode,c.stderr)
        cfile=B/f'{f.stem}.c'; cfile.write_bytes(c.stdout)
        ce=B/f'{f.stem}.c.exe'
        cc=run(['gcc','-std=gnu11','-O1','-fsanitize=undefined','-fno-sanitize-recover=all',cfile,'-o',ce])
        assert cc.returncode==0, ('gcc',cc.stderr[:300])
        got=run([ce],inp)
        assert same(expected,got), ('C mismatch',expected.returncode,got.returncode,expected.stdout[:80],got.stdout[:80],got.stderr[:100])
        if '--baseline' not in sys.argv:
            p=run(['tools/bridge','python',f]); assert p.returncode==0 and p.stdout, p.stderr
            py=B/f'{f.stem}.py'; py.write_bytes(p.stdout)
            got=run([sys.executable,py],inp)
            assert same(expected,got), ('Python mismatch',expected.returncode,got.returncode,got.stderr[:200])
        print('PASS', f.stem)
    except Exception as e:
        fail+=1; print('FAIL',f.stem,str(e))
print(f'cases={count} failures={fail} RC={int(bool(fail))}')
sys.exit(bool(fail))
