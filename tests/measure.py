"""Small end-to-end observations; includes process startup, not a speed claim."""
import pathlib, subprocess, statistics, time, json, sys, os, importlib.util, ctypes
root=pathlib.Path(__file__).resolve().parents[1];os.chdir(root)
b=root/'build/measure';b.mkdir(exist_ok=True)
def run(args,data=b''):
    p=subprocess.run([str(x) for x in args],input=data,capture_output=True,timeout=30)
    assert p.returncode==0,(args,p.returncode,p.stderr[:200])
    return p.stdout
rows=[]
for name in ('fib','sort','echo'):
    src=pathlib.Path(f'tests/fixtures/{name}.om')
    inp=bytes(range(256))*195 if name=='echo' else b''
    for target in ('c','python'):
        times=[]
        for _ in range(3):
            start=time.perf_counter();out=run(['tools/bridge',target,src]);times.append(time.perf_counter()-start)
        file=b/(name+('.c' if target=='c' else '.py'));file.write_bytes(out)
        rows.append(dict(workload=name,phase='checked_conversion',target=target,median_seconds=statistics.median(times),samples_seconds=times,source_bytes=src.stat().st_size,output_bytes=len(out)))
        if target=='c':run(['gcc','-O2','-std=gnu11',file,'-o',b/name])
    expected=run([root/'build/tests'/f'{name}.native'],inp)
    for target,args in [('native',[root/'build/tests'/f'{name}.native']),('c',[b/name]),('python',[sys.executable,b/(name+'.py')])]:
        times=[]
        for _ in range(5):
            start=time.perf_counter();got=run(args,inp);times.append(time.perf_counter()-start);assert got==expected
        rows.append(dict(workload=name,phase='process_execution',target=target,median_seconds=statistics.median(times),samples_seconds=times,input_bytes=len(inp)))
# Direct Python and ctypes calls use the same fixed-size sum and include boundary checks.
run(['gcc','-O2','-std=gnu11','-fPIC','-shared','build/attachments/attachment.c','-o',b/'attachment.so'])
spec=importlib.util.spec_from_file_location('measured_attachment','build/attachments/attachment.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
lib=ctypes.CDLL(str(b/'attachment.so'));f=lib.omega_total
# Deliberate demo-specific ABI declaration; not a general generated ctypes adapter.
f.argtypes=[ctypes.POINTER(ctypes.c_uint64),ctypes.c_void_p,ctypes.c_uint64];f.restype=ctypes.c_uint32
arr=(ctypes.c_uint64*4)(2,3,5,7);out=ctypes.c_uint64()
for target in ('python_module','ctypes_c'):
    samples=[]
    for _ in range(5):
        start=time.perf_counter()
        for i in range(10000):
            if target=='python_module':assert module.omega_total([2,3,5,7],4)==(0,17)
            else:assert f(ctypes.byref(out),arr,4)==0 and out.value==17
        samples.append(time.perf_counter()-start)
    rows.append(dict(workload='total4',phase='10000_checked_calls',target=target,median_seconds=statistics.median(samples),samples_seconds=samples))
report=dict(context='Shared Linux AArch64 host; quiet-build coordination, not an isolated performance window. Startup included for program runs. Python module call loop includes list construction; ctypes loop reuses C storage. Do not treat the two caller timings as a fair language speed comparison.',results=rows)
pathlib.Path('evidence/measurements.json').write_text(json.dumps(report,indent=2)+'\n')
for r in rows:print(r['phase'],r['workload'],r['target'],f"{r['median_seconds']:.6f}s")
print('measurement correctness checks RC=0')
