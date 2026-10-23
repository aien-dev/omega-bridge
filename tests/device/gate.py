#!/usr/bin/env python3
"""External test harness: compile and execute real Omega host-I/O programs."""
import pathlib, subprocess, json, sys, os, hashlib
compiler=pathlib.Path(sys.argv[1]).resolve(); out=pathlib.Path(sys.argv[2]); out.mkdir(parents=True,exist_ok=False)
cases={
'open-close':('''text path "/dev/null"
fn main to int
buf = new uchar 10 0
for i ulong 9
put buf i get path i
end
f = devopen buf 0 10
if lt f 0
ret int 1
end
r = devshut int f
if ne r 0
ret int 2
end
ret int 0
end
''',0),
'close-negative':('''fn main to int
r = devshut int -1
if ne r -9
ret int 1
end
ret int 0
end
''',0),
'path-unterminated':('''fn main to int
p = new uchar 4 65
f = devopen p 0 4
ret int 0
end
''',103),
'path-oob':('''fn main to int
p = new uchar 4 0
f = devopen p 2 3
ret int 0
end
''',103),
'path-empty':('''fn main to int
p = new uchar 1 0
f = devopen p 0 0
ret int 0
end
''',103),
'missing-path':('''text path "/dev/omega-L605-no-such-device"
fn main to int
p = new uchar 31 0
for i ulong 30
put p i get path i
end
f = devopen p 0 31
if ne f -2
ret int 1
end
ret int 0
end
''',0),
}
cases.update({
'ioctl-pipe':('''fn main to int
b = new uchar 8 99
r = devctl 0 21531 b 2 4
if ne r 0
ret 1
end
if ne get b 2 3
ret 2
end
if ne get b 5 0
ret 3
end
if or ne get b 1 99 ne get b 6 99
ret 4
end
ret 0
end
''',0),
'ioctl-short':('''fn main to int
b = new uchar 4 0
r = devctl 0 21531 b 0 3
ret 0
end
''',103),
'ioctl-oob':('''fn main to int
b = new uchar 4 0
r = devctl 0 21531 b 2 4
ret 0
end
''',103),
'ioctl-invalid-fd':('''fn main to int
b = new uchar 4 0
r = devctl -1 21531 b 0 4
if ne r -9
ret 1
end
ret 0
end
''',0),
'path-embedded-nul':('''fn main to int
p = new uchar 4 0
put p 0 65
put p 2 65
f = devopen p 0 4
ret 0
end
''',103),
})
open_src=cases['open-close'][0]
cases['nested-preserve']=(open_src.replace('r = devshut int f','a = long 123\nr = add a devshut int f').replace('if ne r 0','if ne r 123'),0)
cases['repeat-descriptors']=(open_src.replace('f = devopen buf 0 10','for j ulong 100\nf = devopen buf 0 10').replace('ret int 0\nend','end\nret int 0\nend'),0)
cases['view-open']=('fn op p view uchar 10 to long\nret devopen p 0 10\nend\n'+open_src.replace('devopen buf 0 10','op view buf'),0)
cases['global-open']=(open_src.replace('text path','global buf uchar 10\ntext path').replace('buf = new uchar 10 0\n',''),0)
cases['offset-wrap']=(cases['path-oob'][0].replace('p 2 3','p 18446744073709551615 1'),103)
cases['count-wrap']=(cases['path-oob'][0].replace('p 2 3','p 0 18446744073709551615'),103)
results=[]
for name,(source,expected) in cases.items():
    src=out/(name+'.om'); src.write_text(source)
    c=subprocess.run([str(compiler)],input=source.encode(),capture_output=True)
    (out/(name+'.compile.err')).write_bytes(c.stderr)
    row={'name':name,'compile_rc':c.returncode,'expected_rc':expected}
    if c.returncode==0 and c.stdout.startswith(b'\x7fELF'):
        exe=out/name; exe.write_bytes(c.stdout); exe.chmod(0o700)
        p=subprocess.run([str(exe)],input=b'abc',capture_output=True,timeout=5)
        row.update(run_rc=p.returncode,stdout=p.stdout.hex(),stderr=p.stderr.hex(),passed=p.returncode==expected)
    else: row['passed']=False
    results.append(row)
refusals={
'open-wrong-element':('fn main to int\np = new uint 4 0\nr = devopen p 0 4\nret 0\nend\n',7),
'ioctl-readonly':('text p "abc"\nfn main to int\nr = devctl 0 21531 p 0 4\nret 0\nend\n',20),
'ioctl-request-variable':('fn main to int\np = new uchar 4 0\nx = uint 21531\nr = devctl 0 x p 0 4\nret 0\nend\n',9),
'ioctl-unknown-request':('fn main to int\np = new uchar 4 0\nr = devctl 0 0 p 0 4\nret 0\nend\n',9),
'close-wrong-width':('fn main to int\nr = devshut ulong 0\nret 0\nend\n',7),
'function-mode':('fn probe to long\nret devshut -1\nend\n',9),
}
for name,(source,expected) in refusals.items():
    (out/(name+'.om')).write_text(source)
    c=subprocess.run([str(compiler)],input=source.encode(),capture_output=True)
    (out/(name+'.compile.err')).write_bytes(c.stderr)
    results.append({'name':name,'compile_rc':c.returncode,'expected_compile_rc':expected,'passed':c.returncode==expected and not c.stdout})
receipt={'compiler_sha256':hashlib.sha256(compiler.read_bytes()).hexdigest(),'cases':results,'passed':sum(x['passed'] for x in results),'total':len(results)}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n'); print(json.dumps(receipt,indent=2))
sys.exit(0 if all(x['passed'] for x in results) else 1)
