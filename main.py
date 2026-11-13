"""
main.py  -  Compilador Grupo 19: léxico -> sintáctico -> código intermedio (tercetos) -> Assembler

USO
    python main.py                  compila el programa de la variable PROGRAMA (abajo)
    python main.py mi_programa.txt  compila el programa que está en ese archivo

SALIDA
    - tercetos de cada unidad (main y funciones), errores/warnings y tabla de símbolos
    - si NO hay errores: salida.asm  (MASM32)  y  ensamblar.bat  (ensambla y enlaza)
"""

import sys
import SintacticoRemasterizado as sintactico
from AnalizadorLexico import AnalizadorLexico
from CodigoIntermedio import (GeneradorCodigo, GestorAmbitos, Errores, TablaSimbolosSemantica)
from GeneradorAssembler import GeneradorAssembler

# ----------------------------------------------------------------------------
# PEGÁ ACÁ TU PROGRAMA DE PRUEBA
# ----------------------------------------------------------------------------
PROGRAMA = '''
prueba_completa
UINTEGER a, b;
DOUBLEF x, y;

UINTEGER FUNCTION doble(UINTEGER n)
UINTEGER a;
BEGIN
    a := (n + n);
    ret(a);
END;

AUTO FUNCTION media(DOUBLEF u, DOUBLEF v)
DOUBLEF a;
BEGIN
    a := (u + v) / 2.0;
    ret(a);
END;

FUNCTION saludar(UINTEGER veces)
BEGIN
    pout({hola desde una funcion});
    pout(veces);
END;

CLASS contador BEGIN
    UINTEGER cuenta;
    PRIVATE UINTEGER paso;
    UINTEGER FUNCTION sumar(UINTEGER k)
    BEGIN
        cuenta := cuenta + k;
        ret(cuenta);
    END;
END;

contador c;

BEGIN
    a := 5$ui;
    b := doble(a) + 1$ui;
    pout(b);

    x := media(1.5, 2.5);
    pout(x);

    saludar(b);

    c.cuenta := 10$ui;
    a := c.sumar(5$ui);
    pout(a);
    pout(c.cuenta);

    while (a < 20$ui) repeat
    begin
        a := a + 1$ui;
        pout(a);
    end;

    a := toui(2.0);
    pout(a);
END
'''


def compilar(codigo, salida_asm='salida.asm'):
    sintactico.MOSTRAR_AST = False

    ts = TablaSimbolosSemantica()
    errores = Errores()
    ambitos = GestorAmbitos(ts, errores)
    gen = GeneradorCodigo(ts, errores, ambitos)

    lexer = AnalizadorLexico(ts)
    parser = sintactico.AnalizadorSintactico(ts, gen)

    print("=" * 70)
    print(" ANÁLISIS LÉXICO + SINTÁCTICO + SEMÁNTICO")
    print("=" * 70)
    parser.parse(lexer.tokenize(codigo))

    print("\n" + "=" * 70)
    print(" CÓDIGO INTERMEDIO (TERCETOS)")
    print("=" * 70)
    gen.imprimir()
    print('\nSaltos sin completar (debe ser []):', gen.control_pendiente())

    errores.imprimir()
    ts.imprimir_tabla()

    if errores.hay_errores() or gen.control_pendiente():
        print(">>> Hay errores: NO se genera código Assembler.")
        return False

    print("=" * 70)
    print(" GENERACIÓN DE ASSEMBLER")
    print("=" * 70)
    ruta = GeneradorAssembler(ts, gen).generar(salida_asm)
    base = ruta.rsplit('.', 1)[0]
    with open('ensamblar.bat', 'w') as f:
        f.write('@echo off\n')
        f.write(f'\\masm32\\bin\\ml /c /coff {base}.asm\n')
        f.write('if errorlevel 1 goto fin\n')
        f.write(f'\\masm32\\bin\\link /SUBSYSTEM:WINDOWS /LIBPATH:\\masm32\\lib {base}.obj\n')
        f.write('if errorlevel 1 goto fin\n')
        f.write(f'{base}.exe\n')
        f.write(':fin\npause\n')
    print(f"Se generó {ruta} y ensamblar.bat")
    return True


if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding='utf-8') as f:
            codigo = f.read()
    else:
        codigo = PROGRAMA
    compilar(codigo)