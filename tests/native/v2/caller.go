// Native ABI v2 oracle, Go (tests/native/v2/run.sh): the generated package omeganative only.
package main

import (
	"fmt"
	"os"
	"unsafe"

	om "omegacaller/omeganative"
)

var fails int

func check(name string, ok bool) {
	if ok {
		fmt.Println("PASS " + name)
	} else {
		fmt.Println("FAIL " + name)
		fails++
	}
}

const R0 uint64 = 0x5a5a5a5a5a5a5a5a

// Arrays passed to Omega must hold no Go pointers; these live outside the Go heap's pointer rules.
func main() {
	var r uint64
	check("ident vec", om.Omega2_ident_vec() == om.Omega2Ident_vec)
	abc := [3]byte{'a', 'b', 'c'}
	r = R0
	check("bsum abc = 294", om.Omega2_bsum(&r, unsafe.Pointer(&abc[0]), 3) == om.OmegaOK && r == 294)
	r = R0
	check("bsum (nil, 0) = 0", om.Omega2_bsum(&r, nil, 0) == om.OmegaOK && r == 0)
	r = R0
	check("bsum (nil, 1) refused", om.Omega2_bsum(&r, nil, 1) == om.OmegaBadArg && r == R0)
	raw := [2]uint64{}
	r = R0
	check("wsum misaligned refused", om.Omega2_wsum(&r, unsafe.Add(unsafe.Pointer(&raw[0]), 1), 1) == om.OmegaBadArg && r == R0)
	w4 := [4]uint32{1, 2, 3, 0xffffffff}
	r = R0
	check("wsum = 4294967301", om.Omega2_wsum(&r, unsafe.Pointer(&w4[0]), 4) == om.OmegaOK && r == 4294967301)
	h := [8]uint16{1, 2, 3, 4}
	r = R0
	check("vcopy edit == view refused", om.Omega2_vcopy(&r, unsafe.Pointer(&h[0]), 4, unsafe.Pointer(&h[0]), 4) == om.OmegaBadArg)
	r = R0
	check("vcopy adjacent accepted", om.Omega2_vcopy(&r, unsafe.Pointer(&h[0]), 4, unsafe.Pointer(&h[4]), 4) == om.OmegaOK && r == 4 && h[7] == 4)
	d16 := [16]byte{}
	r = R0
	check("#748 golden: vpart o 2^64-2 k 4 traps 3", om.Omega2_vpart(&r, unsafe.Pointer(&d16[0]), 16, ^uint64(0)-1, 4) == 3 && r == R0)
	s8 := [8]byte{1, 2, 3, 4, 5, 6, 7, 8}
	r = R0
	check("swap8 out == view reversed", om.Omega2_swap8(&r, unsafe.Pointer(&s8[0]), 8, unsafe.Pointer(&s8[0])) == om.OmegaOK && s8 == [8]byte{8, 7, 6, 5, 4, 3, 2, 1})
	ho := [2]uint64{11, 22}
	r = R0
	check("halt traps 9, out untouched", om.Omega2_halt(&r, unsafe.Pointer(&ho[0])) == 9 && ho == [2]uint64{11, 22} && r == R0)
	c := [24]byte{}
	r = R0
	check("absorb", om.Omega2_absorb(&r, unsafe.Pointer(&c[0]), unsafe.Pointer(&abc[0]), 3) == om.OmegaOK && c[0] == 38 && c[1] == 1 && c[8] == 3)
	o16 := [16]byte{}
	r = R0
	check("digest", om.Omega2_digest(&r, unsafe.Pointer(&c[0]), unsafe.Pointer(&o16[0])) == om.OmegaOK && r == 3 && o16[8] == 38)
	f3 := [3]uint64{}
	r = R0
	check("fillv", om.Omega2_fillv(&r, unsafe.Pointer(&f3[0]), 3, 9) == om.OmegaOK && f3 == [3]uint64{9, 9, 9})
	l3 := [3]int64{-5, 7, -9}
	r = R0
	check("lsum = -7", om.Omega2_lsum(&r, unsafe.Pointer(&l3[0]), 3) == om.OmegaOK && int64(r) == -7)
	ok := true
	for k := uint64(0); k < 100; k++ {
		r = R0
		ok = ok && om.Omega_madd(&r, k, 3, 1) == om.OmegaOK && r == 3*k+1
		r = R0
		ok = ok && om.Omega2_bsum(&r, unsafe.Pointer(&abc[0]), 3) == om.OmegaOK && r == 294
	}
	check("interleaved madd (v1) and bsum (v2)", ok)
	if fails != 0 {
		fmt.Printf("GO-V2 FAIL %d\n", fails)
		os.Exit(1)
	}
	fmt.Println("GO-V2 PASS 0")
}
