#!/usr/bin/env python3
"""Exercise pure-scalar transport, source refusals, and the GPU_FS_LINK import gate."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
OMC = os.environ['OMEGA_NATIVE_OMC']
ALLOWED = {'_GLOBAL_OFFSET_TABLE_', 'memcpy', 'memmove', 'memset', 'memcmp', 'strlen', 'strcmp'}
# Shared with tests/native/x86/suite.py, which runs the same caller under qemu-x86_64.
EPOCH = 'fn guard n ulong to ulong\nif eq n 18446744073709551615\ntrap 1\nend\nret n\nend\nfn epoch n ulong to ulong\nx = guard n\nret add x 1\nend\n'
CALLER = '''#include "omega_native.h"
#include <pthread.h>
#include <stdint.h>
static pthread_barrier_t barrier;
static void *call(void *arg) {
    (void)arg;
    pthread_barrier_wait(&barrier);
    for (unsigned i = 0; i < 10000; ++i) {
        uint64_t v = 17;
        if (omega_epoch(&v, UINT64_MAX) != 1 || v != 17) return (void *)1;
        if (omega_epoch(&v, 1) || v != 2) return (void *)1;
        if (omega_smadd(&v, UINT64_C(0x7fffffffffffffff), 2, 0) != 1 || v != 2) return (void *)1;
        if (omega_smadd(&v, 3, 5, 7) || v != 22) return (void *)1;
    }
    return 0;
}
int main(void) {
    pthread_t threads[4];
    if (omega_epoch(0, 1) != OMEGA_BAD_ARG) return 1;
    if (pthread_barrier_init(&barrier, 0, 4)) return 1;
    for (unsigned i = 0; i < 4; ++i) if (pthread_create(&threads[i], 0, call, 0)) return 1;
    for (unsigned i = 0; i < 4; ++i) { void *v; if (pthread_join(threads[i], &v) || v) return 1; }
    return pthread_barrier_destroy(&barrier) != 0;
}
'''


def run(args, **kw):
    p = subprocess.run([str(a) for a in args], capture_output=True, **kw)
    if p.returncode:
        raise AssertionError(f'{args}: exit {p.returncode}\n{p.stdout!r}\n{p.stderr!r}')
    return p.stdout


def imports(obj):
    return {line.split()[-1] for line in run(['nm', '-u', obj]).decode().splitlines() if line.split()}


def main():
    with tempfile.TemporaryDirectory(prefix='bridge-freestanding-') as td:
        t = Path(td)
        epoch = t / 'epoch.om'
        epoch.write_text(EPOCH)
        out = t / 'lib'
        run([ROOT / 'tools/native', '--freestanding', out, epoch, ROOT / 'tests/native/smadd.om'])
        assert not imports(out / 'omega_native.o') - ALLOWED
        linked = t / 'freestanding.o'
        run(['cc', '-r', '-nostdlib', out / 'omega_native.o', '-o', linked])
        assert not imports(linked) - ALLOWED
        assert '.tbss' not in run(['readelf', '-SW', linked]).decode()
        assert '.tdata' not in run(['readelf', '-SW', linked]).decode()
        assert not (out / 'libomega_native.so').exists()
        assert not (out / 'omega_native.py').exists()
        caller = t / 'caller.c'
        caller.write_text(CALLER)
        run(['cc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror', '-pthread', '-I', out, caller, linked, '-o', t / 'caller'])
        run([t / 'caller'])
        print('PASS freestanding epoch increment/MAX trap, nested trap unwind, signed trap and four-thread isolation; GPU_FS_LINK imports and no TLS')
        gen = out / 'work/native-gen'
        code = (out / 'work/epoch.bin').read_bytes()
        refusals = {
            'global': 'global a ulong 1\nfn epoch n ulong to ulong\nret n\nend\n',
            'text': 'text a "a"\nfn epoch n ulong to ulong\nret n\nend\n',
            'array': 'fn epoch a view ulong 1 to ulong\nret get a 0\nend\n',
            'local-array': 'fn epoch n ulong to ulong\na = new ulong 1 0\nret n\nend\n',
            'host': 'fn epoch n ulong to ulong\nr = getpid\nret n\nend\n',
            'exit': 'fn epoch n ulong to ulong\nexit 0\nret n\nend\n',
            'hidden-host-helper': 'fn hidden to ulong\nret monons\nend\nfn epoch n ulong to ulong\nret n\nend\n',
            'om2': 'om2\nfn epoch n ulong to ulong\nret n\nend\n',
        }
        for name, source in refusals.items():
            frame = source.encode() + b'\0' + f'{len(code):08d}'.encode() + code
            p = subprocess.run([gen, 'freest'], input=frame, capture_output=True)
            assert p.returncode == 110 and not p.stdout, (name, p.returncode, p.stdout)
        print('PASS freestanding refuses arrays, storage, text, host effects including unused helper and OM-2 before any output')
        # Mutate the .om emitter, not a production C implementation. The normal tools/native gate
        # must refuse an actual pthread import and leave an already installed library untouched.
        mutant = t / 'mutant'
        (mutant / 'tools').mkdir(parents=True)
        (mutant / 'src').mkdir()
        shutil.copy2(ROOT / 'tools/native', mutant / 'tools/native')
        source = (ROOT / 'src/native.om').read_text()
        import json
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if line.startswith('text fp '):
                runtime = json.loads(line[len('text fp '):])
                runtime += '#include <pthread.h>\npthread_t ombr_mutant(void);\npthread_t ombr_mutant(void) { return pthread_self(); }\n'
                lines[i] = 'text fp ' + json.dumps(runtime)
                break
        else:
            raise AssertionError('freestanding runtime template missing')
        (mutant / 'src/native.om').write_text('\n'.join(lines) + '\n')
        before = (out / 'omega_native.o').read_bytes()
        p = subprocess.run([mutant / 'tools/native', '--freestanding', out, epoch], capture_output=True)
        assert p.returncode != 0 and b'pthread_self' in p.stderr and b'imports refused' in p.stderr, p.stderr
        assert (out / 'omega_native.o').read_bytes() == before
        print('PASS pthread-import emitter mutant rejected by freestanding gate, installed object unchanged')
        # Inspector failures are refusals, not an empty, implicitly accepted symbol set.
        fakebin = t / 'fakebin'
        fakebin.mkdir()
        inspectenv = os.environ.copy()
        inspectenv['PATH'] = str(fakebin) + os.pathsep + inspectenv['PATH']
        for command, status in (('nm', 1), ('nm', 127), ('awk', 1)):
            fake = fakebin / command
            fake.write_text(f'#!/bin/sh\nexit {status}\n')
            fake.chmod(0o755)
            p = subprocess.run([ROOT / 'tools/native', '--freestanding', out, epoch],
                               env=inspectenv, capture_output=True)
            assert p.returncode != 0 and b'inspection' in p.stderr, p.stderr
            assert (out / 'omega_native.o').read_bytes() == before
            fake.unlink()
        print('PASS failing/missing symbol inspector and failing import filter refuse; installed object unchanged')

        # Inject a source replacement just after the real, still-pinned compiler
        # returns. No timing race and no fake compiler/hash oracle are involved.
        race = t / 'race-tool'
        (race / 'tools').mkdir(parents=True)
        (race / 'src').mkdir()
        shutil.copy2(ROOT / 'src/native.om', race / 'src/native.om')
        driver = (ROOT / 'tools/native').read_text()
        marker = '    "$OMC" < "$src" > "$W/work/$b.bin"'
        assert marker in driver
        driver = driver.replace(marker, marker + '\n    cp -- "$RACE_PURE" "$u"')
        target = t / 'race.om'
        unsafe = b'fn race n ulong to ulong\na = new ulong 1 0\nret n\nend\n'
        safe = b'fn race n ulong to ulong\nret n\nend\n'
        replacement = t / 'pure.om'
        replacement.write_bytes(safe)
        raceenv = os.environ.copy()
        raceenv['RACE_PURE'] = str(replacement)
        script = race / 'tools/native'
        script.write_text(driver)
        script.chmod(0o755)
        target.write_bytes(unsafe)
        p = subprocess.run([script, '--freestanding', out, target], env=raceenv, capture_output=True)
        assert p.returncode == 110 and b'refused' in p.stderr, p.stderr
        assert target.read_bytes() == safe
        assert (out / 'omega_native.o').read_bytes() == before
        # Restore the old reread defect: now the exact same swap incorrectly
        # admits non-pure machine code under the replacement's pure source.
        unsnapshotted = driver.replace('src=$W/work/$b.om', 'src=$u')
        assert unsnapshotted != driver
        script.write_text(unsnapshotted)
        target.write_bytes(unsafe)
        raceout = t / 'race-mutant-output'
        run([script, '--freestanding', raceout, target], env=raceenv)
        frame = (raceout / 'work/units.in').read_bytes()
        actualsource, payload = frame.split(b'\0', 1)
        assert actualsource == safe
        assert payload[8:] == run([OMC], input=unsafe)
        print('PASS source-swap control refuses original non-pure snapshot; reread mutant admits mismatched source/code and is caught')


if __name__ == '__main__':
    main()
