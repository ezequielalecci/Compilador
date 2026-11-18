"""
main.py  -  Compilador Grupo 19: léxico -> sintáctico -> código intermedio (tercetos) -> Assembler

USO
    python main.py <prueba>             compila una prueba (ruta, o nombre dentro de test/)
    python main.py --lista              lista las pruebas disponibles
    python main.py --todas [filtro]     corre todas las pruebas (o las que contengan 'filtro')
                                        y verifica ok_* -> sin errores / err_* -> con errores

    El nombre de la prueba puede abreviarse mientras sea único:
        python main.py ok_uinteger_literales
        python main.py uinteger_negativo

SALIDA (siempre en este orden)
    1. errores y warnings
    2. tercetos de cada unidad (main y funciones)
    3. tabla de símbolos
    Si NO hay errores se genera salida.asm (MASM32) y ensamblar.bat.

OPCIONES PARA ACOTAR LA SALIDA
    --no-errores,  -E     no muestra errores/warnings
    --no-tercetos, -T     no muestra los tercetos
    --no-ts,       -S     no muestra la tabla de símbolos
    --solo X [Y ...]      muestra únicamente lo indicado (errores, tercetos, ts)
    --no-asm              no genera salida.asm ni ensamblar.bat
"""

import argparse
import io
import os
import sys
from contextlib import redirect_stdout

import SintacticoRemasterizado as sintactico
from AnalizadorLexico import AnalizadorLexico
from CodigoIntermedio import (GeneradorCodigo, GestorAmbitos, Errores, TablaSimbolosSemantica)
from GeneradorAssembler import GeneradorAssembler


CARPETA_TEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test')


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def banner(titulo):
    print("=" * 70)
    print(titulo)
    print("=" * 70)


def capturar(funcion):
    """Ejecuta funcion() y devuelve lo que imprimió, sin mostrarlo."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        funcion()
    return buf.getvalue()


def lineas_nuevas(texto, referencia):
    """Líneas de 'texto' que no aparecen ya en 'referencia' (evita duplicados)."""
    vistas = {l.strip() for l in referencia.splitlines()}
    return [l for l in texto.splitlines() if l.strip() and l.strip() not in vistas]


def listar_pruebas():
    if not os.path.isdir(CARPETA_TEST):
        return []
    return sorted(f for f in os.listdir(CARPETA_TEST) if f.endswith('.txt'))


def resolver_prueba(nombre):
    """Acepta una ruta, un nombre exacto, o un fragmento único del nombre."""
    if os.path.isfile(nombre):
        return nombre
    pruebas = listar_pruebas()
    clave = nombre[:-4] if nombre.endswith('.txt') else nombre
    exacta = clave + '.txt'
    if exacta in pruebas:
        return os.path.join(CARPETA_TEST, exacta)
    coincidencias = [p for p in pruebas if clave in p]
    if len(coincidencias) == 1:
        return os.path.join(CARPETA_TEST, coincidencias[0])
    if not coincidencias:
        sys.exit(f"No se encontró la prueba '{nombre}'. Usá --lista para ver las disponibles.")
    sys.exit(f"'{nombre}' es ambiguo, coincide con:\n  " + "\n  ".join(coincidencias))


# --------------------------------------------------------------------------
# Compilación
# --------------------------------------------------------------------------
def compilar(codigo, ver_errores=True, ver_tercetos=True, ver_ts=True,
             generar_asm=True, salida_asm='salida.asm', silencioso=False):
    """Compila 'codigo'. Devuelve True si no hubo errores."""
    sintactico.MOSTRAR_AST = False

    ts = TablaSimbolosSemantica()
    errores = Errores()
    ambitos = GestorAmbitos(ts, errores)
    gen = GeneradorCodigo(ts, errores, ambitos)

    lexer = AnalizadorLexico(ts)
    parser = sintactico.AnalizadorSintactico(ts, gen)

    # El análisis se hace en silencio: lo que imprima el léxico/sintáctico se
    # muestra después, dentro de la sección de errores, para respetar el orden.
    salida_parse = io.StringIO()
    excepcion = None
    try:
        with redirect_stdout(salida_parse):
            parser.parse(lexer.tokenize(codigo))
    except Exception as e:                       # el compilador se rompió
        excepcion = f"{type(e).__name__}: {e}"

    texto_errores = capturar(errores.imprimir)
    hay_errores = (errores.hay_errores() or gen.control_pendiente()
                   or excepcion is not None)

    if not silencioso:
        # 1) ERRORES
        if ver_errores:
            banner(" ERRORES Y WARNINGS")
            extra = lineas_nuevas(salida_parse.getvalue(), texto_errores)
            if excepcion:
                extra.append(f"[EXCEPCIÓN DEL COMPILADOR] {excepcion}")
            if extra:
                print("\n".join(extra))
            if texto_errores.strip():
                print(texto_errores.rstrip())
            if not extra and not texto_errores.strip():
                print("(sin errores ni warnings)")
            print()

        # 2) TERCETOS
        if ver_tercetos:
            banner(" CÓDIGO INTERMEDIO (TERCETOS)")
            gen.imprimir()
            print()

        # 3) TABLA DE SÍMBOLOS
        if ver_ts:
            banner(" TABLA DE SÍMBOLOS")
            ts.imprimir_tabla()
            print()

    if hay_errores:
        if not silencioso:
            print(">>> Hay errores: NO se genera código Assembler.")
        return False

    if not generar_asm:
        if not silencioso:
            print(">>> Sin errores (no se genera Assembler: --no-asm).")
        return True

    if not silencioso:
        banner(" GENERACIÓN DE ASSEMBLER")
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
    if not silencioso:
        print(f"Se generó {ruta} y ensamblar.bat")
    return True


def correr_todas(filtro=''):
    """Corre todas las pruebas; ok_* debe compilar limpio y err_* debe dar error."""
    pruebas = [p for p in listar_pruebas() if filtro in p]
    if not pruebas:
        sys.exit("No hay pruebas que coincidan.")
    fallas = 0
    for p in pruebas:
        with open(os.path.join(CARPETA_TEST, p), encoding='utf-8') as f:
            codigo = f.read()
        esperaba_ok = p.startswith('ok')
        with redirect_stdout(io.StringIO()):
            compilo_ok = compilar(codigo, generar_asm=False, silencioso=True)
        bien = (compilo_ok == esperaba_ok)
        fallas += (not bien)
        print(f"[{'PASA ' if bien else 'FALLA'}] {p[:-4]:<48} "
              f"esperado: {'sin errores' if esperaba_ok else 'con errores':<12} "
              f"obtenido: {'sin errores' if compilo_ok else 'con errores'}")
    print(f"\n{len(pruebas) - fallas}/{len(pruebas)} pruebas se comportaron como se esperaba.")
    return fallas == 0


# --------------------------------------------------------------------------
# Línea de comandos
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Compilador Grupo 19. Por defecto muestra errores, tercetos y tabla de símbolos.")
    ap.add_argument('prueba', nargs='?',
                    help="archivo .txt o nombre de una prueba de test/ (con --todas: filtro)")
    ap.add_argument('-E', '--no-errores', action='store_true', help="oculta errores y warnings")
    ap.add_argument('-T', '--no-tercetos', action='store_true', help="oculta los tercetos")
    ap.add_argument('-S', '--no-ts', action='store_true', help="oculta la tabla de símbolos")
    ap.add_argument('--solo', nargs='+', choices=['errores', 'tercetos', 'ts'],
                    help="muestra únicamente lo indicado")
    ap.add_argument('--no-asm', action='store_true', help="no genera salida.asm ni ensamblar.bat")
    ap.add_argument('-l', '--lista', action='store_true', help="lista las pruebas disponibles")
    ap.add_argument('--todas', action='store_true',
                    help="corre todas las pruebas y verifica el resultado esperado (ok_/err_)")
    a = ap.parse_args()

    if a.lista:
        pruebas = listar_pruebas()
        if not pruebas:
            sys.exit(f"No hay pruebas en {CARPETA_TEST}")
        for p in pruebas:
            print(p[:-4])
        return

    if a.todas:
        sys.exit(0 if correr_todas(a.prueba or '') else 1)

    if not a.prueba:
        ap.print_help()
        print("\nPruebas disponibles (python main.py --lista):")
        for p in listar_pruebas():
            print("  " + p[:-4])
        sys.exit(1)

    ver = {'errores': not a.no_errores, 'tercetos': not a.no_tercetos, 'ts': not a.no_ts}
    if a.solo:
        ver = {k: (k in a.solo) and v for k, v in ver.items()}

    ruta = resolver_prueba(a.prueba)
    with open(ruta, encoding='utf-8') as f:
        codigo = f.read()
    print(f"Prueba: {os.path.relpath(ruta)}\n")
    ok = compilar(codigo, ver['errores'], ver['tercetos'], ver['ts'],
                  generar_asm=not a.no_asm)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()