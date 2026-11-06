"""
CodigoIntermedio.py  -  TP3 (Grupo 19)  -  generación de código intermedio con TERCETOS

Representación elegida: TERCETOS      ( operador , operando1 , operando2 )

=====================================================================================
REGISTRO DE CAMBIOS
=====================================================================================
[AVANCE 1]  Infraestructura base: tercetos, ámbitos con name mangling, atributos
            semánticos en la TS, chequeo de tipos del tema 34, expresiones, asignación
            (tema 18), IF, WHILE (tema 11), POUT, RET.

[PASO 2 - REVISIÓN]  (reconstruido a partir de lo descripto en AnalizadorSintactico.py)
  - Sin tercetos LABEL: los destinos de salto son NÚMEROS DE TERCETO.
        IF (c) A end_if          ->  c ; BF c,->fin ; A
        IF (c) A else B end_if   ->  c ; BF c,->B ; A ; BI ->fin ; B
        WHILE (c) repeat A       ->  [ini:] c ; BF c,->fin ; A ; BI ->ini
  - control_pendiente(): lista de saltos todavía sin completar (debe quedar []).

[PASO 3]  Funciones, invocaciones, retornos y AUTO (tema 21)
  - VOID: nuevo tipo interno (resultado de invocar una función sin tipo de retorno).
  - Operando: nuevo campo 'linea' (se usa para informar errores desde reglas que no
    tienen terminales, como  factor : invocacion_funcion).
  - Errores.sintactico(): errores estructurales que detecta el parser (ej: función sin
    parámetros, falta de ret en AUTO) pero que se muestran junto con los demás.
  - iniciar_funcion / declarar_parametros / finalizar_funcion:
        * la función se declara en el ámbito que la contiene      (aa:main)
        * se entra a su ámbito: sus parámetros y locales quedan   (x:main:aa)
        * cada función tiene su PROPIA estructura de tercetos (UnidadCodigo)
  - retorno(): chequea el tipo del ret contra el tipo de la función (reglas del tema 34);
    AUTO acumula los tipos devueltos.
  - Retorno por defecto: toda función no-AUTO termina con un RET por defecto
    (enunciado: "se asumirá un valor de retorno por defecto del tipo devuelto").
  - AUTO (tema 21): el tipo de la función es el MÁS ABARCATIVO de sus retornos
    (DOUBLEF si alguno es DOUBLEF; si no, UINTEGER). Se fija al terminar de compilarla.
  - invocacion(): chequea que exista, que sea función, cantidad de parámetros y
    compatibilidad de tipos; genera la COPIA de cada real sobre su formal (pasaje por
    copia, en orden) y luego el terceto CALL.
  - valor_invocacion(): una función VOID no puede usarse dentro de una expresión.
=====================================================================================
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
VOID = 'VOID'           # [PASO 3] tipo interno: función sin retorno
ERROR = 'ERROR'         # tipo interno: evita errores en cascada
AUTO = 'AUTO'           # [PASO 3] tipo declarado de las funciones AUTO (tema 21)
TIPOS_BASICOS = {UINTEGER, DOUBLEF}

# Decisión de diseño pendiente: ¿se permite asignar entero a flotante sin conversión?
# El tema 34 solo EXIGE conversión en el sentido flotante -> entero.
PERMITE_ENTERO_A_FLOAT = False


# ----------------------------------------------------------------------------
# Tabla de símbolos con atributos semánticos (tipo, uso, ámbito)
# ----------------------------------------------------------------------------
class TablaSimbolosSemantica(TablaSimbolos):
    """
    Extiende la TablaSimbolos del TP1 sin tocarla. El TP3 pide agregar a cada
    entrada: TIPO y USO (variable, función, parámetro, clase, ...), y otros
    atributos que el compilador necesite (ámbito, tipo de retorno, parámetros, etc.).
    """

    def registrar(self, lexema, token, **atributos):
        self.insertar(lexema, token)
        self._simbolos[(str(lexema), token)].update(atributos)

    def buscar(self, lexema, token='ID'):
        return self._simbolos.get((str(lexema), token))

    def imprimir_tabla(self):
        ancho = 110
        print("\n" + "=" * ancho)
        print(f"{'TABLA DE SÍMBOLOS':^{ancho}}")
        print("=" * ancho)
        print(f"{'LEXEMA':<28} | {'TOKEN':<12} | {'TIPO':<10} | {'USO':<10} | DETALLE")
        print("-" * ancho)
        for s in self._simbolos.values():
            if s.get('uso') == 'funcion':
                # [PASO 3] las funciones muestran sus parámetros formales (nombre mangleado:tipo)
                formales = ', '.join(f"{n}:{t}" for n, t in s.get('parametros', []))
                detalle = f"parametros=[{formales}]"
            else:
                detalle = str(s['valor']) if s['valor'] is not None else '-'
                if s.get('comptime'):
                    detalle += ' (comptime)'
            print(f"{s['lexema']:<28} | {s['token']:<12} | {str(s.get('tipo') or '-'):<10} | "
                  f"{str(s.get('uso') or '-'):<10} | {detalle}")
        print("=" * ancho + "\n")


# ----------------------------------------------------------------------------
# Errores: se acumulan y se muestran todos juntos al final (lo pide el TP3)
# ----------------------------------------------------------------------------
class Errores:
    def __init__(self):
        self.lista = []

    def semantico(self, linea, mensaje):
        self.lista.append((linea, f"Error Semántico: {mensaje}"))

    # [PASO 3] NUEVO: errores estructurales detectados por el parser.
    def sintactico(self, linea, mensaje):
        self.lista.append((linea, f"Error Sintáctico: {mensaje}"))

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
        la función aa (declarada en main) ->  aa:main
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

    def declarar(self, nombre, tipo, uso, linea, **extra) -> Optional[str]:
        """Registra un símbolo en el ámbito ACTUAL. Devuelve el nombre mangleado
        o None si ya existía en ese mismo ámbito (redeclaración)."""
        mangleado = f"{nombre}:{self.ambito_actual()}"
        if self.tabla.buscar(mangleado) is not None:
            self.errores.semantico(linea, f"'{nombre}' ya está declarado en el ámbito '{self.ambito_actual()}' (redeclaración).")
            return None
        self.tabla.registrar(mangleado, 'ID', tipo=tipo, uso=uso, ambito=self.ambito_actual(), **extra)
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
        """Número del próximo terceto que se va a emitir (destino de un salto hacia adelante)."""
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
    linea: int = 0               # [PASO 3] línea donde se originó (para informar errores)


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
        self._n_sin_nombre = 0      # [PASO 3] contador para funciones/parámetros sin nombre

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
        return Operando(mangleado, info['tipo'], linea)

    def constante_ui(self, valor) -> Operando:
        # Además de armar el operando, deja registrado el TIPO de la constante en la TS
        # (el TP3 pide que las constantes tengan tipo).
        lexema = f"{valor}$ui"          # misma clave que usa el léxico al insertar
        self.tabla.registrar(lexema, 'CONST_UI', tipo=UINTEGER)
        return Operando(lexema, UINTEGER)

    def constante_float(self, lexema) -> Operando:
        # 'lexema' es la clave de la TS (token 'FLOAT').
        self.tabla.registrar(lexema, 'FLOAT', tipo=DOUBLEF)
        return Operando(lexema, DOUBLEF)

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

    # [PASO 3] NUEVO: regla única de compatibilidad "lado derecho -> lado izquierdo".
    # La usan la asignación, el ret y el pasaje de parámetros (el enunciado dice que en
    # los parámetros se aplican las reglas de los temas 33/34/35 como en las asignaciones).
    def _compatible(self, destino, origen) -> bool:
        return destino == origen or (
            PERMITE_ENTERO_A_FLOAT and destino == DOUBLEF and origen == UINTEGER)

    @staticmethod
    def _pista_conversion(destino, origen) -> str:
        return " Usar TOUI(...)." if destino == UINTEGER and origen == DOUBLEF else ""

    # ---------------- expresiones ----------------
    def operacion(self, op, izq, der, linea) -> Operando:
        """op en {'+','-','*','/'}"""
        if ERROR in (izq.tipo, der.tipo):
            return ERR
        tipo = self._tipo_resultado(izq.tipo, der.tipo, linea)
        if tipo is None:
            return ERR
        return Operando(self.unidad.emitir(op, izq.ref, der.ref, tipo), tipo, linea)

    def negar(self, expr, linea) -> Operando:
        if expr.tipo == ERROR:
            return ERR
        if expr.tipo == UINTEGER:
            self.errores.semantico(linea, "no se puede aplicar signo negativo a un UINTEGER.")
            return ERR
        return Operando(self.unidad.emitir('NEG', expr.ref, None, expr.tipo), expr.tipo, linea)

    def comparacion(self, op, izq, der, linea) -> Operando:
        """op en {'<','<=','>','>=','==','!='}"""
        if ERROR in (izq.tipo, der.tipo):
            return ERR
        if self._tipo_resultado(izq.tipo, der.tipo, linea) is None:
            return ERR
        return Operando(self.unidad.emitir(op, izq.ref, der.ref, BOOL), BOOL, linea)

    def convertir_toui(self, expr, linea) -> Operando:
        """Tema 34: TOUI(expr) convierte DOUBLEF -> UINTEGER."""
        if expr.tipo == ERROR:
            return ERR
        if expr.tipo != DOUBLEF:
            self.errores.semantico(linea, f"TOUI espera una expresión DOUBLEF y recibió {expr.tipo}.")
            return ERR
        return Operando(self.unidad.emitir('TOUI', expr.ref, None, UINTEGER), UINTEGER, linea)

    def asignacion(self, destino, expr, linea) -> Operando:
        """
        Sirve para ':=' (sentencia) y para '=' embebido (tema 18): misma estructura.
        Devuelve el LADO IZQUIERDO como valor de la expresión.
        """
        if ERROR in (destino.tipo, expr.tipo):
            return destino
        if not self._compatible(destino.tipo, expr.tipo):
            self.errores.semantico(
                linea, f"asignación incompatible: destino {destino.tipo}, expresión {expr.tipo}."
                       f"{self._pista_conversion(destino.tipo, expr.tipo)}")
            return destino
        self.unidad.emitir(':=', destino.ref, expr.ref, destino.tipo)
        return destino

    # ---------------- salida ----------------
    def salida_expresion(self, expr):
        if expr.tipo != ERROR:
            self.unidad.emitir('POUT', expr.ref, None, expr.tipo)

    def salida_cadena(self, texto):
        # El léxico entrega el texto SIN llaves, pero la clave en la TS es el lexema
        # original CON llaves; se reconstruye acá para referenciar la TS.
        lexema_ts = '{' + texto + '}'
        self.unidad.emitir('POUT', lexema_ts, None, 'CADENA')

    # ======================================================================
    # [PASO 3] FUNCIONES
    # ======================================================================
    def iniciar_funcion(self, nombre, tipo_retorno, linea, sin_nombre=False):
        """
        Se llama cuando el parser reconoce  <tipo> FUNCTION <ID>  (antes de los parámetros).
          1) declara la función en el ámbito que la contiene          -> nombre:ambito
          2) entra al ámbito de la función (sus parámetros y locales quedan nombre:...:f)
          3) abre una estructura de tercetos independiente para su cuerpo
        tipo_retorno: UINTEGER / DOUBLEF / nombre de clase / VOID / AUTO
        """
        if sin_nombre:      # el parser detectó "falta el nombre de la función"
            self._n_sin_nombre += 1
            nombre = f"sin_nombre_{self._n_sin_nombre}"

        padre = self.ambitos.ambito_actual()
        mangleado = f"{nombre}:{padre}"
        ok = self.ambitos.declarar(nombre, tipo_retorno, 'funcion', linea, parametros=[]) is not None
        if ok:
            info, ambito = self.tabla.buscar(mangleado), nombre
        else:
            # Función redeclarada: se compila igual el cuerpo (para detectar más errores),
            # en un ámbito aparte para no tocar la entrada original de la TS.
            info, ambito, mangleado = {}, f"{nombre}#redeclarada", f"{mangleado}#redeclarada"

        self.ambitos.entrar(ambito)
        self.pila_unidades.append(UnidadCodigo(mangleado))
        self.pila_funciones.append({'nombre': mangleado, 'tipo': tipo_retorno, 'linea': linea,
                                    'info': info, 'cant_ret': 0, 'tipos_ret': []})

    def declarar_parametros(self, parametros, linea):
        """Registra los parámetros formales en el ámbito de la función (x:main:aa) y deja
        en la entrada de la función la lista [(nombre_mangleado, tipo), ...] que se usa
        para chequear las invocaciones."""
        f = self.pila_funciones[-1]
        formales = []
        for prm in parametros:
            nombre, tipo = prm['id'], prm['tipo_dato']
            if tipo == 'UNKNOWN':
                tipo = ERROR
            if nombre == 'UNKNOWN':
                self._n_sin_nombre += 1
                nombre = f"param_sin_nombre_{self._n_sin_nombre}"
            mangleado = self.ambitos.declarar(nombre, tipo, 'parametro', linea)
            if mangleado is not None:
                formales.append((mangleado, tipo))
        f['info']['parametros'] = formales

    def falta_retorno(self):
        """El parser detectó un cuerpo AUTO que no termina con 'ret'."""
        f = self.pila_funciones[-1]
        self.errores.sintactico(
            f['linea'], f"la función AUTO '{f['nombre']}' debe terminar con una sentencia 'ret' "
                        f"(falta el retorno).")

    def retorno(self, expr, linea):
        if not self.pila_funciones:
            self.errores.semantico(linea, "'ret' fuera de una función.")
            return
        f = self.pila_funciones[-1]
        f['cant_ret'] += 1
        if expr.tipo == ERROR:
            return
        if f['tipo'] == VOID:
            self.errores.semantico(linea, f"la función '{f['nombre']}' es VOID y no puede devolver un valor.")
            return
        if f['tipo'] == AUTO:
            if expr.tipo not in TIPOS_BASICOS:
                self.errores.semantico(linea, f"'ret' de una función AUTO devuelve {expr.tipo}; se esperaba UINTEGER o DOUBLEF.")
                return
            f['tipos_ret'].append(expr.tipo)      # el tipo final se resuelve en finalizar_funcion
        elif not self._compatible(f['tipo'], expr.tipo):
            self.errores.semantico(
                linea, f"'ret' devuelve {expr.tipo} pero la función '{f['nombre']}' devuelve {f['tipo']}."
                       f"{self._pista_conversion(f['tipo'], expr.tipo)}")
            return
        self.unidad.emitir('RET', expr.ref, None, expr.tipo)

    def _valor_por_defecto(self, tipo) -> Optional[Operando]:
        # Estas constantes no vienen del léxico (el programa puede no tenerlas escritas), así
        # que además de registrar su tipo se les completa el valor si la TS no lo tiene.
        if tipo == UINTEGER:
            op, token, valor = self.constante_ui(0), 'CONST_UI', 0
        elif tipo == DOUBLEF:
            op, token, valor = self.constante_float('0.0'), 'FLOAT', 0.0
        else:
            return None
        entrada = self.tabla.buscar(op.ref, token)
        if entrada.get('valor') is None:
            entrada['valor'] = valor
        return op

    def finalizar_funcion(self):
        """
        Se llama al terminar de reconocer la función completa.
          - AUTO: fija el tipo de retorno = el más abarcativo entre sus 'ret' (tema 21)
          - VOID / tipadas: agrega el RET por defecto al final (enunciado: "se asumirá un
            valor de retorno por defecto, del tipo devuelto por la función"). Se agrega
            SIEMPRE: así los saltos que apuntan al final de la función tienen destino.
          - cierra la estructura de tercetos de la función y sale de su ámbito.
        """
        f = self.pila_funciones.pop()
        if f['tipo'] == AUTO:
            tipos = f['tipos_ret']
            if DOUBLEF in tipos:
                resuelto = DOUBLEF
            elif UINTEGER in tipos:
                resuelto = UINTEGER
            else:
                resuelto = ERROR            # sin ret válidos: ya se informó el error
            f['info']['tipo'] = resuelto
        elif f['tipo'] == VOID:
            self.unidad.emitir('RET', None, None, VOID)
        else:
            defecto = self._valor_por_defecto(f['tipo'])
            self.unidad.emitir('RET', defecto.ref if defecto else None, None, f['tipo'])
        self.terminadas.append(self.pila_unidades.pop())
        self.ambitos.salir()
        return f

    # ---------------- invocaciones ----------------
    def invocacion(self, nombre, argumentos, linea) -> Operando:
        """
        Chequeos (enunciado, 'Invocaciones'):
          - la función existe y es visible
          - es realmente una función (uso correcto del símbolo)
          - cantidad de parámetros reales == cantidad de parámetros formales
          - tipo de cada real compatible con el del formal (mismas reglas que la asignación)
        Código: pasaje POR COPIA. Antes del CALL se copia cada real sobre su formal, en orden:
                ( := , formal , real )   ...   ( CALL , función , - )
        El valor de la invocación es el propio terceto CALL.
        """
        mangleado, info = self.ambitos.resolver(nombre, linea)
        if info is None:
            return ERR
        if info.get('uso') != 'funcion':
            self.errores.semantico(linea, f"'{nombre}' es {info.get('uso')} y se invoca como función.")
            return ERR
        tipo = info['tipo']
        if tipo == AUTO:
            self.errores.semantico(
                linea, f"la función AUTO '{nombre}' se invoca antes de que su tipo de retorno "
                       f"quede determinado (invocación recursiva).")
            return ERR
        formales = info.get('parametros', [])
        if len(argumentos) != len(formales):
            self.errores.semantico(
                linea, f"la función '{nombre}' espera {len(formales)} parámetro(s) y se invocó con "
                       f"{len(argumentos)}.")
            return ERR
        correcto = True
        for i, ((_, t_formal), real) in enumerate(zip(formales, argumentos), start=1):
            if ERROR in (t_formal, real.tipo):
                correcto = False
            elif not self._compatible(t_formal, real.tipo):
                self.errores.semantico(
                    linea, f"parámetro {i} de '{nombre}': se esperaba {t_formal} y se recibió "
                           f"{real.tipo}.{self._pista_conversion(t_formal, real.tipo)}")
                correcto = False
        if not correcto or tipo == ERROR:
            return ERR
        for (formal, t_formal), real in zip(formales, argumentos):
            self.unidad.emitir(':=', formal, real.ref, t_formal)
        return Operando(self.unidad.emitir('CALL', mangleado, None, tipo), tipo, linea)

    def valor_invocacion(self, op) -> Operando:
        """Una invocación usada DENTRO de una expresión debe devolver valor."""
        if op.tipo == VOID:
            self.errores.semantico(op.linea, "la función es VOID: no devuelve valor y no puede usarse en una expresión.")
            return ERR
        return op

    # ---------------- IF (con backpatching) ----------------
    def if_condicion(self, cond, linea):
        """Después de parsear la condición: emite BF (salta si es falsa) con destino pendiente."""
        if cond.tipo not in (BOOL, ERROR):
            self.errores.semantico(linea, "la condición del IF debe ser una comparación.")
        self.pila_control.append(self.unidad.emitir('BF', cond.ref, None))

    def if_else(self):
        """Al llegar al ELSE: cierra la rama then con un salto incondicional (BI, destino
        pendiente) y completa el BF para que apunte al primer terceto de la rama else."""
        if not self.pila_control:       # protección ante errores sintácticos
            return
        bf = self.pila_control.pop()
        bi = self.unidad.emitir('BI')
        self.unidad.completar_salto(bf, self.unidad.proximo())      # = nº del BI + 1
        self.pila_control.append(bi)

    def if_fin(self):
        """Al llegar al END_IF: completa el salto pendiente (BF si no hubo else, BI si lo hubo)
        con el número del próximo terceto."""
        if not self.pila_control:       # protección ante errores sintácticos
            return
        pendiente = self.pila_control.pop()
        self.unidad.completar_salto(pendiente, self.unidad.proximo())

    # ---------------- WHILE ... REPEAT (tema 11) ----------------
    def while_inicio(self):
        """Antes de la condición: apila el número del terceto donde empieza (para volver)."""
        self.pila_control.append(self.unidad.proximo())

    def while_condicion(self, cond, linea):
        if cond.tipo not in (BOOL, ERROR):
            self.errores.semantico(linea, "la condición del WHILE debe ser una comparación.")
        self.pila_control.append(self.unidad.emitir('BF', cond.ref, None))

    def while_fin(self):
        """Tras el cuerpo: BI al inicio de la condición y completa el BF para salir del ciclo."""
        if len(self.pila_control) < 2:  # protección ante errores sintácticos
            self.pila_control.clear()
            return
        bf = self.pila_control.pop()
        inicio = self.pila_control.pop()
        self.unidad.emitir('BI', inicio)
        self.unidad.completar_salto(bf, self.unidad.proximo())

    def control_pendiente(self):
        """Saltos sin completar. Al terminar de compilar debe ser []."""
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

    V = lambda n, l: gen.variable(n, l)
    UI = gen.constante_ui
    F = gen.constante_float

    amb.declarar('a', UINTEGER, 'variable', 1)
    amb.declarar('b', UINTEGER, 'variable', 1)
    amb.declarar('x', DOUBLEF, 'variable', 2)

    # UINTEGER FUNCTION suma(UINTEGER p, UINTEGER q) UINTEGER r; begin r := p + q; ret(r); end;
    gen.iniciar_funcion('suma', UINTEGER, 4)
    gen.declarar_parametros([{'tipo_dato': UINTEGER, 'id': 'p'}, {'tipo_dato': UINTEGER, 'id': 'q'}], 4)
    gen.declarar_variables(UINTEGER, ['r'], 5)
    gen.asignacion(V('r', 7), gen.operacion('+', V('p', 7), V('q', 7), 7), 7)
    gen.retorno(V('r', 8), 8)
    gen.finalizar_funcion()

    # AUTO FUNCTION elegir(UINTEGER n) begin if (n > 0$ui) ret(1.5); end_if; ret(n); end;
    gen.iniciar_funcion('elegir', AUTO, 11)
    gen.declarar_parametros([{'tipo_dato': UINTEGER, 'id': 'n'}], 11)
    gen.if_condicion(gen.comparacion('>', V('n', 13), UI(0), 13), 13)
    gen.retorno(F('1.5'), 14)
    gen.if_fin()
    gen.retorno(V('n', 16), 16)
    gen.finalizar_funcion()

    # FUNCTION informar(UINTEGER n) begin pout(n); end;
    gen.iniciar_funcion('informar', VOID, 19)
    gen.declarar_parametros([{'tipo_dato': UINTEGER, 'id': 'n'}], 19)
    gen.salida_expresion(V('n', 21))
    gen.finalizar_funcion()

    # ---- programa principal ----
    gen.asignacion(V('a', 25), gen.valor_invocacion(gen.invocacion('suma', [UI(1), UI(2)], 25)), 25)
    gen.invocacion('informar', [V('a', 26)], 26)                          # como sentencia
    gen.asignacion(V('x', 27), gen.valor_invocacion(gen.invocacion('elegir', [V('a', 27)], 27)), 27)
    gen.asignacion(V('b', 28), gen.convertir_toui(V('x', 28), 28), 28)

    # ---- errores a detectar ----
    gen.invocacion('suma', [UI(1)], 31)                                   # cantidad de parámetros
    gen.invocacion('suma', [F('2.5'), UI(1)], 32)                         # DOUBLEF -> UINTEGER sin TOUI
    gen.asignacion(V('a', 33), gen.valor_invocacion(gen.invocacion('informar', [UI(1)], 33)), 33)   # VOID en expresión
    gen.invocacion('a', [UI(1)], 34)                                      # variable usada como función
    gen.invocacion('noexiste', [UI(1)], 35)                               # no declarada
    gen.retorno(UI(1), 36)                                                # ret fuera de función
    V('suma', 37)                                                         # función usada como variable

    gen.imprimir()
    print('Saltos sin completar (debe ser []):', gen.control_pendiente())
    errores.imprimir()
    tabla.imprimir_tabla()