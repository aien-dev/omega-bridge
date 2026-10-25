"""Compile and run independent C and Python host programs."""
import os, pathlib, subprocess, sys
root=pathlib.Path(__file__).resolve().parents[1]
os.chdir(root)
b=root/'build/attachments'; b.mkdir(exist_ok=True)
def run(args):
    p=subprocess.run([str(x) for x in args],capture_output=True,timeout=20)
    assert p.returncode==0,(args,p.returncode,p.stderr[:600])
    return p.stdout
for target,ext in [('c','c'),('python','py')]:
    out=run(['tools/bridge',target,'examples/attachment.om'])
    assert out
    (b/f'attachment.{ext}').write_bytes(out)
try:
    run(['gcc','-O1','-std=gnu11','-fsanitize=undefined','-fno-sanitize-recover=all','-I',b,'examples/caller.c','-o',b/'caller'])
    print(run([b/'caller']).decode().strip())
    (b/'caller.py').write_bytes(pathlib.Path('examples/caller.py').read_bytes())
    print(run([sys.executable,b/'caller.py']).decode().strip())
except Exception as exc:
    print('FAIL',exc);sys.exit(1)
print('attachment cases=2 failures=0 RC=0')
