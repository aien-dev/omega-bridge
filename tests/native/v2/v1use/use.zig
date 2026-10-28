// Links omega_bsum (the v1 symbol) from the v1 file; against the v2 library this must fail to link.
const om = @import("omega_native.zig");
pub fn main() u8 {
    var r: u64 = 0;
    const d = [_]u8{0} ** 4;
    return @intCast(om.omega_bsum(&r, &d, 4));
}
