"""
codigo_intermedio.py  -  TP3 (Grupo 19)  -  AVANCE 1 + PASO 2 (sentencias de control)

Representación elegida: TERCETOS      ( operador , operando1 , operando2 )

Temas del grupo que toca este avance:
  - Tema  4 : UINTEGER (constantes $ui)
  - Tema  8 : DOUBLEF
  - Tema 11 : WHILE ... REPEAT
  - Tema 18 : asignaciones con '=' dentro de expresiones (el valor es el LADO IZQUIERDO)
  - Tema 34 : conversión explícita float -> entero (TOUI) y chequeo de tipos asociado
Temas que se agregan en avances siguientes: 21 (AUTO), 22 (COMPTIME), 27 (friend/private),
28 (acceso con '.'), 32 (herencia, ambigüedad = error).
"""

from dataclasses import dataclass
from typing import Optional, Union
from TablaSimbolos import TablaSimbolos

# ----------------------------------------------------------------------------
# Tipos del lenguaje
# ----------------------------------------------------------------------------
UINTEGER = 'UINTEGER'   # tema 4  (entero)
DOUBLEF = 'DOUBLEF'     # tema 8  (flotante)
BOOL = 'BOOL'           # tipo interno: resultado de una comparación
ERROR = 'ERROR'         # tipo interno: evita errores en cascada
TIPOS_BASICOS = {UINTEGER, DOUBLEF}

# Decisión de diseño pendiente (ver preguntas): ¿se permite asignar entero a flotante sin conversión?
# El tema 34 solo EXIGE conversión en el sentido flotante -> entero.
PERMITE_ENTERO_A_FLOAT = False


# ----------------------------------------------------------------------------
# Tabla de símbolos con atributos semánticos (tipo, uso, ámbito)
# ----------------------------------------------------------------------------


# ----------------------------------------------------------------------------
# Errores: se acumulan y se muestran todos juntos al final (lo pide el TP3)
# -------------------class TablaSimbolosSemantica(TablaSimbolos):

class TablaSimbolosSemantica(TablaSimbolos):

    def declarar(self, nombre_interno, tipo, uso, ambito, **extra):
        if self.buscar(nombre_interno, 'ID') is not None:
            return False

        self.registrar(
            nombre_interno,
            'ID',
            tipo=tipo,
            uso=uso,
            ambito=ambito,
            **extra
        )

        return True

    

class Errores:
    def __init__(self):
        self.lista = []

    def semantico(self, linea, mensaje):
        self.lista.append((linea, f"Error Semántico: {mensaje}"))

    def warning(self, linea, mensaje):
        self.lista.append((linea, f"Warning: {mensaje}"))

    def imprimir(self):
        print("\n--- ERRORES / WARNINGS ---")
        if not self.lista:
            print("(sin errores)")
        for linea, msg in sorted(self.lista, key=lambda e: e[0]):
            print(f"Línea {linea}: {msg}")


# ----------------------------------------------------------------------------
# Ámbitos y name mangling
# ----------------------------------------------------------------------------
class GestorAmbitos:
    """
    Mantiene la PILA de ámbitos. Cada símbolo se guarda en la Tabla de Símbolos
    con su nombre + ':' + ámbito completo:
        a declarada en main            ->  a:main
        parámetro x de la función aa   ->  x:main:aa
    Reglas de alcance (enunciado):
      - un símbolo es visible en su ámbito y en los ámbitos contenidos en él
      - mismo nombre permitido en ámbitos distintos, NO en el mismo ámbito
    """

    def __init__(self, tabla, errores, global_='main'):
        self.tabla = tabla
        self.errores = errores
        self.pila = [global_]

    def ambito_actual(self):
        return ':'.join(self.pila)

    def entrar(self, nombre):
        self.pila.append(nombre)

    def salir(self):
        self.pila.pop()

    def declarar(self, nombre, tipo, uso, linea, **extra):
        mangleado = f"{nombre}:{self.ambito_actual()}"

        if self.tabla.buscar(mangleado) is not None:
            self.errores.semantico(
                linea,
                f"'{nombre}' ya está declarado en el ámbito "
                f"'{self.ambito_actual()}' (redeclaración)."
            )
            return None

        self.tabla.registrar(
            mangleado,
            'ID',
            tipo=tipo,
            uso=uso,
            ambito=self.ambito_actual(),
            **extra
        )
        return mangleado

    def resolver(self, nombre, linea):
        """Busca 'nombre' desde el ámbito actual hacia los ámbitos que lo contienen
        (de adentro hacia afuera). Devuelve (nombre_mangleado, info) o (None, None)."""
        for i in range(len(self.pila), 0, -1):
            mangleado = f"{nombre}:{':'.join(self.pila[:i])}"
            info = self.tabla.buscar(mangleado)
            if info is not None:
                return mangleado, info
        self.errores.semantico(linea, f"'{nombre}' no está declarado o no es visible desde el ámbito '{self.ambito_actual()}'.")
        return None, None


# ----------------------------------------------------------------------------
# Tercetos
# ----------------------------------------------------------------------------
@dataclass
class Terceto:
    op: str
    a1: Union[int, str, None] = None   # int -> referencia a otro terceto [n] ; str -> símbolo de la TS
    a2: Union[int, str, None] = None
    tipo: Optional[str] = None         # tipo del resultado (lo vamos a necesitar en el TP4)


def _fmt(x):
    if x is None:
        return '-'
    if isinstance(x, int):
        return f'[{x}]'
    return str(x)


class UnidadCodigo:
    """Una estructura dinámica (lista) de tercetos. Una por el programa principal
    y una por cada función, así los saltos son relativos a su propia numeración."""

    def __init__(self, nombre):
        self.nombre = nombre
        self.tercetos = []

    def emitir(self, op, a1=None, a2=None, tipo=None) -> int:
        self.tercetos.append(Terceto(op, a1, a2, tipo))
        return len(self.tercetos) - 1

    def proximo(self) -> int:
        return len(self.tercetos)

    def completar_salto(self, idx, destino):
        """Backpatching: completa el destino de un salto emitido antes de conocerlo."""
        t = self.tercetos[idx]
        if t.op == 'BI':
            t.a1 = destino
        else:               # BF
            t.a2 = destino

    def imprimir(self):
        print(f"\n=== Código intermedio: {self.nombre} ===")
        for i, t in enumerate(self.tercetos):
            print(f"{i:>3}  ( {t.op} , {_fmt(t.a1)} , {_fmt(t.a2)} )")


# ----------------------------------------------------------------------------
# Operando: lo que devuelve cada expresión (referencia + tipo)
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Operando:
    ref: Union[int, str, None]   # int -> resultado de un terceto ; str -> símbolo/constante de la TS
    tipo: str


ERR = Operando(None, ERROR)


# ----------------------------------------------------------------------------
# Generador de código intermedio
# ----------------------------------------------------------------------------
class GeneradorCodigo:
    def __init__(self, tabla, errores, ambitos):
        self.tabla = tabla
        self.errores = errores
        self.ambitos = ambitos
        self.pila_unidades = [UnidadCodigo('main')]
        self.terminadas = []        # unidades de funciones ya cerradas
        self.pila_control = []      # saltos pendientes de completar (if / while)
        self.pila_funciones = []    # contexto de la función que se está compilando

    @property
    def unidad(self) -> UnidadCodigo:
        return self.pila_unidades[-1]

    # ---------------- operandos ----------------
    def variable(self, nombre, linea) -> Operando:
        mangleado, info = self.ambitos.resolver(nombre, linea)
        if info is None:
            return ERR
        if info.get('uso') not in ('variable', 'parametro'):
            self.errores.semantico(linea, f"'{nombre}' es {info.get('uso')} y se usa como variable.")
            return ERR
        return Operando(mangleado, info['tipo'])

    def constante_ui(self, valor) -> Operando:
        # [PASO 1] CAMBIO: además de armar el operando, deja registrado el TIPO de la
        # constante en la TS (el TP3 pide que las constantes tengan tipo).
        lexema = f"{valor}$ui"          # misma clave que usa el léxico al insertar
        self.tabla.registrar(lexema, 'CONST_UI', tipo=UINTEGER)
        return Operando(lexema, UINTEGER)

    def constante_float(self, lexema) -> Operando:
        # [PASO 1] CAMBIO: igual que arriba. 'lexema' es la clave de la TS (token 'FLOAT').
        self.tabla.registrar(lexema, 'FLOAT', tipo=DOUBLEF)
        return Operando(lexema, DOUBLEF)

    # [PASO 1] NUEVO: declaración de variables llamada desde el parser.
    def declarar_variables(self, tipo, nombres, linea, comptime=False):
        """Registra cada variable en el ámbito actual (con name mangling) con su tipo.
        'comptime' queda guardado como atributo para el avance del tema 22."""
        for nombre in nombres:
            self.ambitos.declarar(nombre, tipo, 'variable', linea, comptime=comptime)
        

    # ---------------- chequeo de tipos (tema 34) ----------------
    def _tipo_resultado(self, t1, t2, linea) -> Optional[str]:
        if t1 not in TIPOS_BASICOS or t2 not in TIPOS_BASICOS:
            self.errores.semantico(linea, f"operación no válida entre '{t1}' y '{t2}'.")
            return None
        if t1 != t2:
            self.errores.semantico(
                linea, f"operandos de tipos distintos ({t1} y {t2}); con el tema 34 hace falta "
                       f"conversión explícita con TOUI.")
            return None
        return t1

    # ---------------- expresiones ----------------
    def operacion(self, op, izq, der, linea) -> Operando:
        """op en {'+','-','*','/'}"""
        if ERROR in (izq.tipo, der.tipo):
            return ERR
        tipo = self._tipo_resultado(izq.tipo, der.tipo, linea)
        if tipo is None:
            return ERR
        return Operando(self.unidad.emitir(op, izq.ref, der.ref, tipo), tipo)

    def negar(self, expr, linea) -> Operando:
        if expr.tipo == ERROR:
            return ERR
        if expr.tipo == UINTEGER:
            self.errores.semantico(linea, "no se puede aplicar signo negativo a un UINTEGER.")
            return ERR
        return Operando(self.unidad.emitir('NEG', expr.ref, None, expr.tipo), expr.tipo)

    def comparacion(self, op, izq, der, linea) -> Operando:
        """op en {'<','<=','>','>=','==','!='}"""
        if ERROR in (izq.tipo, der.tipo):
            return ERR
        if self._tipo_resultado(izq.tipo, der.tipo, linea) is None:
            return ERR
        return Operando(self.unidad.emitir(op, izq.ref, der.ref, BOOL), BOOL)

    def convertir_toui(self, expr, linea) -> Operando:
        """Tema 34: TOUI(expr) convierte DOUBLEF -> UINTEGER."""
        if expr.tipo == ERROR:
            return ERR
        if expr.tipo != DOUBLEF:
            self.errores.semantico(linea, f"TOUI espera una expresión DOUBLEF y recibió {expr.tipo}.")
            return ERR
        return Operando(self.unidad.emitir('TOUI', expr.ref, None, UINTEGER), UINTEGER)

    def asignacion(self, destino, expr, linea) -> Operando:
        """
        Sirve para ':=' (sentencia) y para '=' embebido (tema 18): misma estructura.
        Devuelve el LADO IZQUIERDO como valor de la expresión (corrección pedida:
        antes el parser tomaba el derecho).
        """
        if ERROR in (destino.tipo, expr.tipo):
            return destino
        compatible = destino.tipo == expr.tipo or (
            PERMITE_ENTERO_A_FLOAT and destino.tipo == DOUBLEF and expr.tipo == UINTEGER)
        if not compatible:
            extra = " Usar TOUI(...)." if destino.tipo == UINTEGER and expr.tipo == DOUBLEF else ""
            self.errores.semantico(linea, f"asignación incompatible: destino {destino.tipo}, expresión {expr.tipo}.{extra}")
            return destino
        self.unidad.emitir(':=', destino.ref, expr.ref, destino.tipo)
        return destino

    # ---------------- salida y retorno ----------------
    def salida_expresion(self, expr):
        if expr.tipo != ERROR:
            self.unidad.emitir('POUT', expr.ref, None, expr.tipo)

    def salida_cadena(self, texto):
        # [PASO 1] CAMBIO: el léxico entrega el texto SIN llaves, pero la clave en la TS
        # es el lexema original CON llaves; se reconstruye acá para referenciar la TS.
        lexema_ts = '{' + texto + '}'
        self.unidad.emitir('POUT', lexema_ts, None, 'CADENA')

    def retorno(self, expr, linea):
        if not self.pila_funciones:
            self.errores.semantico(linea, "'ret' fuera de una función.")
            return
        f = self.pila_funciones[-1]
        f['cant_ret'] += 1
        if expr.tipo != ERROR:
            if f['tipo'] == 'AUTO':
                f['tipos_ret'].append(expr.tipo)       # el tipo final se resuelve en el avance de AUTO
            elif f['tipo'] != expr.tipo:
                self.errores.semantico(linea, f"'ret' devuelve {expr.tipo} pero la función '{f['nombre']}' devuelve {f['tipo']}.")
        self.unidad.emitir('RET', expr.ref, None, expr.tipo)

    # ---------------- funciones: una unidad de código por función ----------------
    def iniciar_funcion(self, nombre_mangleado, tipo_retorno):
        self.pila_unidades.append(UnidadCodigo(nombre_mangleado))
        self.pila_funciones.append({'nombre': nombre_mangleado, 'tipo': tipo_retorno,
                                    'cant_ret': 0, 'tipos_ret': []})

    def finalizar_funcion(self, linea):
        info = self.pila_funciones.pop()
        if info['tipo'] == 'AUTO' and info['cant_ret'] == 0:
            self.errores.semantico(linea, f"la función AUTO '{info['nombre']}' debe tener al menos un 'ret'.")
        self.terminadas.append(self.pila_unidades.pop())
        return info

    # ------------------------------------------------------------------
    # [PASO 2 - REVISIÓN] Sentencias de control SIN tercetos LABEL, siguiendo los
    # pasos recomendados por la cátedra.
    #
    # Convención:  DIR_ACTUAL = número del ÚLTIMO terceto emitido.
    #              self.unidad.proximo() = DIR_ACTUAL + 1 = próximo terceto a emitir.

    # pila_control guarda tuplas (tipo, nro_terceto) para detectar desbalances que
    # puedan dejar los errores sintácticos:
    #     ('BF', n)      BF incompleto           ('BI', n)      BI incompleto
    #     ('INICIO', n)  terceto donde empieza la condición de un WHILE
    #
    #   IF (c) A end_if        ->  [cond] BF(c,->fin) [A]  fin:
    #   IF (c) A else B end_if ->  [cond] BF(c,->B) [A] BI(->fin) B: [B]  fin:
    #   WHILE (c) repeat A     ->  ini: [cond] BF(c,->fin) [A] BI(->ini)  fin:
    #
    # OJO: un destino puede ser == len(tercetos) si la sentencia es lo último de la
    # unidad (no hay terceto "siguiente"). En el TP4 ese destino se trata como una
    # etiqueta al final del código de la unidad.
    # ------------------------------------------------------------------d
    def _tope_es(self, *tipos) -> bool:
        return bool(self.pila_control) and self.pila_control[-1][0] in tipos

    # ---------------- IF ----------------
    def if_condicion(self, cond, linea):
        """TERMINA LA CONDICIÓN: 1) crea el BF incompleto  2) apila su número."""
        if cond.tipo not in (BOOL, ERROR):
            self.errores.semantico(linea, "la condición del IF debe ser una comparación.")
        bf = self.unidad.emitir('BF', cond.ref, None)
        self.pila_control.append(('BF', bf))

    def if_else(self):
        """FIN DEL THEN (hay ELSE): 1) desapila el BF  2) crea el BI incompleto
        3) completa el BF con DIR_ACTUAL+2 (= primer terceto del else, justo
        después del BI)  4) apila el BI."""
        if not self._tope_es('BF'):
            return                          # protección ante errores sintácticos
        _, bf = self.pila_control.pop()
        bi = self.unidad.emitir('BI')
        self.unidad.completar_salto(bf, self.unidad.proximo())
        self.pila_control.append(('BI', bi))

    def if_fin(self):
        """FIN DEL IF: desapila el salto pendiente (BI si hubo else, BF si no) y lo
        completa con DIR_ACTUAL+1 (= próximo terceto a emitir)."""
        if not self._tope_es('BF', 'BI'):
            return                          # protección ante errores sintácticos
        _, pendiente = self.pila_control.pop()
        self.unidad.completar_salto(pendiente, self.unidad.proximo())

    # ---------------- WHILE ... REPEAT (tema 11) ----------------
    def while_inicio(self):
        """ANTES DE LA CONDICIÓN: apila el número del terceto donde empieza."""
        self.pila_control.append(('INICIO', self.unidad.proximo()))

    def while_condicion(self, cond, linea):
        """TERMINA LA CONDICIÓN: crea el BF incompleto y apila su número."""
        if cond.tipo not in (BOOL, ERROR):
            self.errores.semantico(linea, "la condición del WHILE debe ser una comparación.")
        bf = self.unidad.emitir('BF', cond.ref, None)
        self.pila_control.append(('BF', bf))

    def while_fin(self):
        """FIN DEL CUERPO: 1) desapila el BF  2) desapila el inicio  3) genera el BI
        al inicio  4) completa el BF con el terceto siguiente al BI."""
        if (len(self.pila_control) < 2 or self.pila_control[-1][0] != 'BF'
                or self.pila_control[-2][0] != 'INICIO'):
            return                          # protección ante errores sintácticos
        _, bf = self.pila_control.pop()
        _, inicio = self.pila_control.pop()
        self.unidad.emitir('BI', inicio)
        self.unidad.completar_salto(bf, self.unidad.proximo())

    def control_pendiente(self):
        """Para depurar: saltos que quedaron sin completar (debería ser lista vacía)."""
        return list(self.pila_control)

    # ---------------- salida ----------------
    def imprimir(self):
        for u in self.terminadas:
            u.imprimir()
        self.unidad.imprimir()


# ----------------------------------------------------------------------------
# Demo manual (sin parser): simula lo que harían las acciones semánticas
# ----------------------------------------------------------------------------
if __name__ == '__main__':
    tabla = TablaSimbolosSemantica()
    errores = Errores()
    amb = GestorAmbitos(tabla, errores)
    gen = GeneradorCodigo(tabla, errores, amb)

    
    amb.declarar('a', UINTEGER, 'variable', 2)
    amb.declarar('b', UINTEGER, 'variable', 2)
    amb.declarar('x', DOUBLEF, 'variable', 3)
    amb.declarar('a', UINTEGER, 'variable', 4)        # ERROR: redeclaración en main

    V = lambda n, l: gen.variable(n, l)
    UI = gen.constante_ui

    # b := a + 2$ui * a;
    t = gen.operacion('+', V('a', 6), gen.operacion('*', UI(2), V('a', 6), 6), 6)
    gen.asignacion(V('b', 6), t, 6)

    # a := b = 3$ui;        (tema 18: asignación embebida, vale el lado izquierdo)
    gen.asignacion(V('a', 7), gen.asignacion(V('b', 7), UI(3), 7), 7)

    # while (a < 10$ui) repeat a := a + 1$ui;
    gen.while_inicio()
    gen.while_condicion(gen.comparacion('<', V('a', 9), UI(10), 9), 9)
    gen.asignacion(V('a', 9), gen.operacion('+', V('a', 9), UI(1), 9), 9)
    gen.while_fin()

    # if (a == 5$ui) pout(a) else b := a end_if;
    gen.if_condicion(gen.comparacion('==', V('a', 11), UI(5), 11), 11)
    gen.salida_expresion(V('a', 11))
    gen.if_else()
    gen.asignacion(V('b', 12), V('a', 12), 12)
    gen.if_fin()

    # a := toui(x) + b;     (tema 34: válido)
    gen.asignacion(V('a', 14), gen.operacion('+', gen.convertir_toui(V('x', 14), 14), V('b', 14), 14), 14)

    # ---- errores a detectar ----
    gen.asignacion(V('a', 16), V('x', 16), 16)                 # UINTEGER := DOUBLEF sin TOUI
    gen.operacion('+', V('a', 17), V('x', 17), 17)             # UINTEGER + DOUBLEF sin TOUI
    V('zzz', 18)                                         # no declarada


        # ---- PRUEBAS DE ÁMBITOS ----

    # Crear ámbito de función suma
    amb.entrar('suma')

    amb.declarar('a', UINTEGER, 'variable', 20)
    amb.declarar('c', DOUBLEF, 'variable', 21)

    # Debe detectar redeclaración dentro de suma
    amb.declarar('a', UINTEGER, 'variable', 22)

    # Acceder a variable local
    V('a', 23)

    # Acceder a variable global
    V('b', 24)

    # Intentar acceder a una variable inexistente
    V('zzz', 25)

    amb.salir()

    # Crear otro ámbito de función resta
    amb.entrar('resta')

    # Puede volver a declarar a porque pertenece a otro ámbito
    amb.declarar('a', UINTEGER, 'variable', 27)

    V('a', 28)

    # No debería acceder a c, que pertenece a suma
    V('c', 29)

    amb.salir()

    gen.imprimir()
    print('Saltos sin completar:', gen.control_pendiente())
    errores.imprimir()
    tabla.imprimir_tabla()