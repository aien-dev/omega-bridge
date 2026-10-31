"""Seeded-only internal binary32 differential and fail-closed controls."""
import os
import pathlib
import subprocess

root = pathlib.Path(__file__).resolve().parents[1]
os.chdir(root)
b = root / 'build/seeded-float'
b.mkdir(parents=True, exist_ok=True)
seed = os.environ['OMEGA_SEEDED_OMC']

def run(args, data=None):
    return subprocess.run(list(map(str, args)), input=data, capture_output=True, timeout=60)

def checked(args, data=None):
    p = run(args, data)
    assert p.returncode == 0, (args, p.returncode, p.stderr)
    return p.stdout

source = '''fn calc u uint to uint
x = bitcast f32 u
y = mul x 1.5f32
z = fabs y
if le z 3.0f32
ret bitcast uint y
end
ret bitcast uint z
end
fn main to int
out = new uchar 4 0
'''
for value in [0, 1, 8388607, 8388608, 1065353216, 2139095039, 2139095040, 2143289344, 2147483648]:
    source += f'u = calc {value}\nfor i ulong 4\nput out i uchar and shr u uint mul i 8 255\nend\nn = write 1 out 0 4\n'
source += 'ret 0\nend\n'
f = b / 'float.om'
f.write_text(source)
native = b / 'native'
native.write_bytes(checked([seed], source.encode()))
native.chmod(0o755)
expected = checked([native])
c = b / 'float.c'
c.write_bytes(checked(['sh', 'tools/bridge-seeded', 'c', f]))
checked(['gcc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror', c, '-o', b / 'portable'])
assert checked([b / 'portable']) == expected
for target in ['python']:
    p = run(['sh', 'tools/bridge-seeded', target, f])
    assert p.returncode != 0 and not p.stdout
p = run(['sh', 'tools/bridge', 'c', f])
assert p.returncode != 0 and not p.stdout
# Compile-time arithmetic-mode refusal is not an ignored warning.
p = run(['gcc', '-std=gnu11', '-O2', '-ffast-math', c, '-o', b / 'unsafe'])
assert p.returncode != 0 and b'fast math' in p.stderr
for name, body in {
    'public_float': 'fn root x f32 to f32\nret x\nend\n',
    'float_array': 'fn root x view f32 2 to uint\nret 0\nend\n',
    'float_cast': 'fn root x uint to uint\ny = bitcast f32 x\nret uint y\nend\n',
    'float_add': 'fn root x uint to uint\ny = bitcast f32 x\nz = add y 1.0f32\nret bitcast uint z\nend\n',
}.items():
    f = b / (name + '.om')
    f.write_text(body)
    for target in ['c', 'h']:
        p = run(['sh', 'tools/bridge-seeded', target, f])
        assert p.returncode != 0 and not p.stdout, (name, target, p.stderr)
print('PASS seeded binary32 byte differential; baseline/Python/public-float/array/cast/op/fast-math refusals')
