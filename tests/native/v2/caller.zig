// Native ABI v2 oracle, Zig 0.13 (tests/native/v2/run.sh): the generated omega_native.zig only.
const std = @import("std");
const om = @import("omega_native.zig");

var fails: u32 = 0;
fn check(name: []const u8, ok: bool) void {
    std.debug.print("{s} {s}\n", .{ if (ok) "PASS" else "FAIL", name });
    if (!ok) fails += 1;
}
// A pointer one byte past an aligned buffer, typed as the binding's u32 pointer. Zig's own alignment
// check would stop it first; the bridge's refusal is what is tested, so that check is off here.
fn misaligned(r: *u64, raw: *align(8) [16]u8) u32 {
    @setRuntimeSafety(false);
    const mis: [*]const u32 = @ptrFromInt(@intFromPtr(raw) + 1);
    return om.omega2_wsum(r, mis, 1);
}
const R0: u64 = 0x5a5a5a5a5a5a5a5a;

pub fn main() void {
    var r: u64 = R0;
    check("ident vec", std.mem.eql(u8, std.mem.span(om.omega2_ident_vec()), om.OMEGA2_IDENT_vec));
    const abc = [_]u8{ 'a', 'b', 'c' };
    r = R0;
    check("bsum abc = 294", om.omega2_bsum(&r, &abc, 3) == om.OMEGA_OK and r == 294);
    r = R0;
    check("bsum (null, 0) = 0", om.omega2_bsum(&r, null, 0) == om.OMEGA_OK and r == 0);
    r = R0;
    check("bsum (null, 1) refused", om.omega2_bsum(&r, null, 1) == om.OMEGA_BAD_ARG and r == R0);
    var raw align(8) = [_]u8{0} ** 16;
    r = R0;
    check("wsum misaligned refused", misaligned(&r, &raw) == om.OMEGA_BAD_ARG and r == R0);
    const w4 = [_]u32{ 1, 2, 3, 0xffffffff };
    r = R0;
    check("wsum = 4294967301", om.omega2_wsum(&r, &w4, 4) == om.OMEGA_OK and r == 4294967301);
    var h = [_]u16{ 1, 2, 3, 4, 0, 0, 0, 0 };
    r = R0;
    check("vcopy edit == view refused", om.omega2_vcopy(&r, &h, 4, &h, 4) == om.OMEGA_BAD_ARG);
    r = R0;
    check("vcopy adjacent accepted", om.omega2_vcopy(&r, &h, 4, h[4..].ptr, 4) == om.OMEGA_OK and r == 4 and h[7] == 4);
    const d16 = [_]u8{0} ** 16;
    r = R0;
    check("#748 golden: vpart o 2^64-2 k 4 traps 3", om.omega2_vpart(&r, &d16, 16, std.math.maxInt(u64) - 1, 4) == 3 and r == R0);
    var s8 = [_]u8{ 1, 2, 3, 4, 5, 6, 7, 8 };
    r = R0;
    check("swap8 out == view reversed", om.omega2_swap8(&r, &s8, 8, &s8) == om.OMEGA_OK and s8[0] == 8 and s8[7] == 1);
    var ho = [_]u64{ 11, 22 };
    r = R0;
    check("halt traps 9, out untouched", om.omega2_halt(&r, &ho) == 9 and ho[0] == 11 and ho[1] == 22 and r == R0);
    var c = [_]u8{0} ** 24;
    r = R0;
    check("absorb", om.omega2_absorb(&r, &c, &abc, 3) == om.OMEGA_OK and c[0] == 38 and c[1] == 1 and c[8] == 3);
    var o16 = [_]u8{0} ** 16;
    r = R0;
    check("digest", om.omega2_digest(&r, &c, &o16) == om.OMEGA_OK and r == 3 and o16[8] == 38);
    var f3 = [_]u64{0} ** 3;
    r = R0;
    check("fillv", om.omega2_fillv(&r, &f3, 3, 9) == om.OMEGA_OK and f3[0] == 9 and f3[2] == 9);
    const l3 = [_]i64{ -5, 7, -9 };
    r = R0;
    check("lsum = -7", om.omega2_lsum(&r, &l3, 3) == om.OMEGA_OK and @as(i64, @bitCast(r)) == -7);
    var ok = true;
    var k: u64 = 0;
    while (k < 100) : (k += 1) {
        r = R0;
        ok = ok and om.omega_madd(&r, k, 3, 1) == om.OMEGA_OK and r == 3 * k + 1;
        r = R0;
        ok = ok and om.omega2_bsum(&r, &abc, 3) == om.OMEGA_OK and r == 294;
    }
    check("interleaved madd (v1) and bsum (v2)", ok);
    std.debug.print("{s} {d}\n", .{ if (fails != 0) "ZIG-V2 FAIL" else "ZIG-V2 PASS", fails });
    if (fails != 0) std.process.exit(1);
}
