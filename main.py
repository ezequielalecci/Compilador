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


PROGRAMA = '''
prueba

uinteger x;
doublef y, res;

auto function prueba_ifs(uinteger a, doublef b)
uinteger aux;
begin
    pout(b);
    aux := toui(b);
    
    if (a > aux) ret(a);
    else 
        begin
            if (a < aux) ret(b);
            else pout({iguales});
            end_if;
        end
    end_if;
end;

BEGIN
    x := 1$ui;
    y := 1.5;
    res := prueba_ifs(x, y);
    pout(res);
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