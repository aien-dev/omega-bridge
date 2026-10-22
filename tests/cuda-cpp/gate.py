#!/usr/bin/env python3
"""Independent test harness; production parsing and lowering are native Omega."""
import hashlib,json,os,random,struct,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(os.environ.get('CUDA_CPP_TEST_OUT',ROOT/'build/cuda-cpp-tests'))
OUT.mkdir(parents=True,exist_ok=True)
FRONT=ROOT/'build/native/cuda-cpp'
OMC=ROOT/'build/bootstrap/omc'
records=[]
def run(args,data=b'',**kw):
    return subprocess.run(list(map(str,args)),input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20,**kw)
def check(ok,label,**info):
    records.append({'name':label,'pass':bool(ok),**info})
    if not ok:
        (OUT/'results.json').write_text(json.dumps(records,indent=2))
        raise AssertionError((label,info))
def compile_native(source,name,front=FRONT):
    p=run([front],b'C'+source)
    check(p.returncode==0 and p.stdout, name+' frontend',rc=p.returncode,stderr=p.stderr.decode(errors='replace'))
    (OUT/(name+'.om')).write_bytes(p.stdout)
    q=run([OMC],p.stdout)
    check(q.returncode==0 and q.stdout,name+' native compile',rc=q.returncode,stderr=q.stderr.decode(errors='replace'))
    exe=OUT/(name+'.native');exe.write_bytes(q.stdout);exe.chmod(0o700)
    check(run([ROOT/'tools/verify-elf.sh',exe]).returncode==0,name+' static ELF')
    return exe
base=(ROOT/'tests/cuda-cpp/vector.cu').read_bytes()
# C++ compilation of the ORIGINAL CUDA source, not the emitted Omega program.
def oracle(source,name,kernel='vector_add',inputs=2):
    cpp=b'''#include <cstdint>\n#include <cstdio>\n#include <vector>\n#define __global__\nstruct Dim { unsigned int x; };\nDim blockIdx,blockDim,threadIdx;\n'''+source+b'''\nstatic unsigned int word(){unsigned int v=0;for(unsigned i=0;i<4;i++){int c=getchar();if(c==EOF)std::exit(77);v|=unsigned(c)<<(8*i);}return v;}\nint main(){static_assert(sizeof(unsigned int)==4);unsigned b=word(),t=word(),n=word();\n'''
    cpp=b'#include <cstdlib>\n'+cpp
    for j in range(inputs+1): cpp+=f'std::vector<unsigned> a{j}(n);for(auto &v:a{j})v=word();\n'.encode()
    cpp+=b'blockDim.x=t;for(unsigned bi=0;bi<b;bi++){blockIdx.x=bi;for(unsigned ti=0;ti<t;ti++){threadIdx.x=ti;'
    cpp+=f'{kernel}('.encode()+','.join(f'a{j}.data()' for j in range(inputs+1)).encode()+b',n);}}\n'
    cpp+=b'for(auto v:a0){for(unsigned j=0;j<4;j++){putchar((v>>(8*j))&255);}}return 0;}\n'
    src=OUT/(name+'.cpp');src.write_bytes(cpp);exe=OUT/(name+'.oracle')
    p=run(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-Wno-error=parentheses','-Wno-error=unused-parameter',src,'-o',exe])
    check(p.returncode==0,name+' C++ original oracle compile',stderr=p.stderr.decode(errors='replace'))
    return exe
rng=random.Random(605)
def frame(b,t,n,inputs=2):
    values=[b,t,n]
    for j in range(inputs+1):
        values.extend(([0,1,0xffffffff,0x80000000,0x7fffffff][i%5] if i<10 else rng.getrandbits(32)) for i in range(n))
    return struct.pack('<'+'I'*len(values),*values)
exprs=['left[index] + right[index]','left[index] - right[index]','left[index] * right[index]',
       'left[index] & right[index]','left[index] ^ right[index]','left[index] | right[index]',
       'left[index] + right[index] * 3U','(left[index] + right[index]) * 3u',
       'left[index] - right[index] - 1U','left[index] | right[index] ^ count & 17U',
       '4294967295U + left[index]','0U - left[index]','count','42U',
       ' + '.join(['1U']*64), '(' * 15 + '1U' + ')' * 15]
cases=[(1,1,0),(1,1,1),(1,1,7),(2,3,17),(2,32,63),(4,32,128),(1,4096,4096),(4096,1,17)]
for j,expr in enumerate(exprs):
    source=base.replace(b'left[index] + right[index]',expr.encode())
    native=compile_native(source,f'e{j}')
    ref=oracle(source,f'e{j}')
    for k,(b,t,n) in enumerate(cases+[(rng.randint(1,8),rng.randint(1,32),rng.randint(0,150)) for _ in range(10)]):
        data=frame(b,t,n);p=run([native],data);q=run([ref],data)
        check(p.returncode==q.returncode==0 and p.stdout==q.stdout and not p.stderr,f'e{j} case{k}',native_rc=p.returncode,oracle_rc=q.returncode,input_sha256=hashlib.sha256(data).hexdigest(),output_sha256=hashlib.sha256(p.stdout).hexdigest())
# Names deliberately collide with Omega implementation names; source identifiers must be resolved.
renamed=base.replace(b'vector_add',b'calc').replace(b'index',b'ix').replace(b'count',b'Num').replace(b'out',b'A0').replace(b'left',b'A1').replace(b'right',b'A2')
native=compile_native(renamed,'renamed');ref=oracle(renamed,'renamed','calc')
data=frame(4,16,67)
check(run([native],data).stdout==run([ref],data).stdout,'renamed identifiers')
# One and four read-only input buffers.
for count in (1,4):
    params=', '.join(f'const unsigned int *p{j}' for j in range(count))
    expression=' + '.join(f'p{j}[i]' for j in range(count))
    source=f'__global__ void k(unsigned int *out, {params}, unsigned int n) {{unsigned int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n){{out[i]={expression};}}}}'.encode()
    native=compile_native(source,f'arity{count}');ref=oracle(source,f'arity{count}','k',count)
    for n in (0,1,31,4096):
        data=frame(4,32,n,count);p=run([native],data);q=run([ref],data)
        check(p.returncode==q.returncode==0 and p.stdout==q.stdout,f'arity{count} n{n}')
# Exact source capacity and whitespace/comment variants retain semantic behavior.
for label,source in [('source-exact',base+b' '*(16384-len(base))),('crlf',base.replace(b'\n',b'\r\n')),('comments',base.replace(b'unsigned int *out',b'unsigned /*comment*/ int *out'))]:
    native=compile_native(source,label);ref=oracle(source,label)
    data=frame(2,8,19);p=run([native],data);q=run([ref],data)
    check(p.returncode==q.returncode==0 and p.stdout==q.stdout,label+' parity')
# All invalid source cases must publish no output.
neg={
'host function':base.replace(b'__global__',b'__host__'),
'float':base.replace(b'unsigned int',b'float'),
'unknown buffer':base.replace(b'left[index] +',b'unknown[index] +'),
'output read':base.replace(b'left[index] +',b'out[index] +'),
'const write':base.replace(b'out[index] =',b'left[index] ='),
'duplicate names':base.replace(b'*right',b'*left'),
'unknown index':base.replace(b'right[index]',b'right[index+1U]'),
'index wrap':base.replace(b'blockIdx.x * blockDim.x + threadIdx.x',b'threadIdx.x'),
'bad bound':base.replace(b'index < count',b'index <= count'),
'unguarded':base.replace(b'if (index < count)',b'if (1U)'),
'include':b'#include <stdint.h>\n'+base,
'macro':b'#define X 1\n'+base,
'line splice':base+b'//test\\\n',
'NUL':base+b'\x00',
'extra function':base+base,
'signed literal':base.replace(b'left[index] + right[index]',b'1'),
'octal':base.replace(b'left[index] + right[index]',b'010U'),
'hex':base.replace(b'left[index] + right[index]',b'0x10U'),
'overflow literal':base.replace(b'left[index] + right[index]',b'4294967296U'),
'shift':base.replace(b'left[index] + right[index]',b'left[index] << 1U'),
'divide':base.replace(b'left[index] + right[index]',b'left[index] / 1U'),
'call':base.replace(b'left[index] + right[index]',b'foo()'),
'logical':base.replace(b'left[index] + right[index]',b'left[index] && right[index]'),
'comment EOF':base+b'/*',
'preprocessor trigraph':base+b'//??=x\n',
'deep':base.replace(b'left[index] + right[index]',b'('*17+b'1U'+b')'*17),
'long identifier':base.replace(b'vector_add',b'a'*64),
'over source':base+b' '*(16385-len(base)),
'over nodes':base.replace(b'left[index] + right[index]',b' + '.join([b'1U']*65)),
'keyword identifier':base.replace(b'vector_add',b'class'),
'namespace':base.replace(b'vector_add',b'ns::kernel'),
}
for label,source in neg.items():
    p=run([FRONT],b'C'+source)
    check(p.returncode in (65,67) and not p.stdout and p.stderr,'refuse '+label,rc=p.returncode)
# Input errors must be transactional before any stdout.
native=compile_native(base,'input')
valid=frame(2,3,7)
for i in range(len(valid)):
    p=run([native],valid[:i]);check(p.returncode==77 and not p.stdout,f'truncated frame {i}')
for label,data in [('extra',valid+b'x'),('zero blocks',frame(0,1,0)),('zero threads',frame(1,0,0)),('many blocks',frame(4097,1,0)),('many threads',frame(1,4097,0)),('product',frame(4096,2,0)),('length',struct.pack('<III',1,1,4097))]:
    p=run([native],data);check(p.returncode==77 and not p.stdout,'input refusal '+label,rc=p.returncode)
# Native-source mutations must compile and execute, then disagree with an independent oracle.
original=(ROOT/'src/cuda-cpp.om').read_text()
mutations=[('add-sub','text Ops "add sub mul and xor or"','text Ops "sub sub mul and xor or"'),
           ('buffer-map','ret node 1 0 0 add j 1','ret node 1 0 0 1'),
           ('literal','put Value 0 v','put Value 0 add v 1')]
for label,old,new in mutations:
    check(original.count(old)==1,'mutant unique '+label)
    p=run([OMC],original.replace(old,new).encode()+(ROOT/'src/cuda-sm121.om').read_bytes());check(p.returncode==0 and p.stdout,'mutant compiles '+label)
    mutant=OUT/('mutant-'+label);mutant.write_bytes(p.stdout);mutant.chmod(0o700)
    check(run([ROOT/'tools/verify-elf.sh',mutant]).returncode==0,'mutant ELF '+label)
    source=base.replace(b'left[index] + right[index]',b'left[index] + right[index] + 3U')
    exe=compile_native(source,'m-'+label,mutant);ref=oracle(source,'m-'+label)
    data=frame(1,32,27);p=run([exe],data);q=run([ref],data)
    check(p.returncode==q.returncode==0 and p.stdout!=q.stdout,'mutant caught '+label)
(OUT/'results.json').write_text(json.dumps(records,indent=2))
(OUT/'inputs.json').write_text(json.dumps({str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [ROOT/'src/cuda-cpp.om',ROOT/'src/cuda-sm121.om',ROOT/'tests/cuda-cpp/gate.py',FRONT,OMC]},indent=2)+'\n')
print(json.dumps({'checks':len(records),'passed':sum(r['pass'] for r in records),'source_sha256':hashlib.sha256(original.encode()).hexdigest(),'compiler_sha256':hashlib.sha256(OMC.read_bytes()).hexdigest()}))
