// Go caller (cgo) for the omega-bridge native call ABI v1 test library.
// Run with Go 1.27.3 (cgo) by tests/native/run.sh (10 checks).
package main

/*
#cgo LDFLAGS: -L${SRCDIR} -lomega_native -Wl,-rpath,${SRCDIR}
#include <stdint.h>
#include <stdlib.h>
uint32_t omega_madd(uint64_t *result, uint64_t a, uint64_t b, uint64_t c);
uint32_t omega_smadd(uint64_t *result, uint64_t a, uint64_t b, uint64_t c);
uint32_t omega_fill(uint64_t *result, void *buf, uint64_t buf_len, uint64_t k);
*/
import "C"

import (
	"fmt"
	"os"
	"unsafe"
)

var fails int

func check(name string, ok bool) {
	if ok {
		fmt.Println("PASS", name)
	} else {
		fmt.Println("FAIL", name)
		fails++
	}
}

func main() {
	const sentinel = uint64(6148914691236517205)
	var r C.uint64_t
	check("madd 3*5+7 = 22", C.omega_madd(&r, 3, 5, 7) == 0 && r == 22)
	check("madd wraps = 3", C.omega_madd(&r, C.uint64_t(^uint64(0)), 2, 5) == 0 && r == 3)
	check("madd large", C.omega_madd(&r, 1311768467463790320, 18364758544493064720, 1085102592571150095) == 0 && r == 3637949782307626511)
	m3 := int64(-3)
	check("madd signed bits = -13", C.omega_madd(&r, C.uint64_t(uint64(m3)), 5, 2) == 0 && int64(r) == -13)
	r = C.uint64_t(sentinel)
	check("smadd overflow traps 1, result unchanged", C.omega_smadd(&r, 1<<62, 4, 0) == 1 && uint64(r) == sentinel)
	buf := (*[4]C.uint64_t)(C.malloc(32)) // C memory: the call may not hold Go pointers past its return
	defer C.free(unsafe.Pointer(buf))
	*buf = [4]C.uint64_t{}
	check("fill k=1 traps 3, result unchanged", C.omega_fill(&r, unsafe.Pointer(buf), 4, 1) == 3 && uint64(r) == sentinel)
	check("writes before the trap stay visible", buf[0] == 11 && buf[1] == 22 && buf[2] == 0)
	check("fill k=0 = 3", C.omega_fill(&r, unsafe.Pointer(buf), 4, 0) == 0 && r == 3 && buf[2] == 33)
	check("null result refused 32", C.omega_madd(nil, 3, 5, 7) == 32)
	if fails > 0 {
		fmt.Println("FAIL", fails, "failure(s)")
		os.Exit(1)
	}
	fmt.Println("PASS 0 failure(s)")
}
