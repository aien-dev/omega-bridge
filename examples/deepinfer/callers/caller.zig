// Zig 0.13 caller for examples/deepinfer/flops_pairs.om. Every Omega declaration comes from the generated
// omega_native.zig; nothing is typed by hand here. Expected values: evidence/deepinfer-flops-pairs/wolfram.md.
const std = @import("std");
const om = @import("omega_native.zig");

var fails: u32 = 0;
fn check(name: []const u8, ok: bool) void {
    std.debug.print("{s} {s}\n", .{ if (ok) "PASS" else "FAIL", name });
    if (!ok) fails += 1;
}

const Fn = enum { floor_prefix, capped_prefix, pairs };
const V = struct { f: Fn, a: [4]i64, status: u32, want: i64 };

fn call(x: V, r: ?*u64) u32 {
    var u: [4]u64 = undefined;
    for (x.a, 0..) |v, i| u[i] = @bitCast(v);
    return switch (x.f) {
        .floor_prefix => om.omega2_floor_prefix(r, u[0], u[1]),
        .capped_prefix => om.omega2_capped_prefix(r, u[0], u[1], u[2]),
        .pairs => om.omega2_pairs(r, u[0], u[1], u[2], u[3]),
    };
}

pub fn main() void {
    const vs = [_]V{
        .{ .f = .floor_prefix, .a = .{ 9, 2, 0, 0 }, .status = 0, .want = 20 },
        .{ .f = .capped_prefix, .a = .{ 9, 2, 3, 0 }, .status = 0, .want = 18 },
        .{ .f = .pairs, .a = .{ 3, 9, 2, 3 }, .status = 0, .want = 16 },
        .{ .f = .pairs, .a = .{ 3, 9, 2, 0 }, .status = 0, .want = 18 },
        .{ .f = .pairs, .a = .{ 0, 4096, 1, 512 }, .status = 0, .want = 1966336 },
        .{ .f = .floor_prefix, .a = .{ 3037000499, 1, 0, 0 }, .status = 0, .want = 4611686016981624750 },
        .{ .f = .capped_prefix, .a = .{ 4611686018427387904, 1, 2, 0 }, .status = 0, .want = 9223372036854775807 },
        .{ .f = .floor_prefix, .a = .{ 3037000500, 1, 0, 0 }, .status = 1, .want = 0 },
        .{ .f = .capped_prefix, .a = .{ 4611686018427387905, 1, 2, 0 }, .status = 1, .want = 0 },
        .{ .f = .capped_prefix, .a = .{ 0, 4294967296, 2147483648, 0 }, .status = 1, .want = 0 },
        .{ .f = .floor_prefix, .a = .{ -1, 1, 0, 0 }, .status = 9, .want = 0 },
        .{ .f = .floor_prefix, .a = .{ 5, 0, 0, 0 }, .status = 9, .want = 0 },
        .{ .f = .pairs, .a = .{ 5, 3, 1, 0 }, .status = 9, .want = 0 },
        .{ .f = .pairs, .a = .{ 0, 3, 1, -1 }, .status = 9, .want = 0 },
    };
    const sentinel: u64 = 0x5a5a5a5a5a5a5a5a;
    check("ident: library == binding", std.mem.eql(u8, std.mem.span(om.omega2_ident_flops_pairs()), om.OMEGA2_IDENT_flops_pairs));
    var buf: [160]u8 = undefined;
    for (vs) |x| {
        var r: u64 = sentinel;
        const st = call(x, &r);
        const ok = st == x.status and (if (st == om.OMEGA_OK) @as(i64, @bitCast(r)) == x.want else r == sentinel);
        const name = std.fmt.bufPrint(&buf, "{s} {any} -> status {d}", .{ @tagName(x.f), x.a, st }) catch "vector";
        check(name, ok);
    }
    check("null result refused 32", om.omega2_pairs(null, 0, 3, 1, 0) == om.OMEGA_BAD_ARG);
    std.process.exit(if (fails == 0) 0 else 1);
}
