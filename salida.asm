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
_cw_old DW 0
_cw_new DW 0
err_mul_ui_msg DB "Error en ejecucion: overflow en producto de enteros.",0
err_mul_f_msg DB "Error en ejecucion: overflow en producto de punto flotante.",0
err_resta_msg DB "Error en ejecucion: resultado negativo en resta de enteros sin signo.",0
err_conv_msg DB "Error en ejecucion: perdida de informacion en conversion de flotante a entero.",0
err_div0_msg DB "Error en ejecucion: division por cero.",0
v_x_main DW 0
v_res_main DW 0
v_const_main DW 0
v_y_main DQ 0.0
v_afuera_main DQ 0.0
v_resf_main DQ 0.0
v_a_main_retorno_correcto DW 0
v_b_main_retorno_correcto DQ 0.0
v_aux_main_retorno_correcto DW 0
_t0_5 DW 0
_t0_6 DW 0
_t0_11 DQ 0.0
_t1_1 DW 0
_t1_4 DW 0
_f0 DQ 2.70000000000000018e+00
_f1 DQ 5.59999999999999964e+00
_str0 DB 101,115,116,97,32,102,117,110,99,105,111,110,32,110,111,32,116,105,101,110,101,32,114,101,116,111,114,110,111,0

.code
start:
    finit
    ; [0] ( := , x:main , 1$ui )
    mov ax, 1
    mov v_x_main, ax
    ; [1] ( := , y:main , 2.7 )
    fld _f0
    fstp v_y_main
    ; [2] ( := , const:main , 3$ui )
    mov ax, 3
    mov v_const_main, ax
    ; [3] ( ARG , x:main , a:main:retorno_correcto )
    mov ax, v_x_main
    mov v_a_main_retorno_correcto, ax
    ; [4] ( ARG , y:main , b:main:retorno_correcto )
    fld v_y_main
    fstp v_b_main_retorno_correcto
    ; [5] ( CALL , retorno_correcto:main , None )
    call fn_retorno_correcto_main
    mov _t0_5, ax
    ; [6] ( / , 5 , const:main )
    mov ax, _t0_5
    mov bx, v_const_main
    cmp bx, 0
    je _err_div0
    xor dx, dx
    div bx
    mov _t0_6, ax
    ; [7] ( := , res:main , 6 )
    mov ax, _t0_6
    mov v_res_main, ax
    ; [8] ( POUT , res:main , None )
    movzx eax, WORD PTR v_res_main
    invoke wsprintf, addr _buf, addr _fmt_ui, eax
    invoke MessageBox, NULL, addr _buf, addr _titulo, MB_OK
    ; [9] ( CALL , sin_retorno:main , None )
    call fn_sin_retorno_main
    ; [10] ( := , afuera:main , 5.6 )
    fld _f1
    fstp v_afuera_main
    ; [11] ( CALL , retorna_afuera:main , None )
    call fn_retorna_afuera_main
    fstp _t0_11
    ; [12] ( := , resf:main , 11 )
    fld _t0_11
    fstp v_resf_main
    ; [13] ( POUT , resf:main , None )
    push DWORD PTR [v_resf_main+4]
    push DWORD PTR [v_resf_main]
    push offset _fmt_f
    push offset _buf
    call crt_sprintf
    add esp, 16
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
fn_retorno_correcto_main:
    ; [0] ( POUT , b:main:retorno_correcto , None )
    push DWORD PTR [v_b_main_retorno_correcto+4]
    push DWORD PTR [v_b_main_retorno_correcto]
    push offset _fmt_f
    push offset _buf
    call crt_sprintf
    add esp, 16
    invoke MessageBox, NULL, addr _buf, addr _titulo, MB_OK
    ; [1] ( TOUI , b:main:retorno_correcto , None )
    fld v_b_main_retorno_correcto
    fnstcw _cw_old
    mov ax, _cw_old
    or ax, 0C00h
    mov _cw_new, ax
    fldcw _cw_new
    fistp DWORD PTR _conv32
    fldcw _cw_old
    mov eax, _conv32
    cmp eax, 65535
    ja _err_conv
    mov _t1_1, ax
    ; [2] ( := , aux:main:retorno_correcto , 1 )
    mov ax, _t1_1
    mov v_aux_main_retorno_correcto, ax
    ; [3] ( POUT , aux:main:retorno_correcto , None )
    movzx eax, WORD PTR v_aux_main_retorno_correcto
    invoke wsprintf, addr _buf, addr _fmt_ui, eax
    invoke MessageBox, NULL, addr _buf, addr _titulo, MB_OK
    ; [4] ( + , a:main:retorno_correcto , aux:main:retorno_correcto )
    mov ax, v_a_main_retorno_correcto
    add ax, v_aux_main_retorno_correcto
    mov _t1_4, ax
    ; [5] ( RET , 4 , None )
    mov ax, _t1_4
    ret
    ret
fn_sin_retorno_main:
    ; [0] ( POUT , {esta funcion no tiene retorno} , None )
    invoke MessageBox, NULL, addr _str0, addr _titulo, MB_OK
    ret
fn_retorna_afuera_main:
    ; [0] ( RET , afuera:main , None )
    fld v_afuera_main
    ret
    ret
end start
