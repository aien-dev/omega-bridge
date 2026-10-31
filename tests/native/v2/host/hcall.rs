// hcall.rs: the Rust oracle for hfile.om through the --host library (tests/native/v2/run.sh, section 11).
// hcall FILE MISSING LINK, as for hcall.c; expectations come from std, independently of the unit.
mod omega_native;
use omega_native::*;
use std::os::unix::fs::MetadataExt;
use std::sync::atomic::{AtomicBool, Ordering};

static BAD: AtomicBool = AtomicBool::new(false);
fn check(what: &str, ok: bool) {
    println!("{} {}", if ok { "PASS" } else { "FAIL" }, what);
    if !ok {
        BAD.store(true, Ordering::Relaxed);
    }
}

fn peek(p: &str) -> Option<i64> {
    let mut r: u64 = 0;
    let s = unsafe { omega2_peek(&mut r, p.as_ptr(), p.len() as u64) };
    if s == OMEGA_OK { Some(r as i64) } else { None }
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    assert!(a.len() == 4, "usage: hcall FILE MISSING LINK");
    check("peek FILE reads its 5 bytes", peek(&a[1]) == Some(5));
    check("peek MISSING = -ENOENT (-2)", peek(&a[2]) == Some(-2));
    check("peek LINK = -ELOOP (-40, fopen with O_NOFOLLOW)", peek(&a[3]) == Some(-40));
    let m = std::fs::metadata(&a[1]).expect("metadata");
    let mut r: u64 = 0;
    let s = unsafe { omega2_size(&mut r, a[1].as_ptr(), a[1].len() as u64) };
    check("size FILE == metadata len", s == OMEGA_OK && r == m.size());
    let p = std::fs::metadata("/proc/self").expect("/proc/self");
    let s = unsafe { omega2_ids(&mut r) };
    check("ids >= euid + egid (from /proc/self)", s == OMEGA_OK && r >= p.uid() as u64 + p.gid() as u64);
    check("ident carries host=", OMEGA2_IDENT_hfile.contains(" host="));
    if BAD.load(Ordering::Relaxed) {
        std::process::exit(1);
    }
}
