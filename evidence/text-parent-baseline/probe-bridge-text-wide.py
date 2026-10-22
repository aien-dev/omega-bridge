from pathlib import Path
import subprocess,hashlib,json
h=Path.home();w=h/'workspace/omega-bridge-native-development';root=h/'handoffs/bridge-text-baseline';seed=w/'build/bootstrap/omc'
assert hashlib.sha256(seed.read_bytes()).hexdigest()=='191b776ef98821597c3e30655da6d680a9b66edbc9ceaca3c39c61ea6df098e9'
def literal(data):
 escapes={9:b'\\t',10:b'\\n',34:b'\\"',92:b'\\\\'}
 return b'"'+b''.join(escapes.get(n,bytes([n])) for n in data)+b'"'
def prog(data,body=None):return b'text t '+literal(data)+b'\nfn main to int\n'+(body or b'w = write 1 t 0 len t\nret 0\n')+b'end\n'
allbytes=bytes(range(256));rev=bytes(reversed(allbytes));repeat=allbytes*4
view=b'text t "abc"\nfn val a view uchar 3 to uchar\nret get a 2\nend\nfn main to int\nret int val t\nend\n'
edit=b'text t "abc"\nfn val a edit uchar 3 to void\nput a 0 1\nend\nfn main to int\nval t\nret 0\nend\n'
cases=[('all-byte-values',prog(allbytes),allbytes,0),('all-byte-reverse',prog(rev),rev,0),('repeated-alphabet',prog(repeat),repeat,0),('readonly-view-call',view,b'',ord('c')),('readonly-put',prog(b'abc',b'put t 0 1\nret 0\n'),None,None),('readonly-read',prog(b'abc',b'n = read 0 t 0 1\nret 0\n'),None,None),('readonly-edit-call',edit,None,None),('empty-runtime-bounds',prog(b'',b'i = ulong 0\nv = get t i\nret int v\n'),None,'observe')]
rows=[]
for name,src,want,status in cases:
 built=subprocess.run([str(seed)],input=src,capture_output=True,timeout=20)
 row={'name':name,'source_hex':src.hex(),'source_sha256':hashlib.sha256(src).hexdigest(),'native_compile_rc':built.returncode,'native_stderr':built.stderr.decode(errors='replace')}
 if built.returncode==0:
  assert built.stdout[:4]==b'\x7fELF' and len(built.stdout)>64
  exe=root/(name+'.elf');exe.write_bytes(built.stdout);exe.chmod(0o700)
  subprocess.run([str(w/'tools/verify-elf.sh'),str(exe)],check=True,capture_output=True)
  result=subprocess.run([str(exe)],input=b'',capture_output=True,timeout=10)
  assert not result.stderr,(name,result.stderr)
  row.update(native_rc=result.returncode,native_stdout_hex=result.stdout.hex())
  if status!='observe':assert result.returncode==status and result.stdout==want,(name,result.returncode,result.stdout)
 else:assert want is None,(name,built.returncode,built.stderr)
 rows.append(row)
report={'seed_sha256':hashlib.sha256(seed.read_bytes()).hexdigest(),'source_base':'0fc7d8662cb799e7c206b17c18ea4c3ec2b8fea9','executed':len(rows),'cases':rows}
(root/'extended-native-oracle.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'executed':len(rows),'cases':[{k:v for k,v in r.items() if k in ('name','native_compile_rc','native_rc')} for r in rows]},indent=2))
