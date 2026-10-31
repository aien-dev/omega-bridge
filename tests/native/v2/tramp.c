/* tramp.c: the trampoline itself, with no C wrapper between the probe and ombr_enter (a wrapper that saves
 * a callee-saved register for its own use would hide a missing restore). Built with the generated
 * omega_native.c included, so the hidden ombr_enter and ombr_rt_table are in this file. The unit is
 * hand-assembled: it writes every register a unit may write under docs/NATIVE-ABI.md that the caller
 * expects kept (x20..x28, x29, d8..d15), then returns 42 or, for a nonzero first argument, takes the
 * trap entry with code 9 after clobbering x30 as well. The probe sets x20..x28 and d8..d15 to known
 * values and counts, after ombr_enter returns, every one that differs, plus x19 and x29 (its frame). */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include "omega_native.c"

extern const unsigned char tr_clob[];
__asm__(".text\n.balign 4\n.globl tr_clob\n.type tr_clob,%function\ntr_clob:\nhint #34\n"
        "mov x20,#901\nmov x21,#902\nmov x22,#903\nmov x23,#904\nmov x24,#905\nmov x25,#906\nmov x26,#907\n"
        "mov x27,#908\nmov x28,#909\nmov x29,#910\n"
        "mov x9,#911\nfmov d8,x9\nmov x9,#912\nfmov d9,x9\nmov x9,#913\nfmov d10,x9\nmov x9,#914\nfmov d11,x9\n"
        "mov x9,#915\nfmov d12,x9\nmov x9,#916\nfmov d13,x9\nmov x9,#917\nfmov d14,x9\nmov x9,#918\nfmov d15,x9\n"
        "cbnz x0,1f\nmov x0,#42\nret\n"
        "1:\nldr x16,[x7,#16]\nmov x1,#9\nmov x30,#0\nbr x16\n.size tr_clob,.-tr_clob\n");

/* tr_probe(code, args, rt, out, top): ombr_enter's own arguments; returns its status in the low 32 bits
 * and the number of changed registers in the high 32 bits. */
uint64_t tr_probe(const void *code, const uint64_t *args, const ombr_rt *rt, uint64_t *out, void *top);
__asm__(".text\n.balign 4\n.globl tr_probe\n.type tr_probe,%function\ntr_probe:\nhint #34\n"
        "stp x29,x30,[sp,#-160]!\nmov x29,sp\nstp x19,x20,[sp,#16]\nstp x21,x22,[sp,#32]\nstp x23,x24,[sp,#48]\n"
        "stp x25,x26,[sp,#64]\nstp x27,x28,[sp,#80]\nstp d8,d9,[sp,#96]\nstp d10,d11,[sp,#112]\n"
        "stp d12,d13,[sp,#128]\nstp d14,d15,[sp,#144]\n"
        "mov x19,#119\nmov x20,#120\nmov x21,#121\nmov x22,#122\nmov x23,#123\nmov x24,#124\nmov x25,#125\nmov x26,#126\nmov x27,#127\nmov x28,#128\n"
        "mov x9,#108\nfmov d8,x9\nmov x9,#109\nfmov d9,x9\nmov x9,#110\nfmov d10,x9\nmov x9,#111\nfmov d11,x9\nmov x9,#112\nfmov d12,x9\nmov x9,#113\nfmov d13,x9\nmov x9,#114\nfmov d14,x9\nmov x9,#115\nfmov d15,x9\n"
        "bl ombr_enter\nmov w0,w0\nmov x9,#0\n"
        "mov x10,sp\ncmp x29,x10\ncinc x9,x9,ne\n"
        "cmp x19,#119\ncinc x9,x9,ne\ncmp x20,#120\ncinc x9,x9,ne\ncmp x21,#121\ncinc x9,x9,ne\ncmp x22,#122\ncinc x9,x9,ne\ncmp x23,#123\ncinc x9,x9,ne\ncmp x24,#124\ncinc x9,x9,ne\ncmp x25,#125\ncinc x9,x9,ne\ncmp x26,#126\ncinc x9,x9,ne\ncmp x27,#127\ncinc x9,x9,ne\ncmp x28,#128\ncinc x9,x9,ne\n"
        "fmov x10,d8\ncmp x10,#108\ncinc x9,x9,ne\nfmov x10,d9\ncmp x10,#109\ncinc x9,x9,ne\nfmov x10,d10\ncmp x10,#110\ncinc x9,x9,ne\nfmov x10,d11\ncmp x10,#111\ncinc x9,x9,ne\nfmov x10,d12\ncmp x10,#112\ncinc x9,x9,ne\nfmov x10,d13\ncmp x10,#113\ncinc x9,x9,ne\nfmov x10,d14\ncmp x10,#114\ncinc x9,x9,ne\nfmov x10,d15\ncmp x10,#115\ncinc x9,x9,ne\n"
        "orr x0,x0,x9,lsl #32\nldp d14,d15,[sp,#144]\nldp d12,d13,[sp,#128]\nldp d10,d11,[sp,#112]\nldp d8,d9,[sp,#96]\n"
        "ldp x27,x28,[sp,#80]\nldp x25,x26,[sp,#64]\nldp x23,x24,[sp,#48]\nldp x21,x22,[sp,#32]\nldp x19,x20,[sp,#16]\n"
        "ldp x29,x30,[sp],#160\nret\n.size tr_probe,.-tr_probe\n");

static int fails;
static void check(const char *name, int ok)
{
    printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    if (!ok)
        fails++;
}

int main(void)
{
    setvbuf(stdout, 0, _IOLBF, 0);
    unsigned char *stk = aligned_alloc(16, 1u << 16);
    if (!stk)
        return 2;
    void *top = stk + (1u << 16);
    uint64_t a[6] = {0}, v = 7;
    uint64_t pv = tr_probe(tr_clob, a, &ombr_rt_table, &v, top);
    check("tramp: return, x19..x29 and d8..d15 kept", (uint32_t)pv == OMEGA_OK && (pv >> 32) == 0 && v == 42);
    a[0] = 1;
    v = 7;
    pv = tr_probe(tr_clob, a, &ombr_rt_table, &v, top);
    check("tramp: trap 9, x19..x29 and d8..d15 kept", (uint32_t)pv == 9 && (pv >> 32) == 0 && v == 7);
    free(stk);
    printf("%s %d\n", fails ? "TRAMP FAIL" : "TRAMP PASS", fails);
    return fails != 0;
}
