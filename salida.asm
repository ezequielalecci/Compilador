.386
.model flat, stdcall
option casemap :none
include \masm32\include\windows.inc
include \masm32\include\kernel32.inc
include \masm32\include\user32.inc
include \masm32\include\msvcrt.inc
includelib \masm32\lib\kernel32.lib
includelib \masm32\lib\user32.lib
includelib \masm32\lib\msvcrt.lib

.data
_titulo DB "Programa",0
_fmt_ui DB "%u",0
_fmt_f DB "%g",0
_buf DB 400 DUP(0)
_conv32 DD 0
err_mul_ui_msg DB "Error en ejecucion: overflow en producto de enteros.",0
err_mul_f_msg DB "Error en ejecucion: overflow en producto de punto flotante.",0
err_resta_msg DB "Error en ejecucion: resultado negativo en resta de enteros sin signo.",0
err_conv_msg DB "Error en ejecucion: perdida de informacion en conversion de flotante a entero.",0
err_div0_msg DB "Error en ejecucion: division por cero.",0
v_a_main DW 0
v_b_main DW 0
v_x_main DQ 0.0
v_y_main DQ 0.0
v_n_main_doble DW 0
v_a_main_doble DW 0
v_u_main_media DQ 0.0
v_v_main_media DQ 0.0
v_a_main_media DQ 0.0
v_veces_main_saludar DW 0
v_contador_cuenta DW 0
v_contador_paso DW 0
v_k_main_contador_sumar DW 0
v_c_cuenta_main DW 0
v_c_paso_main DW 0
_t0_2 DW 0
_t0_3 DW 0
_t0_8 DQ 0.0
_t0_17 DW 0
_t0_25 DW 0
_t0_29 DW 0
_t1_0 DW 0
_t2_0 DQ 0.0
_t2_1 DQ 0.0
_t4_0 DW 0
_f0 DQ 1.50000000000000000e+00
_f1 DQ 2.50000000000000000e+00
_f2 DQ 2.00000000000000000e+00
_str0 DB 104,111,108,97,32,100,101,115,100,101,32,117,110,97,32,102,117,110,99,105,111,110,0

.code
start:
    finit
    ; [0] ( := , a:main , 5$ui )
    mov ax, 5
    mov v_a_main, ax
    ; [1] ( ARG , a:main , n:main:doble )
    mov ax, v_a_main
    mov v_n_main_doble, ax
    ; [2] ( CALL , doble:main , None )
    call fn_doble_main
    mov _t0_2, ax
    ; [3] ( + , 2 , 1$ui )
    mov ax, _t0_2
    add ax, 1
    mov _t0_3, ax
    ; [4] ( := , b:main , 3 )
    mov ax, _t0_3
    mov v_b_main, ax
    ; [5] ( POUT , b:main , None )
    movzx eax, WORD PTR v_b_main
    invoke wsprintf, addr _buf, addr _fmt_ui, eax
    invoke MessageBox, NULL, addr _buf, addr _titulo, MB_OK
    ; [6] ( ARG , 1.5 , u:main:media )
    fld _f0
    fstp v_u_main_media
    ; [7] ( ARG , 2.5 , v:main:media )
    fld _f1
    fstp v_v_main_media
    ; [8] ( CALL , media:main , None )
    call fn_media_main
    fstp _t0_8
    ; [9] ( := , x:main , 8 )
    fld _t0_8
    fstp v_x_main
    ; [10] ( POUT , x:main , None )
    push DWORD PTR [v_x_main+4]
    push DWORD PTR [v_x_main]
    push offset _fmt_f
    push offset _buf
    call crt_sprintf
    add esp, 16
    invoke MessageBox, NULL, addr _buf, addr _titulo, MB_OK
    ; [11] ( ARG , b:main , veces:main:saludar )
    mov ax, v_b_main
    mov v_veces_main_saludar, ax
    ; [12] ( CALL , saludar:main , None )
    call fn_saludar_main
    ; [13] ( := , c.cuenta:main , 10$ui )
    mov ax, 10
    mov v_c_cuenta_main, ax
    ; [14] ( := , contador.cuenta , c.cuenta:main )
    mov ax, v_c_cuenta_main
    mov v_contador_cuenta, ax
    ; [15] ( := , contador.paso , c.paso:main )
    mov ax, v_c_paso_main
    mov v_contador_paso, ax
    ; [16] ( ARG , 5$ui , k:main:contador:sumar )
    mov ax, 5
    mov v_k_main_contador_sumar, ax
    ; [17] ( CALL , contador.sumar , None )
    call fn_contador_sumar
    mov _t0_17, ax
    ; [18] ( := , c.cuenta:main , contador.cuenta )
    mov ax, v_contador_cuenta
    mov v_c_cuenta_main, ax
    ; [19] ( := , c.paso:main , contador.paso )
    mov ax, v_contador_paso
    mov v_c_paso_main, ax
    ; [20] ( := , a:main , 17 )
    mov ax, _t0_17
    mov v_a_main, ax
    ; [21] ( POUT , a:main , None )
    movzx eax, WORD PTR v_a_main
    invoke wsprintf, addr _buf, addr _fmt_ui, eax
    invoke MessageBox, NULL, addr _buf, addr _titulo, MB_OK
    ; [22] ( POUT , c.cuenta:main , None )
    movzx eax, WORD PTR v_c_cuenta_main
    invoke wsprintf, addr _buf, addr _fmt_ui, eax
    invoke MessageBox, NULL, addr _buf, addr _titulo, MB_OK
L0_23:
    ; [23] ( < , a:main , 20$ui )
    mov ax, v_a_main
    cmp ax, 20
    ; [24] ( BF , 23 , 29 )
    jae L0_29
    ; [25] ( + , a:main , 1$ui )
    mov ax, v_a_main
    add ax, 1
    mov _t0_25, ax
    ; [26] ( := , a:main , 25 )
    mov ax, _t0_25
    mov v_a_main, ax
    ; [27] ( POUT , a:main , None )
    movzx eax, WORD PTR v_a_main
    invoke wsprintf, addr _buf, addr _fmt_ui, eax
    invoke MessageBox, NULL, addr _buf, addr _titulo, MB_OK
    ; [28] ( BI , 23 , None )
    jmp L0_23
L0_29:
    ; [29] ( TOUI , 2.0 , None )
    fld _f2
    fld st(0)
    frndint
    fcomp st(1)
    fstsw ax
    sahf
    jne _err_conv
    fistp DWORD PTR _conv32
    mov eax, _conv32
    cmp eax, 65535
    ja _err_conv
    mov _t0_29, ax
    ; [30] ( := , a:main , 29 )
    mov ax, _t0_29
    mov v_a_main, ax
    ; [31] ( POUT , a:main , None )
    movzx eax, WORD PTR v_a_main
    invoke wsprintf, addr _buf, addr _fmt_ui, eax
    invoke MessageBox, NULL, addr _buf, addr _titulo, MB_OK
    invoke ExitProcess, 0
_err_mul_ui:
    invoke MessageBox, NULL, addr err_mul_ui_msg, addr _titulo, MB_ICONERROR
    invoke ExitProcess, 1
_err_mul_f:
    invoke MessageBox, NULL, addr err_mul_f_msg, addr _titulo, MB_ICONERROR
    invoke ExitProcess, 1
_err_resta:
    invoke MessageBox, NULL, addr err_resta_msg, addr _titulo, MB_ICONERROR
    invoke ExitProcess, 1
_err_conv:
    invoke MessageBox, NULL, addr err_conv_msg, addr _titulo, MB_ICONERROR
    invoke ExitProcess, 1
_err_div0:
    invoke MessageBox, NULL, addr err_div0_msg, addr _titulo, MB_ICONERROR
    invoke ExitProcess, 1
fn_doble_main:
    ; [0] ( + , n:main:doble , n:main:doble )
    mov ax, v_n_main_doble
    add ax, v_n_main_doble
    mov _t1_0, ax
    ; [1] ( := , a:main:doble , 0 )
    mov ax, _t1_0
    mov v_a_main_doble, ax
    ; [2] ( RET , a:main:doble , None )
    mov ax, v_a_main_doble
    ret
    ret
fn_media_main:
    ; [0] ( + , u:main:media , v:main:media )
    fld v_u_main_media
    fadd v_v_main_media
    fstp _t2_0
    ; [1] ( / , 0 , 2.0 )
    fld _t2_0
    fdiv _f2
    fstp _t2_1
    ; [2] ( := , a:main:media , 1 )
    fld _t2_1
    fstp v_a_main_media
    ; [3] ( RET , a:main:media , None )
    fld v_a_main_media
    ret
    ret
fn_saludar_main:
    ; [0] ( POUT , {hola desde una funcion} , None )
    invoke MessageBox, NULL, addr _str0, addr _titulo, MB_OK
    ; [1] ( POUT , veces:main:saludar , None )
    movzx eax, WORD PTR v_veces_main_saludar
    invoke wsprintf, addr _buf, addr _fmt_ui, eax
    invoke MessageBox, NULL, addr _buf, addr _titulo, MB_OK
    ret
fn_contador_sumar:
    ; [0] ( + , contador.cuenta , k:main:contador:sumar )
    mov ax, v_contador_cuenta
    add ax, v_k_main_contador_sumar
    mov _t4_0, ax
    ; [1] ( := , contador.cuenta , 0 )
    mov ax, _t4_0
    mov v_contador_cuenta, ax
    ; [2] ( RET , contador.cuenta , None )
    mov ax, v_contador_cuenta
    ret
    ret
end start
