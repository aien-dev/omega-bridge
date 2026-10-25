"""Adversarial source boundaries; no accepted prefix may publish partial output."""
import os, pathlib, subprocess, sys, json
root=pathlib.Path(__file__).resolve().parents[1];os.chdir(root)
seed=os.environ.get('OMEGA_SEED','build/bootstrap/omc')
data=pathlib.Path('tests/fixtures/order_calls.om').read_bytes()
# All byte prefixes include mid-token, mid-number and unterminated blocks.
cases=[data[:i] for i in range(len(data)+1)]
cases += [b'C',b'\x00',b'\xff',b'fn main to int\nret '+b'neg '*1025+b'int 1\nend\n',b'note '+b'x'*65536+b'\nfn main to int\nret 0\nend\n']
count=0;refused=0;accepted=0
for src in cases:
    path=pathlib.Path('build/adversarial.om');path.write_bytes(src)
    native=subprocess.run([seed],input=src,capture_output=True,timeout=5)
    assert native.returncode>=0 and native.returncode<100, native.returncode
    for t in ('c','python'):
        p=(subprocess.run(['build/toc'],input=src,capture_output=True,timeout=5) if '--baseline' in sys.argv else subprocess.run(['tools/bridge',t,str(path)],capture_output=True,timeout=5))
        assert 0<=p.returncode<100,(t,p.returncode,p.stderr)
        if native.returncode:
            assert p.returncode==native.returncode and not p.stdout,(t,p.returncode,native.returncode)
        elif p.returncode:
            assert not p.stdout and b'error ' in p.stderr
        else:
            assert p.stdout
        refused+=int(p.returncode!=0);accepted+=int(p.returncode==0)
    count+=1
print(f'robustness cases={count} target_accepts={accepted} target_refusals={refused} failures=0 RC=0')
