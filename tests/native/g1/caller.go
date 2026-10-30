// Go caller for the G1 sample calc: reads "i0 i1" lines, prints "i0 i1 status result" per line.
// Every Omega declaration comes from the generated omeganative package; this file has no cgo.
package main

import (
	"bufio"
	"fmt"
	"os"

	on "omegacaller/omeganative"
)

func main() {
	sc := bufio.NewScanner(os.Stdin)
	for sc.Scan() {
		var a, b uint64
		if _, err := fmt.Sscan(sc.Text(), &a, &b); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		var r uint64
		s := on.Omega_calc(&r, a, b)
		fmt.Println(a, b, s, r)
	}
}
