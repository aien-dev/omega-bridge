// Native ABI v2 oracle, Rust (tests/native/v2/run.sh): the generated omega_native.rs only.
mod omega_native;
use omega_native::*;
use std::ptr;

static mut FAILS: u32 = 0;
fn check(name: &str, ok: bool) {
    println!("{} {}", if ok { "PASS" } else { "FAIL" }, name);
    if !ok {
        unsafe { FAILS += 1 };
    }
}
const R0: u64 = 0x5a5a5a5a5a5a5a5a;

fn main() {
    unsafe {
        let mut r: u64;
        let id = std::ffi::CStr::from_ptr(omega2_ident_vec() as *const std::ffi::c_char);
        check("ident vec", id.to_bytes() == OMEGA2_IDENT_vec.as_bytes());
        let abc = [b'a', b'b', b'c'];
        r = R0;
        check("bsum abc = 294", omega2_bsum(&mut r, abc.as_ptr(), 3) == OMEGA_OK && r == 294);
        r = R0;
        check("bsum (NULL, 0) = 0", omega2_bsum(&mut r, ptr::null(), 0) == OMEGA_OK && r == 0);
        r = R0;
        check("bsum (NULL, 1) refused", omega2_bsum(&mut r, ptr::null(), 1) == OMEGA_BAD_ARG && r == R0);
        let raw = [0u64; 2];
        r = R0;
        check(
            "wsum misaligned refused",
            omega2_wsum(&mut r, (raw.as_ptr() as *const u8).add(1) as *const u32, 1) == OMEGA_BAD_ARG && r == R0,
        );
        let w4: [u32; 4] = [1, 2, 3, 0xffffffff];
        r = R0;
        check("wsum = 4294967301", omega2_wsum(&mut r, w4.as_ptr(), 4) == OMEGA_OK && r == 4294967301);
        let mut h: [u16; 8] = [1, 2, 3, 4, 0, 0, 0, 0];
        let hp = h.as_mut_ptr();
        r = R0;
        check("vcopy edit == view refused", omega2_vcopy(&mut r, hp, 4, hp, 4) == OMEGA_BAD_ARG);
        r = R0;
        check("vcopy adjacent accepted", omega2_vcopy(&mut r, hp, 4, hp.add(4), 4) == OMEGA_OK && r == 4 && h[7] == 4);
        let d16 = [0u8; 16];
        r = R0;
        check("#748 golden: vpart o 2^64-2 k 4 traps 3", omega2_vpart(&mut r, d16.as_ptr(), 16, u64::MAX - 1, 4) == 3 && r == R0);
        let mut s8: [u8; 8] = [1, 2, 3, 4, 5, 6, 7, 8];
        let sp = s8.as_mut_ptr();
        r = R0;
        check("swap8 out == view reversed", omega2_swap8(&mut r, sp, 8, sp) == OMEGA_OK && s8 == [8, 7, 6, 5, 4, 3, 2, 1]);
        let mut ho: [u64; 2] = [11, 22];
        r = R0;
        check("halt traps 9, out untouched", omega2_halt(&mut r, ho.as_mut_ptr()) == 9 && ho == [11, 22] && r == R0);
        let mut c = [0u8; 24];
        r = R0;
        check("absorb", omega2_absorb(&mut r, c.as_mut_ptr(), abc.as_ptr(), 3) == OMEGA_OK && c[0] == 38 && c[1] == 1 && c[8] == 3);
        let mut o16 = [0u8; 16];
        r = R0;
        check("digest", omega2_digest(&mut r, c.as_ptr(), o16.as_mut_ptr()) == OMEGA_OK && r == 3 && o16[8] == 38);
        let mut f3 = [0u64; 3];
        r = R0;
        check("fillv", omega2_fillv(&mut r, f3.as_mut_ptr(), 3, 9) == OMEGA_OK && f3 == [9, 9, 9]);
        let l3: [i64; 3] = [-5, 7, -9];
        r = R0;
        check("lsum = -7", omega2_lsum(&mut r, l3.as_ptr(), 3) == OMEGA_OK && r as i64 == -7);
        let mut ok = true;
        for k in 0..100u64 {
            r = R0;
            ok = ok && omega_madd(&mut r, k, 3, 1) == OMEGA_OK && r == 3 * k + 1;
            r = R0;
            ok = ok && omega2_bsum(&mut r, abc.as_ptr(), 3) == OMEGA_OK && r == 294;
        }
        check("interleaved madd (v1) and bsum (v2)", ok);
        let f = FAILS;
        println!("{} {}", if f != 0 { "RS-V2 FAIL" } else { "RS-V2 PASS" }, f);
        std::process::exit(if f != 0 { 1 } else { 0 });
    }
}
