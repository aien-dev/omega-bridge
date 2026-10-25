/* Generated module owns the ABI declarations and checks. No copied prototype. */
#include "attachment.c"
#include <stdio.h>
int main(void) {
    uint64_t out=0, a[4]={2,3,5,7}; uint8_t b[4]={1,2,254,255};
    if(omega_total(&out,a,4)!=0 || out!=17) return 1;
    if(omega_bump(&out,b,4)!=0 || b[0]!=2 || b[2]!=255 || b[3]!=0) return 2;
    if(omega_narrow(&out,256)!=5) return 3;
    if(omega_divide(&out,9,0)!=2) return 4;
    if(omega_total(&out,a,3)!=8 || omega_total(&out,NULL,4)!=8) return 5;
    if(omega_total(&out,a,4)!=0 || out!=17) return 6;
    if(omega_total(a,a,4)!=8) return 7;
    if(omega_copy(&out,a,4,a,4)!=8) return 8;
    uint64_t src[4]={11,13,17,19};
    if(omega_copy(&out,a,4,src,4)!=0 || a[3]!=19) return 9;
    puts("C caller: values, mutation, traps, invalid lengths and recovery OK");
    return 0;
}
