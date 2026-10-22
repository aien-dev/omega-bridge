from pathlib import Path
import subprocess as sp,json,hashlib
h=Path.home();w=h/'workspace/omega-bridge-text-native';out=h/'handoffs/bridge-text-parent-verification';out.mkdir(exist_ok=True)
sha='74905efb3f4f8503cbacf3d521450bd82aed3a09'
assert sp.check_output(['git','-C',str(w),'rev-parse','HEAD'],text=True).strip()==sha
sp.run(['git','-C',str(w),'diff','--exit-code','6876f4d79883592bd19ba229a664cede99fe35ca',sha,'--','src','seed','tools','tests','provenance'],check=True)
bridge=w/'build/native/bridge'
assert hashlib.sha256(bridge.read_bytes()).hexdigest()=='a45e11608c79cd834ab06149106798c45562daeebba2f28210606009323bdc78'
rows=[]
for filename in ['baseline.json','extended-native-oracle.json']:
 rows+=json.loads((h/'handoffs/bridge-text-baseline'/filename).read_text())['cases']
assert len(rows)==17 and len({r['source_sha256'] for r in rows})==17
results=[]
for i,r in enumerate(rows):
 src=bytes.fromhex(r['source_hex']) if 'source_hex' in r else r['source'].encode()
 assert hashlib.sha256(src).hexdigest()==r['source_sha256']
 for target in ['C','P']:
  source=out/f'input-{i}.om';source.write_bytes(src)
  got=sp.run([str(w/'tools/bridge'),'c' if target=='C' else 'python',str(source)],capture_output=True,timeout=15)
  record={'name':r['name'],'target':target,'conversion_rc':got.returncode}
  if r['native_compile_rc']!=0:
   record['expected_refusal']=r['native_compile_rc']
   record['refusal_matches']=got.returncode==r['native_compile_rc'] and not got.stdout
   assert got.returncode!=0 and not got.stdout,(r['name'],target,'unsafe acceptance')
  else:
   assert got.returncode==0 and got.stdout,(r['name'],got)
   path=out/f'case-{i}.{ "c" if target=="C" else "py"}'
   path.write_bytes(got.stdout)
   if target=='C':
    exe=out/f'case-{i}.exe'
    built=sp.run(['cc','-std=c11','-O2',str(path),'-o',str(exe)],capture_output=True,timeout=30)
    assert built.returncode==0,built.stderr
    cmd=[str(exe)]
   else:cmd=['python3',str(path)]
   run=sp.run(cmd,input=b'',capture_output=True,timeout=15)
   assert run.returncode==r['native_rc'] and run.stdout.hex()==r['native_stdout_hex'] and not run.stderr,(r['name'],target,run)
   record.update(runtime_rc=run.returncode,stdout_hex=run.stdout.hex())
  record['pass']=record.get('refusal_matches',True);results.append(record)
report={'head':sha,'unique_sources':len(rows),'requested':len(rows)*2,'executed':len(results),'passed':sum(x['pass'] for x in results),'results':results}
(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='results'}))
