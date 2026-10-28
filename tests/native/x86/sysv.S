/* SysV AMD64 callee-save oracle. Takes code, result, and two integer slots.
 * This is a foreign caller test, not the bridge implementation. */
.text
.globl x86_sysv_probe
.type x86_sysv_probe,@function
x86_sysv_probe:
    pushq %rbx
    pushq %rbp
    pushq %r12
    pushq %r13
    pushq %r14
    pushq %r15
    movq %rdi, %r10
    movq %rsi, %rdi
    movq %rdx, %rsi
    movq %rcx, %rdx
    subq $8, %rsp
    movq $0x12345671, %rbx
    movq $0x12345672, %rbp
    movq $0x12345673, %r12
    movq $0x12345674, %r13
    movq $0x12345675, %r14
    movq $0x12345676, %r15
    call *%r10
    cmpq $0x12345671, %rbx
    jne .Lbad
    cmpq $0x12345672, %rbp
    jne .Lbad
    cmpq $0x12345673, %r12
    jne .Lbad
    cmpq $0x12345674, %r13
    jne .Lbad
    cmpq $0x12345675, %r14
    jne .Lbad
    cmpq $0x12345676, %r15
    jne .Lbad
    jmp .Ldone
.Lbad:
    movl $99, %eax
.Ldone:
    addq $8, %rsp
    popq %r15
    popq %r14
    popq %r13
    popq %r12
    popq %rbp
    popq %rbx
    ret
.size x86_sysv_probe, .-x86_sysv_probe
.section .note.GNU-stack,"",@progbits
