// Rust caller for examples/deepinfer/flops_pairs.om (no crates). Every Omega declaration comes from the
// generated omega_native.rs; nothing is typed by hand here. Expected values:
// evidence/deepinfer-flops-pairs/wolfram.md.
mod omega_native;
use omega_native::*;

static mut FAILS: u32 = 0;
fn check(name: &str, ok: bool) {
    println!("{} {}", if ok { "PASS" } else { "FAIL" }, name);
    if !ok {
        unsafe { FAILS += 1 };
    }
}

fn call(f: &str, a: &[i64], r: *mut u64) -> u32 {
    let u: Vec<u64> = a.iter().map(|&v| v as u64).collect();
    unsafe {
        match f {
            "floor_prefix" => omega2_floor_prefix(r, u[0], u[1]),
            "capped_prefix" => omega2_capped_prefix(r, u[0], u[1], u[2]),
            _ => omega2_pairs(r, u[0], u[1], u[2], u[3]),
        }
    }
}

fn main() {
    let vs: [(&str, &[i64], u32, i64); 14] = [
        ("floor_prefix", &[9, 2], 0, 20),
        ("capped_prefix", &[9, 2, 3], 0, 18),
        ("pairs", &[3, 9, 2, 3], 0, 16),
        ("pairs", &[3, 9, 2, 0], 0, 18),
        ("pairs", &[0, 4096, 1, 512], 0, 1966336),
        ("floor_prefix", &[3037000499, 1], 0, 4611686016981624750),
        ("capped_prefix", &[4611686018427387904, 1, 2], 0, 9223372036854775807),
        ("floor_prefix", &[3037000500, 1], 1, 0),
        ("capped_prefix", &[4611686018427387905, 1, 2], 1, 0),
        ("capped_prefix", &[0, 4294967296, 2147483648], 1, 0),
        ("floor_prefix", &[-1, 1], 9, 0),
        ("floor_prefix", &[5, 0], 9, 0),
        ("pairs", &[5, 3, 1, 0], 9, 0),
        ("pairs", &[0, 3, 1, -1], 9, 0),
    ];
    const SENTINEL: u64 = 0x5a5a5a5a5a5a5a5a;
    let id = unsafe { std::ffi::CStr::from_ptr(omega2_ident_flops_pairs() as *const std::ffi::c_char) };
    check("ident: library == binding", id.to_bytes() == OMEGA2_IDENT_flops_pairs.as_bytes());
    for (f, a, status, want) in vs.iter() {
        let mut r: u64 = SENTINEL;
        let st = call(f, a, &mut r);
        let ok = st == *status && if st == OMEGA_OK { r as i64 == *want } else { r == SENTINEL };
        check(&format!("{} {:?} -> status {}", f, a, st), ok);
    }
    check("null result refused 32", unsafe { omega2_pairs(std::ptr::null_mut(), 0, 3, 1, 0) } == OMEGA_BAD_ARG);
    std::process::exit(if unsafe { FAILS } == 0 { 0 } else { 1 });
}
