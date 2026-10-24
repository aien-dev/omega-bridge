/* A hand-written statement of the six test units' exported C signatures, from the contract in
 * docs/NATIVE-ABI.md and the units' Omega signature lines, independent of the generator.
 * tests/native/run.sh compiles this file with the generated omega_native.h included first: if the
 * generator's declarations disagree with these, the compiler reports conflicting types. */
#include <stdint.h>

/* fn madd a ulong b ulong c ulong to ulong */
uint32_t omega_madd(uint64_t *result, uint64_t a, uint64_t b, uint64_t c);
/* fn smadd a long b long c long to long */
uint32_t omega_smadd(uint64_t *result, uint64_t a, uint64_t b, uint64_t c);
/* fn fill buf edit ulong 4 k ulong to ulong */
uint32_t omega_fill(uint64_t *result, void *buf, uint64_t buf_len, uint64_t k);
/* fn spin n ulong to ulong */
uint32_t omega_spin(uint64_t *result, uint64_t n);
/* fn mix a ulong b long c view uchar 3 d edit uchar 2 e view ulong 2 f ulong to void */
uint32_t omega_mix(uint64_t *result, uint64_t a, uint64_t b, const void *c, uint64_t c_len, void *d, uint64_t d_len,
                   const void *e, uint64_t e_len, uint64_t f);
/* fn big n ulong to ulong */
uint32_t omega_big(uint64_t *result, uint64_t n);
