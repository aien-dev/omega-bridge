// Zig caller for the omega-bridge native call ABI v1 test library. Written against Zig 0.13;
// NOT_RUN so far: no Zig toolchain on the qualification host.
const std = @import("std");
extern fn omega_madd(result: ?*u64, a: u64, b: u64, c: u64) u32;
extern fn omega_smadd(result: ?*u64, a: u64, b: u64, c: u64) u32;
extern fn omega_fill(result: ?*u64, buf: ?*anyopaque, buf_len: u64, k: u64) u32;

var fails: u32 = 0;
fn check(name: []const u8, ok: bool) void {
    std.debug.print("{s} {s}\n", .{ if (ok) "PASS" else "FAIL", name });
    if (!ok) fails += 1;
}

pub fn main() void {
    const sentinel: u64 = 6148914691236517205;
    var r: u64 = 0;
    check("madd 3*5+7 = 22", omega_madd(&r, 3, 5, 7) == 0 and r == 22);
    check("madd wraps = 3", omega_madd(&r, std.math.maxInt(u64), 2, 5) == 0 and r == 3);
    check("madd large", omega_madd(&r, 1311768467463790320, 18364758544493064720, 1085102592571150095) == 0 and r == 3637949782307626511);
    check("madd signed bits = -13", omega_madd(&r, @bitCast(@as(i64, -3)), 5, 2) == 0 and @as(i64, @bitCast(r)) == -13);
    r = sentinel;
    check("smadd overflow traps 1, result unchanged", omega_smadd(&r, 1 << 62, 4, 0) == 1 and r == sentinel);
    var buf = [_]u64{ 0, 0, 0, 0 };
    check("fill k=1 traps 3, result unchanged", omega_fill(&r, &buf, 4, 1) == 3 and r == sentinel);
    check("writes before the trap stay visible", buf[0] == 11 and buf[1] == 22 and buf[2] == 0);
    check("fill k=0 = 3", omega_fill(&r, &buf, 4, 0) == 0 and r == 3 and buf[2] == 33);
    check("null result refused 32", omega_madd(null, 3, 5, 7) == 32);
    std.debug.print("{s} {d} failure(s)\n", .{ if (fails > 0) "FAIL" else "PASS", fails });
    std.process.exit(if (fails > 0) 1 else 0);
}
