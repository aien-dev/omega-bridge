/* Independently generated bindings must retain private runtime and thread state.
 * Values and overflow case reuse the qualified vectors in caller.c. */
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>

uint32_t omega_madd(uint64_t *, uint64_t, uint64_t, uint64_t);
uint32_t omega_smadd(uint64_t *, uint64_t, uint64_t, uint64_t);
static pthread_barrier_t ready;

static void *exercise(void *arg)
{
    int *failed = arg;
    int rc = pthread_barrier_wait(&ready);
    if (rc != 0 && rc != PTHREAD_BARRIER_SERIAL_THREAD) {
        *failed = 1;
        return NULL;
    }
    for (unsigned i = 0; i < 10000; ++i) {
        uint64_t r = UINT64_C(6148914691236517205);
        if (omega_smadd(&r, UINT64_C(4611686018427387904), 4, 0) != 1 ||
            r != UINT64_C(6148914691236517205))
            *failed = 1;
        if (omega_madd(&r, 3, 5, 7) != 0 || r != 22)
            *failed = 1;
        if (omega_smadd(&r, (uint64_t)(int64_t)-3, 5, 2) != 0 || (int64_t)r != -13)
            *failed = 1;
    }
    return NULL;
}

int main(void)
{
    pthread_t threads[4];
    int failed[4] = {0};
    if (pthread_barrier_init(&ready, NULL, 4) != 0)
        return 1;
    for (unsigned i = 0; i < 4; ++i)
        if (pthread_create(&threads[i], NULL, exercise, &failed[i]) != 0)
            return 1;
    for (unsigned i = 0; i < 4; ++i)
        if (pthread_join(threads[i], NULL) != 0 || failed[i])
            return 1;
    if (pthread_barrier_destroy(&ready) != 0)
        return 1;
    puts("PRIVATE-SYMBOLS PASS: distinct bindings, trap recovery and concurrent threads");
    return 0;
}
