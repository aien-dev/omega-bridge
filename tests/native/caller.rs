// Rust caller for the omega-bridge native call ABI v1 test library (no crates).
#[link(name = "omega_native")]
extern "C" {
    fn omega_madd(result: *mut u64, a: u64, b: u64, c: u64) -> u32;
    fn omega_smadd(result: *mut u64, a: u64, b: u64, c: u64) -> u32;
    fn omega_fill(result: *mut u64, buf: *mut u64, buf_len: u64, k: u64) -> u32;
}

fn main() {
    const SENTINEL: u64 = 6148914691236517205;
    let mut fails = 0;
    let mut check = |name: &str, ok: bool| {
        println!("{} {}", if ok { "PASS" } else { "FAIL" }, name);
        if !ok {
            fails += 1;
        }
    };
    let mut r: u64 = 0;
    unsafe {
        check("madd 3*5+7 = 22", omega_madd(&mut r, 3, 5, 7) == 0 && r == 22);
        check("madd wraps = 3", omega_madd(&mut r, u64::MAX, 2, 5) == 0 && r == 3);
        check("madd large", omega_madd(&mut r, 1311768467463790320, 18364758544493064720, 1085102592571150095) == 0
            && r == 3637949782307626511);
        check("madd signed bits = -13", omega_madd(&mut r, (-3i64) as u64, 5, 2) == 0 && r as i64 == -13);
        r = SENTINEL;
        check("smadd overflow traps 1, result unchanged", omega_smadd(&mut r, 1u64 << 62, 4, 0) == 1 && r == SENTINEL);
        let mut buf = [0u64; 4];
        check("fill k=1 traps 3, result unchanged", omega_fill(&mut r, buf.as_mut_ptr(), 4, 1) == 3 && r == SENTINEL);
        check("writes before the trap stay visible", buf == [11, 22, 0, 0]);
        check("fill k=0 = 3", omega_fill(&mut r, buf.as_mut_ptr(), 4, 0) == 0 && r == 3 && buf == [11, 22, 33, 0]);
        check("null result refused 32", omega_madd(std::ptr::null_mut(), 3, 5, 7) == 32);
    }
    println!("{} {} failure(s)", if fails > 0 { "FAIL" } else { "PASS" }, fails);
    std::process::exit(if fails > 0 { 1 } else { 0 });
}
