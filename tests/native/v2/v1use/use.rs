// Links omega_bsum (the v1 symbol) from the v1 module; against the v2 library this must fail to link.
mod omega_native;
fn main() {
    let mut r: u64 = 0;
    let d = [0u8; 4];
    let s = unsafe { omega_native::omega_bsum(&mut r, d.as_ptr(), 4) };
    std::process::exit(s as i32);
}
