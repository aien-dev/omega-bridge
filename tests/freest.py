#!/usr/bin/env python3
"""Host-only scalar profile checks. Test infrastructure, never a source converter."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CC = os.environ.get('CC', 'cc')
RUNNER = shlex.split(os.environ.get('FREEST_RUNNER', ''))


def run(args, **kw):
    p = subprocess.run([str(a) for a in args], capture_output=True, **kw)
    assert p.returncode == 0, (args, p.returncode, p.stdout, p.stderr)
    return p.stdout


def main():
    with tempfile.TemporaryDirectory(prefix='bridge-freest-check-') as td:
        t = Path(td)
        objects = []
        for name in ('revision', 'epoch', 'scalar'):
            src = ROOT / f'tests/freest-fixtures/{name}.om'
            if name != 'scalar' and os.environ.get('FREEST_CUDAPP_ROOT'):
                src = Path(os.environ['FREEST_CUDAPP_ROOT']) / f'om/pipeline/{name}.om'
            c = t / f'{name}.c'
            c.write_bytes(run([ROOT / 'tools/bridge-freest', 'c', src]))
            (t / f'{name}.h').write_bytes(run([ROOT / 'tools/bridge-freest', 'h', src]))
            for opt in ('0', '2'):
                obj = t / f'{name}-{opt}.o'
                run([CC, '-std=c11', f'-O{opt}', '-Wall', '-Wextra', '-Werror',
                     '-ffreestanding', '-fno-builtin', '-fno-stack-protector', '-fPIC',
                     '-c', c, '-o', obj])
                assert not run(['nm', '-u', obj]).strip(), obj
                sections = run(['readelf', '-SW', obj])
                assert b'.tdata' not in sections and b'.tbss' not in sections, sections
                if opt == '2':
                    objects.append(obj)
            # Hosted roots remain required and are independently emitted by toc.om.
            if name != 'scalar':
                hc = t / f'hosted_{name}.c'
                hc.write_bytes(run([ROOT / 'tools/bridge-seeded', 'c', src]))
                run([CC, '-std=gnu11', '-O' + os.environ.get('HOSTED_OPT', '2'), '-Wall', '-Wextra', '-Werror',
                     '-c', hc, '-o', t / f'hosted_{name}.o'])
        linked = t / 'freest.o'
        run([CC, '-r', '-nostdlib', *objects, '-o', linked])
        assert not run(['nm', '-u', linked]).strip()
        caller = t / 'caller.c'
        caller.write_text('''#include <stdint.h>
#include "revision.h"
#include "epoch.h"
#include "scalar.h"
int main(void) {
    uint64_t out=17;
    if(omega_native_revision(&out,0)||out!=1)return 1;
    if(omega_native_revision(&out,UINT64_MAX)||out!=0)return 2;
    if(omega_native_revision(&out,UINT64_MAX-1)||out!=UINT64_MAX)return 3;
    if(omega_native_epoch(&out,0)||out!=1)return 4;
    if(omega_native_epoch(&out,UINT64_MAX)||out!=UINT64_MAX)return 5;
    if(omega_native_epoch(&out,UINT64_MAX-1)||out!=UINT64_MAX)return 6;
    out=17;
    if(omega_native_epoch(0,0)!=32)return 7;
    if(omega_native_epoch((uint64_t *)(uintptr_t)1,0)!=32)return 8;
    if(omega_native_epoch((uint64_t *)UINTPTR_MAX,0)!=32)return 9;
    if(omega_portable_scalar(&out,3,UINT64_MAX)||out!=11)return 10;
    if(omega_portable_scalar(&out,UINT32_MAX,0)||out!=1)return 11;
    out=17;
    if(omega_portable_scalar(&out,UINT64_MAX,0)!=32||out!=17)return 12;
    return 0;
}
''')
        run([CC, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-I', t,
             caller, linked, '-o', t / 'caller'])
        run([*RUNNER, t / 'caller'])
        # Same caller against hosted roots, with the independent scalar freest object.
        run([CC, '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror', '-I', t,
             caller, t / 'hosted_revision.o', t / 'hosted_epoch.o', objects[-1],
             '-o', t / 'hosted-caller'])
        run([*RUNNER, t / 'hosted-caller'])
        print('PASS hosted roots at O' + os.environ.get('HOSTED_OPT', '2') + '; import-free freest roots at O0/O2; MAX boundaries, checked ABI, arbitrary helper names, wrap, signed comparisons and branch locals')
        print('PASS O0/O2 objects and -r -nostdlib link: nm -u empty; no TLS sections')
        # A wrong expected result must actually fail the caller, not merely compile.
        wrong = t / 'wrong.c'
        wrong.write_text(caller.read_text().replace('out!=11', 'out!=12'))
        run([CC, '-std=c11', '-O2', '-I', t, wrong, linked, '-o', t / 'wrong'])
        p = subprocess.run([*RUNNER, t / 'wrong'], capture_output=True)
        assert p.returncode == 10, p.returncode
        print('PASS wrong-result negative control exits 10')
        # WolframLanguageEvaluator (parent routed): Table[{w,w-1,2^w-1,
        # BitAnd[BitShiftLeft[2^w-1,w-1],2^w-1],
        # BitShiftRight[2^w-1,w-1]},{w,{8,16,32,64}}] ->
        # {{8,7,255,128,1},{16,15,65535,32768,1},
        # {32,31,4294967295,2147483648,1},
        # {64,63,18446744073709551615,9223372036854775808,1}}.
        # Native seed results independently check the projected result byte.
        for typ, count, projection, value, left, right in (
                ('uchar', 0, 0, 1, None, None),
                ('uchar', 1, 0, 1, None, None),
                ('ushort', 1, 0, 1, None, None),
                ('uint', 1, 0, 1, None, None),
                ('ulong', 63, 63, 1, None, None),
                ('uchar', 7, 0, 255, 128, 1),
                ('ushort', 15, 0, 65535, 32768, 1),
                ('uint', 31, 0, 4294967295, 2147483648, 1),
                ('ulong', 63, 0, 18446744073709551615, 9223372036854775808, 1)):
            for op in ('shl', 'shr'):
                fixture = t / 'shift.om'
                body = f'fn shift x {typ} to {typ}\nret {op} x {count}\nend\n'
                fixture.write_text(body)
                portable = run([ROOT / 'tools/bridge-freest', 'c', fixture])
                native_source = body + f'fn main to int\nr = shift {typ} {value}\nret int and shr ulong r {projection} 255\nend\n'
                native = t / 'shift-native'
                native.write_bytes(run([os.environ['OMEGA_SEEDED_OMC']], input=native_source.encode()))
                native.chmod(0o755)
                expected = subprocess.run([native], capture_output=True).returncode
                assert expected not in range(101, 115), expected
                c = t / 'shift.c'
                bound = left if op == 'shl' else right
                check = '' if bound is None else f'if(out != UINT64_C({bound}))return 98;'
                caller = '\nint main(void){uint64_t out=0;if(omega_shift(&out,UINT64_C(' + str(value) + ')))return 99;' + check + 'return (int)((out >> ' + str(projection) + ')&255);}\n'
                c.write_bytes(portable + caller.encode())
                run([CC, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', c, '-o', t / 'shift'])
                assert subprocess.run([*RUNNER, t / 'shift'], capture_output=True).returncode == expected, (typ, op, count)
                if typ == 'ulong' and op == 'shl':
                    c.write_bytes(portable.replace(b'case 15:return (a<<b)&mask;', b'case 15:return (a>>b)&mask;') + caller.encode())
                    run([CC, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', c, '-o', t / 'shift-wrong'])
                    assert subprocess.run([*RUNNER, t / 'shift-wrong'], capture_output=True).returncode != expected
        print('PASS literal-count shifts: seed/native-C parity and wrong-direction negative control')
        root = 'fn arbitrary x ulong to ulong\nret x\nend\n'
        hidden = lambda body: f'fn hidden x ulong to ulong\n{body}\nend\n' + root
        refusals = {
            'loop': hidden('for i ulong 1\nx = add x 1\nend\nret x'),
            'while': hidden('while false bound 1\nx = add x 1\nend\nret x'),
            'array-param': 'fn hidden x view ulong 1 to ulong\nret get x 0\nend\n' + root,
            'array-local': hidden('a = new ulong 1 0\nret x'),
            'global': 'global state ulong 1\n' + root,
            'text': 'text msg "x"\n' + root,
            'host': hidden('v = getpid\nret x'),
            'io': hidden('b = new uchar 1 0\nv = write 1 b 0 1\nret x'),
            'main': 'fn main to int\nret 0\nend\n',
            'recursion': 'fn hidden x ulong to ulong\nret hidden x\nend\n' + root,
            'mutual-recursion': 'fn a x ulong to ulong\nret b x\nend\nfn b x ulong to ulong\nret a x\nend\n' + root,
            'float': 'fn hidden x f64 to f64\nret x\nend\n' + root,
            'signed-add': 'fn hidden x long to long\nret add x 1\nend\n' + root,
            'signed-neg': 'fn hidden x long to long\nret neg x\nend\n' + root,
            'signed-mul': 'fn hidden x long to long\nret mul x 2\nend\n' + root,
            'div': hidden('ret div x 1'),
            'rem': hidden('ret rem x 1'),
            'shift': hidden('ret shl x x'),
            'right-shift': hidden('ret shr x x'),
            'shift-at-width': hidden('ret shl x 64'),
            'right-shift-at-width': hidden('ret shr x 64'),
            'negative-shift': hidden('ret shl x -1'),
            'boolean-shift': hidden('ret shr x true'),
            'signed-shift': 'fn hidden x long to long\nret shr x 1\nend\n' + root,
            'narrow': hidden('v = uint x\nret ulong v'),
            'sign-conversion': hidden('v = long x\nret ulong v'),
            'trap': hidden('trap 1'),
            'om2': 'om2\n' + root,
        }
        for name, source in refusals.items():
            src = t / f'{name}.om'
            src.write_text(source)
            for mode in ('c', 'h'):
                p = subprocess.run([ROOT / 'tools/bridge-freest', mode, src], capture_output=True)
                assert p.returncode != 0 and not p.stdout, (name, mode, p.returncode, p.stdout, p.stderr)
        print(f'PASS {len(refusals)} whole-unit refusal controls in c and h modes, including unused helpers; stdout empty')
        # Structural refusal is independently challenged without the seed frontend.
        converter = t / 'converter'
        converter.write_bytes(run([os.environ['OMEGA_SEED']], input=(ROOT / 'src/freest.om').read_bytes()))
        converter.chmod(0o755)
        for name in ('loop', 'while', 'global', 'text', 'host', 'float', 'signed-add',
                     'div', 'rem', 'shift', 'narrow', 'recursion', 'mutual-recursion', 'main'):
            p = subprocess.run([converter], input=b'F' + refusals[name].encode(), capture_output=True)
            expected = 7 if name == 'float' else 24
            assert p.returncode == expected and not p.stdout, (name, p.returncode, p.stdout, p.stderr)
        print('PASS direct structural converter refusals independently of frontend, including recursive call graph')


if __name__ == '__main__':
    main()
