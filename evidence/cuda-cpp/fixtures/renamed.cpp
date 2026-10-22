#include <cstdlib>
#include <cstdint>
#include <cstdio>
#include <vector>
#define __global__
struct Dim { unsigned int x; };
Dim blockIdx,blockDim,threadIdx;
// CUDA C++ source: deliberately no macros or includes.
__global__ void calc(unsigned int *A0, const unsigned int *A1,
                          const unsigned int *A2, unsigned int Num) {
    unsigned int ix = blockIdx.x * blockDim.x + threadIdx.x;
    if (ix < Num) {
        A0[ix] = A1[ix] + A2[ix];
    }
}

static unsigned int word(){unsigned int v=0;for(unsigned i=0;i<4;i++){int c=getchar();if(c==EOF)std::exit(77);v|=unsigned(c)<<(8*i);}return v;}
int main(){static_assert(sizeof(unsigned int)==4);unsigned b=word(),t=word(),n=word();
std::vector<unsigned> a0(n);for(auto &v:a0)v=word();
std::vector<unsigned> a1(n);for(auto &v:a1)v=word();
std::vector<unsigned> a2(n);for(auto &v:a2)v=word();
blockDim.x=t;for(unsigned bi=0;bi<b;bi++){blockIdx.x=bi;for(unsigned ti=0;ti<t;ti++){threadIdx.x=ti;calc(a0.data(),a1.data(),a2.data(),n);}}
for(auto v:a0){for(unsigned j=0;j<4;j++){putchar((v>>(8*j))&255);}}return 0;}
