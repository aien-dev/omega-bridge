/* Test-only oracle: CUDApp's unchanged canonical encoder. Never linked into Omega. */
#include "omega_blackwell_codegen.h"
#include <stdio.h>
#include <stdint.h>
#include <string.h>
int main(void) {
    char name[32]; int d,a,b; unsigned imm;
    while (scanf("%31s %d %d %d %u",name,&d,&a,&b,&imm)==5) {
        BlackwellIRInsn in; memset(&in,0,sizeof(in));
        in.dst_vreg=d;in.src1_vreg=a;in.src2_vreg=b;in.src3_vreg=-1;in.ureg=-1;in.imm=imm;
        if (!strcmp(name,"ldc")) in.op=BW_IR_LDC;
        else if (!strcmp(name,"mov")) in.op=BW_IR_MOV_IMM;
        else if (!strcmp(name,"add")) in.op=BW_IR_IADD3;
        else if (!strcmp(name,"mul")) in.op=BW_IR_IMAD;
        else if (!strcmp(name,"muli")) {in.op=BW_IR_IMAD;in.src2_vreg=-1;}
        else if (!strcmp(name,"lop")) in.op=BW_IR_LOP3_LUT;
        else return 65;
        uint32_t words[4]; if(omega_blackwell_encode_one(&in,words)!=0)return 66;
        for(unsigned j=0;j<4;j++)for(unsigned k=0;k<4;k++)if(putchar((words[j]>>(k*8))&255)==EOF)return 77;
    }
    return ferror(stdin)?77:0;
}
