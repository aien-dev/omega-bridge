// CUDA C++ source: deliberately no macros or includes.
__global__ void vector_add(unsigned int *out, const unsigned int *left,
                          const unsigned int *right, unsigned int count) {
    unsigned int index = blockIdx.x * blockDim.x + threadIdx.x;
    if (index < count) {
        out[index] = left[index] + right[index];
    }
}
