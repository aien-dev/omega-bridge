from pathlib import Path
import subprocess as sp,json
h=Path.home();w=h/'workspace/omega-bridge-text-native';d=h/'handoffs/bridge-text-parent-verification';d.mkdir(exist_ok=True)
src=d/'library-text.om';src.write_text('fn pick a view uchar 3 to uchar\nret get a 2\nend\n')
r=sp.run([str(w/'tools/bridge'),'python',str(src)],capture_output=True);assert r.returncode==0,r.stderr
module=d/'library_text.py';module.write_bytes(r.stdout)
r=sp.run(['python3','-c',"import runpy,json,sys;m=runpy.run_path(sys.argv[1]);print(json.dumps({'text_type':type(b'abc').__name__,'text_result':m['omega_pick'](b'abc',3),'mutable_result':m['omega_pick'](bytearray(b'abc'),3)}))",str(module)],capture_output=True,text=True)
assert r.returncode==0,r.stderr
result=json.loads(r.stdout);assert result['text_result']==[8,None] and result['mutable_result']==[0,99],result
(d/'readonly-view-red.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
