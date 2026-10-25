"""Refusal parity with pinned Omega frontend and explicit backend capability errors."""
import pathlib, subprocess, os, json, sys
root=pathlib.Path(__file__).resolve().parents[1];os.chdir(root)
seed=os.environ.get('OMEGA_SEED','build/bootstrap/omc')
rows=json.loads(pathlib.Path('tests/refusals.json').read_text())
for name in ('r5b_assign','r5b_cycle'):
    rows.append(dict(name=name,source=pathlib.Path(f'tests/fixtures/{name}.om').read_text()))
fail=0
for row in rows:
    try:
        data=row['source'].encode()
        p=subprocess.run([seed],input=data,capture_output=True,timeout=10)
        if 'backend_error' in row:
            assert p.returncode==0,('native rejected capability probe',p.returncode,p.stderr)
            want=row['backend_error']
        else:
            want=row.get('error',p.returncode)
            if want is None: want=p.returncode
            assert 0< p.returncode < 100 and p.returncode==want,('seed',want,p.returncode,p.stderr)
        path=pathlib.Path('build/refusal.om');path.write_bytes(data)
        for target in ('c','python'):
            got=(subprocess.run(['build/toc'],input=data,capture_output=True,timeout=10) if '--baseline' in sys.argv else subprocess.run(['tools/bridge',target,str(path)],capture_output=True,timeout=10))
            assert got.returncode==want and not got.stdout and f'error {want}'.encode() in got.stderr,(target,want,got.returncode,got.stderr)
        print('PASS',row['name'],want)
    except Exception as e:
        fail+=1;print('FAIL',row['name'],e)
print(f'refusal cases={len(rows)} failures={fail} RC={int(bool(fail))}')
sys.exit(bool(fail))
