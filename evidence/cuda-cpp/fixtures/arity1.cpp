#include <cstdlib>
#include <cstdint>
#include <cstdio>
#include <vector>
#define __global__
struct Dim { unsigned int x; };
Dim blockIdx,blockDim,threadIdx;
__global__ void k(unsigned int *out, const unsigned int *p0, unsigned int n) {unsigned int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n){out[i]=p0[i];}}
static unsigned int word(){unsigned int v=0;for(unsigned i=0;i<4;i++){int c=getchar();if(c==EOF)std::exit(77);v|=unsigned(c)<<(8*i);}return v;}
int main(){static_assert(sizeof(unsigned int)==4);unsigned b=word(),t=word(),n=word();
std::vector<unsigned> a0(n);for(auto &v:a0)v=word();
std::vector<unsigned> a1(n);for(auto &v:a1)v=word();
blockDim.x=t;for(unsigned bi=0;bi<b;bi++){blockIdx.x=bi;for(unsigned ti=0;ti<t;ti++){threadIdx.x=ti;k(a0.data(),a1.data(),n);}}
for(auto v:a0){for(unsigned j=0;j<4;j++){putchar((v>>(8*j))&255);}}return 0;}
