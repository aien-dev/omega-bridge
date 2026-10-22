#!/usr/bin/env python3
"""Offline GPU-code qualification. Decoder execution is NOT a GPU hardware run."""
from pathlib import Path
import hashlib,json,os,random,struct,subprocess
R=Path(__file__).resolve().parents[2];O=Path(os.environ.get('CUDA_CPP_GPU_OUT',R/'build/cuda-cpp-gpu-tests'));O.mkdir(parents=True,exist_ok=True)
F=R/'build/native/cuda-cpp';OMC=R/'build/bootstrap/omc';rows=[]
def run(args,data=b''):
    return subprocess.run(list(map(str,args)),input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
def ck(ok,name,**kw):
    rows.append({'name':name,'pass':bool(ok),**kw})
    if not ok:
        (O/'results.json').write_text(json.dumps(rows,indent=2));raise AssertionError((name,kw))
seed=(R/'tests/cuda-cpp/reference/vecadd.bin').read_bytes()
ck(hashlib.sha256(seed).hexdigest()=='39f3dfdfc529a75a8274a27900acf4e7382b7f280a211e0412c51609f44b62a1','pinned seed reference')
# The LDC R8,n insertion is checked independently from the known original prologue.
prefix=seed[:16]+struct.pack('<4I',0xff087b82,0xe600,0x800,0xfe200)+seed[16:18*16]
def capsule(data):
    if len(data)<544 or data[:4]!=b'OMGP':raise ValueError('capsule magic/length')
    version,arch,flags,size,gprs,params,inputs=struct.unpack_from('<7I',data,4)
    if (version,arch,flags,params,inputs)!=(1,121,1,28,2):raise ValueError('capsule identity')
    if not 17<=gprs<=144 or size<512 or size%128 or size+32!=len(data):raise ValueError('capsule resources')
    code=data[32:]
    if code[:len(prefix)]!=prefix:raise ValueError('launch prologue differs from pinned reference')
    return [struct.unpack_from('<4I',code,j) for j in range(len(prefix),len(code),16)],gprs
# Independent decoder: it reads instruction fields, not frontend AST/desired expression.
def evaluate(insns,gprs,a,b,n):
    regs={2:a,5:b,8:n,255:0};output=None;ended=False;branched=False
    def read(r):
        if r not in regs:raise ValueError('uninitialized register')
        return regs[r]
    for w0,w1,w2,w3 in insns:
        op=w0&0xffff;d=(w0>>16)&255;s=(w0>>24)&255
        if branched:
            if (w0,w1,w2,w3)!=(0x7918,0,0,0xfc000):raise ValueError('bad padding')
            continue
        if ended:
            if (w0,w1,w2,w3)!=(0xfc7947,0xfffffffc,0x0383ffff,0xfc000):raise ValueError('missing terminal guard')
            branched=True;continue
        if output is not None:
            if (w0,w1,w2,w3)!=(0x794d,0,0x03800000,0xfea00):raise ValueError('missing exit')
            ended=True;continue
        if op==0x7986:
            if (w0,w2,w3)!=(0x06007986,0x0c101904,0xfe200) or w1>255:raise ValueError('bad output store')
            output=read(w1);continue
        if not 16<=d<gprs:raise ValueError('destination outside declared GPRs')
        if op==0x7802:
            if s or w2!=0xf00 or w3!=0xfe200:raise ValueError('bad MOV')
            v=w1
        elif op==0x7210:
            if w1>255 or w2!=0x07ffe0ff or w3!=0x010fca00:raise ValueError('bad IADD3')
            v=read(s)+read(w1)
        elif op in (0x7224,0x7824):
            if w2!=0x078e02ff or w3!=0x001fca00:raise ValueError('bad IMAD')
            v=read(s)*(read(w1) if op==0x7224 else w1)
        elif op==0x7212:
            lut=(w2>>8)&255
            if w1>255 or w2!=(0x078e00ff|(lut<<8)) or w3!=0x001fca00:raise ValueError('bad LOP3')
            av,bv=read(s),read(w1);v=0
            for bit in range(32):
                index=(((av>>bit)&1)<<2)|(((bv>>bit)&1)<<1)
                v|=((lut>>index)&1)<<bit
        else:raise ValueError('unknown arithmetic opcode')
        regs[d]=v&0xffffffff
    if not ended or not branched or output is None:raise ValueError('incomplete kernel')
    return output
ENCODER=Path(os.environ.get('CUDA_CPP_C_ENCODER',R/'build/cuda-cpp-reference/c-encoder'))
ck(ENCODER.is_file(),'external canonical C encoder available')
q=run([ENCODER],b'ldc 8 -1 -1 920\n')
ck(q.returncode==0 and q.stdout==prefix[16:32],'length LDC equals canonical C encoder')
def check_encoder(code,label):
    requests=[];expected=bytearray()
    for w0,w1,w2,w3 in code:
        op=w0&0xffff;d=(w0>>16)&255;a=(w0>>24)&255
        if op==0x7986:break
        if op==0x7802:args=('mov',d,-1,-1,w1)
        elif op==0x7210:args=('add',d,a,w1,0)
        elif op==0x7224:args=('mul',d,a,w1,0)
        elif op==0x7824:args=('muli',d,a,-1,w1)
        elif op==0x7212:args=('lop',d,a,w1,(w2>>8)&255)
        else:raise ValueError('unknown op before C differential')
        requests.append(' '.join(map(str,args)))
        expected.extend(struct.pack('<4I',w0,w1,w2,w3))
    result=run([ENCODER],('\n'.join(requests)+'\n').encode())
    ck(result.returncode==0 and result.stdout==expected,label+' all arithmetic words match canonical encoder',instructions=len(requests))
rng=random.Random(605121)
def test_semantics(data,reference,tag):
    code,gprs=capsule(data)
    for k,(blocks,threads,n) in enumerate([(1,1,0),(1,1,1),(1,1,7),(2,3,17),(1,32,32),(4,32,129)]+[(rng.randint(1,4),rng.randint(1,32),rng.randint(0,137)) for _ in range(8)]):
        vals=[[rng.getrandbits(32) for _ in range(n)] for _ in range(3)]
        for a in vals:
            for j in range(min(5,n)):a[j]=[0,1,0xffffffff,0x80000000,0x7fffffff][j]
        frame=struct.pack('<'+'I'*(3+3*n),blocks,threads,n,*vals[0],*vals[1],*vals[2])
        expected=run([reference],frame);ck(expected.returncode==0,tag+' oracle run '+str(k))
        output=[evaluate(code,gprs,vals[1][i],vals[2][i],n) if i<blocks*threads else vals[0][i] for i in range(n)]
        got=struct.pack('<'+'I'*n,*output)
        ck(got==expected.stdout,tag+' decoded instructions vs original C++ '+str(k),output_sha256=hashlib.sha256(got).hexdigest())
# Require current CPU/original-source differential gate, rather than trusting stale fixtures.
status=json.loads((R/'build/cuda-cpp-tests/results.json').read_text())
ck(status and all(row['pass'] for row in status),'upstream CPU/oracle gate complete')
inputs=json.loads((R/'build/cuda-cpp-tests/inputs.json').read_text())
required={'src/cuda-cpp.om','src/cuda-sm121.om','tests/cuda-cpp/gate.py','build/native/cuda-cpp','build/bootstrap/omc'}
ck(set(inputs)==required and all(hashlib.sha256((R/path).read_bytes()).hexdigest()==digest for path,digest in inputs.items()),'upstream source and executable closure is current')
for j in range(16):
    cpp=(R/f'build/cuda-cpp-tests/e{j}.cpp').read_bytes()
    begin=cpp.index(b'__global__ void');end=cpp.index(b'\nstatic unsigned int word')
    source=cpp[begin:end];p=run([F],b'G'+source)
    ck(p.returncode==0 and p.stdout,f'e{j} native GPU emission',rc=p.returncode,stderr=p.stderr.decode())
    (O/f'e{j}.omgpu').write_bytes(p.stdout)
    code,gprs=capsule(p.stdout);check_encoder(code,f'e{j}');ck(True,f'e{j} capsule/prefix qualified',instructions=(len(p.stdout)-32)//16,gprs=gprs)
    test_semantics(p.stdout,R/f'build/cuda-cpp-tests/e{j}.oracle',f'e{j}')
# Pure code bytes plus capsule metadata; not an ELF and never run through host exec.
for label,payload in [('bad magic',b'X'+p.stdout[1:]),('truncated',p.stdout[:-1]),('extra',p.stdout+b'x')]:
    caught=False
    try:capsule(payload)
    except ValueError:caught=True
    ck(caught,'decoder refuses '+label)
for inputs in (1,4):
    cpp=(R/f'build/cuda-cpp-tests/arity{inputs}.cpp').read_bytes();source=cpp[cpp.index(b'__global__ void'):cpp.index(b'\nstatic unsigned int word')]
    q=run([F],b'G'+source);ck(q.returncode==69 and not q.stdout,f'unsupported ABI arity{inputs} refuses transactionally')
# Real semantic mutants compile and still produce structurally valid, decodable kernels.
core=(R/'src/cuda-cpp.om').read_bytes();backend=(R/'src/cuda-sm121.om').read_text()
for label,old,new,case in [('and-or','glop d a b 192','glop d a b 252',3),('mul-add','gmul d a b\nret','gadd d a b\nret',2),('sub-add','gneg d b','gadd d b 255',1)]:
    ck(backend.count(old)==1,label+' unique mutation')
    q=run([OMC],core+backend.replace(old,new).encode());ck(q.returncode==0 and q.stdout,label+' mutant compiles')
    exe=O/('mutant-'+label);exe.write_bytes(q.stdout);exe.chmod(0o700)
    ck(run([R/'tools/verify-elf.sh',exe]).returncode==0,label+' mutant executable ELF')
    cpp=(R/f'build/cuda-cpp-tests/e{case}.cpp').read_bytes();source=cpp[cpp.index(b'__global__ void'):cpp.index(b'\nstatic unsigned int word')]
    q=run([exe],b'G'+source);ck(q.returncode==0 and q.stdout,label+' mutant emits')
    code,gprs=capsule(q.stdout)
    got=evaluate(code,gprs,3,5,1)
    frame=struct.pack('<6I',1,1,1,99,3,5);ref=run([R/f'build/cuda-cpp-tests/e{case}.oracle'],frame)
    ck(ref.returncode==0 and got!=struct.unpack('<I',ref.stdout)[0],label+' semantic mutant caught')
(O/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps({'checks':len(rows),'passed':sum(r['pass'] for r in rows),'compiled_semantic_mutants_caught':3,'GPU_hardware':'NOT_RUN','scheduler_safety':'NOT_QUALIFIED'}))
