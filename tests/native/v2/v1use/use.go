// Links omega_bsum (the v1 symbol) from the v1 package; against the v2 library this must fail to link.
package main

import (
	"os"
	"unsafe"

	om "omegacaller/omeganative"
)

func main() {
	var r uint64
	d := [4]byte{}
	os.Exit(int(om.Omega_bsum(&r, unsafe.Pointer(&d[0]), 4)))
}
