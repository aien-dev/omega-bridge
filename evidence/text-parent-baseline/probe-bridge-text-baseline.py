from pathlib import Path
import subprocess,hashlib,json,os
h=Path.home();w=h/'workspace/omega-bridge-native-development';root=h/'handoffs/bridge-text-baseline';root.mkdir(exist_ok=True)
seed=w/'build/bootstrap/omc';emitter=w/'build/bridge'
assert hashlib.sha256(seed.read_bytes()).hexdigest()=='191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9'
def program(lit):return b'text t '+lit+b'\nfn main to int\nw = write 1 t 0 len t\nret 0\nend\n'
cases=[('empty',program(b'""'),b''),('hello',program(b'"hello"'),b'hello'),('escapes',program(b'"A\\tB\\\\C\\\"D\\nZ"'),b'A\tB\\C"D\nZ'),('raw-nul',program(b'"A\x00B"'),b'A\x00B'),('utf8',program('"caf\u00e9 \u03a9"'.encode()),'caf\u00e9 \u03a9'.encode()),('unused',b'text t "abc"\nfn main to int\nret 0\nend\n',b''),('bad-escape',program(b'"a\\qb"'),None),('unterminated',program(b'"abc'),None),('inline-literal',b'fn main to int\nw = write 1 "abc" 0 3\nret 0\nend\n',None)]
rows=[]
for name,src,want in cases:
 build=subprocess.run([str(seed)],input=src,capture_output=True,timeout=20)
 row={'name':name,'source':src.decode('utf8'),'source_sha256':hashlib.sha256(src).hexdigest(),'native_compile_rc':build.returncode,'native_stderr':build.stderr.decode(errors='replace')}
 if want is not None:
  assert build.returncode==0 and build.stdout[:4]==b'\x7fELF' and len(build.stdout)>64,(name,build.returncode,build.stderr)
  exe=root/(name+'.elf');exe.write_bytes(build.stdout);exe.chmod(0o700)
  subprocess.run([str(w/'tools/verify-elf.sh'),str(exe)],check=True,capture_output=True)
  got=subprocess.run([str(exe)],capture_output=True,timeout=10)
  assert got.returncode==0 and got.stdout==want and got.stderr==b'',(name,got)
  row.update(native_rc=got.returncode,native_stdout_hex=got.stdout.hex(),expected_stdout_hex=want.hex())
  targets={}
  for target in ('C','P'):
   result=subprocess.run([str(emitter)],input=target.encode()+src,capture_output=True,timeout=10)
   assert result.returncode in (16,24) and not result.stdout,(name,target,result.returncode,result.stdout[:80])
   targets[target]={'rc':result.returncode,'stdout_bytes':len(result.stdout),'stderr':result.stderr.decode(errors='replace')}
  row['old_bridge']=targets
 else:assert build.returncode!=0,(name,'unexpected native acceptance')
 rows.append(row)
report={'source_commit':'0fc7d8662cb799e7c206b17c18ea4c3ec2b8fea9','seed_sha256':hashlib.sha256(seed.read_bytes()).hexdigest(),'cases':rows,'executed':len(rows),'native_accepts':sum('native_rc' in r for r in rows),'native_refusals':sum('native_rc' not in r for r in rows)}
(root/'baseline.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))
