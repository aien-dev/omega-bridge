#!/usr/bin/env python3
"""OM-2 freestanding binding: FIPS 180-4 digests of sha256-om2.om through outputs freest + fapic,
the out-buffer rules, and a mutant runtime that drops the copy-back."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = {'_GLOBAL_OFFSET_TABLE_', 'memcpy', 'memmove', 'memset', 'memcmp', 'strlen', 'strcmp'}
# FIPS 180-2/180-4 examples: empty, "abc", the 448-bit message, and 1,000,000 'a'.
WANT = {
    'empty': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    'abc': 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
    '448': '248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1',
    'million': 'cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0',
}


def run(args, **kw):
    p = subprocess.run([str(a) for a in args], capture_output=True, **kw)
    if p.returncode:
        raise AssertionError(f'{args}: exit {p.returncode}\n{p.stdout!r}\n{p.stderr!r}')
    return p.stdout


def main():
    with tempfile.TemporaryDirectory(prefix='bridge-freestanding-om2-') as td:
        t = Path(td)
        out = t / 'lib'
        run([ROOT / 'tools/native', '--freestanding', out,
             ROOT / 'tests/native/v2/sha256-om2.om', ROOT / 'tests/native/v2/fsout.om'])
        assert not (out / 'libomega_native.so').exists()
        defined = set()
        imports = {}
        for obj in ('omega_native.o', 'omega_api_defs.o'):
            imports[obj] = {line.split()[-1]
                            for line in run(['nm', '-u', out / obj]).decode().splitlines() if line.split()}
            defined |= {line.split()[-1]
                        for line in run(['nm', '--defined-only', '-g', out / obj]).decode().splitlines()
                        if line.split()}
            sections = run(['readelf', '-SW', out / obj]).decode()
            assert '.tbss' not in sections and '.tdata' not in sections
        for obj, names in imports.items():
            assert not names - ALLOWED - defined, (obj, names - ALLOWED - defined)
        assert not (out / 'omega_api.h').exists()
        # The freestanding object compiled as the consumer would, with the required flags.
        run(['cc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror', '-Wmissing-prototypes',
             '-ffreestanding', '-fno-builtin', '-fno-stack-protector',
             '-include', out / 'omega_native.h', '-c', out / 'omega_native.c', '-o', t / 'again.o'])
        caller = t / 'fsom2'
        run(['cc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror', '-pthread', '-I', out,
             ROOT / 'tests/native/v2/fsom2.c', out / 'omega_native.o', out / 'omega_api_defs.o',
             '-o', caller])
        lines = run([caller]).decode().splitlines()
        got = dict(line.split() for line in lines if line.split()[0] in WANT)
        assert got == WANT, got
        assert 'badarg 32 1' in lines and 'outok 0 2 7 1' in lines and 'outtrap 5 1' in lines
        assert 'threads 1' in lines
        print('PASS OM-2 freestanding: FIPS 180-4 digests, bad-arg and trap leave out untouched, four threads')
        # A trap instruction: 133 when the shell reports it, -5 (SIGTRAP) when Python does.
        p = subprocess.run([caller, 'trap'], capture_output=True)
        assert p.returncode in (133, -5) and not p.stdout, (p.returncode, p.stdout)
        print('PASS fapic wrapper traps on a nonzero status (exit 133)')

        # Negative control: drop the copy-back from the runtime. The digest checks must then fail,
        # because the caller's buffer keeps its pre-call fill.
        mutant = t / 'mutant'
        (mutant / 'tools').mkdir(parents=True)
        (mutant / 'src').mkdir()
        shutil.copy2(ROOT / 'tools/native', mutant / 'tools/native')
        lines_src = (ROOT / 'src/native.om').read_text().splitlines()
        for i, line in enumerate(lines_src):
            if line.startswith('text fq '):
                parts = json.loads(line[len('text fq '):]).split('~')
                assert parts[0].count('__builtin_memmove') == 1
                parts[0] = parts[0].replace('__builtin_memmove(o[i].dst, buf[i], o[i].n);', '(void)buf[i];')
                lines_src[i] = 'text fq ' + json.dumps('~'.join(parts))
                break
        else:
            raise AssertionError('freestanding OM-2 runtime template missing')
        (mutant / 'src/native.om').write_text('\n'.join(lines_src) + '\n')
        mout = t / 'mutlib'
        run([mutant / 'tools/native', '--freestanding', mout,
             ROOT / 'tests/native/v2/sha256-om2.om', ROOT / 'tests/native/v2/fsout.om'])
        mcaller = t / 'mfsom2'
        run(['cc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror', '-pthread', '-I', mout,
             ROOT / 'tests/native/v2/fsom2.c', mout / 'omega_native.o', mout / 'omega_api_defs.o',
             '-o', mcaller])
        mlines = subprocess.run([mcaller], capture_output=True).stdout.decode().splitlines()
        mgot = dict(line.split() for line in mlines if line.split() and line.split()[0] in WANT)
        assert mgot != WANT, mgot
        print('PASS mutant runtime (copy-back dropped) fails the digest checks')


if __name__ == '__main__':
    main()
