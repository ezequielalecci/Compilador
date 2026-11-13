"""
CodigoIntermedio.py  -  TP3 (Grupo 19)  -  AVANCES 1 a 5

Representación elegida: TERCETOS      ( operador , operando1 , operando2 )

Temas del grupo:
  - Tema  4 : UINTEGER (constantes $ui)
  - Tema  8 : DOUBLEF
  - Tema 11 : WHILE ... REPEAT
  - Tema 18 : asignaciones con '=' dentro de expresiones (el valor es el LADO IZQUIERDO)
  - Tema 21 : funciones AUTO
  - Tema 22 : COMPTIME
  - Tema 27 : friend / private
  - Tema 28 : acceso con '.'
  - Tema 32 : herencia (miembro ambiguo = error)
  - Tema 34 : conversión explícita float -> entero (TOUI) y chequeo de tipos asociado

=====================================================================================
CAMBIOS RESPECTO DE LA VERSIÓN ANTERIOR  (marcados con [PASO 3] / [PASO 5] / [TP4])
=====================================================================================
[PASO 3] FUNCIONES
  - iniciar_funcion_decl / finalizar_funcion_decl: abren y cierran el ámbito de la función,
    declaran los parámetros (uso 'parametro') y crean una UnidadCodigo por función.
  - invocar_funcion: valida cantidad y tipos de argumentos y emite
        ( ARG  , valor , parametro_mangleado )     uno por argumento
        ( CALL , unidad_de_la_funcion , - )        tipo = tipo de retorno
    El resultado de una llamada es el propio terceto CALL (Operando con ese número).
  - Las funciones AUTO resuelven su tipo al cerrar la función (según sus 'ret').
  - Una función con tipo y sin 'ret' da error. La recursión da error (el Assembler usa
    variables estáticas para parámetros y locales).
[PASO 5] CLASES, OBJETOS Y '.'
  - Las clases abren un ámbito; dentro de un método, un nombre se busca primero entre los
    parámetros/locales, luego entre los miembros de la clase (con herencia, ambigüedad y
    private/friend) y luego en los ámbitos exteriores.
  - Cada OBJETO (variable cuyo tipo es una clase) registra una copia de sus atributos con el
    nombre   obj.atributo:ambito   (ver _instanciar_objeto). 'obj.x' se resuelve a ese símbolo.
  - Los métodos se compilan como funciones (unidad 'Clase.metodo'). El cuerpo trabaja sobre
    los atributos "plantilla" de la clase ('Clase.atributo'); al invocar obj.m(...) se copian
    los atributos del objeto a la plantilla (antes del CALL) y de vuelta (después).
    No se permite invocar un método desde otro método de la misma jerarquía.
[TP4]
  - operacion(): el plegado de constantes ya NO pliega cuando el resultado se sale de
    [0, 65535] (por ejemplo 2$ui - 3$ui o 300$ui * 300$ui); en ese caso se emite el terceto
    y el control de overflow / resta negativa se hace en ejecución (controles d y f).
  - COMPTIME acepta también constantes flotantes.
  - Se eliminaron el bloque __main__ de pruebas (ahora está en main.py) y un método
    'operacion' duplicado.
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
ERROR = 'ERROR'         # tipo interno: evita errores en cascada
VOID = 'VOID'           # tipo de retorno de las funciones sin tipo
TIPOS_BASICOS = {UINTEGER, DOUBLEF}
MAX_UI = 65535

# El tema 34 solo EXIGE conversión en el sentido flotante -> entero.
PERMITE_ENTERO_A_FLOAT = False


# ----------------------------------------------------------------------------
# Tabla de símbolos con atributos semánticos (tipo, uso, ámbito)
# ----------------------------------------------------------------------------
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

    def miembros_de(self, clase):
        """[PASO 5] Símbolos declarados como miembros (atributos y métodos) de 'clase'."""
        return [s for (n, tok), s in self._simbolos.items()
                if tok == 'ID' and s.get('miembro_de') == clase]


# ----------------------------------------------------------------------------
# Errores: se acumulan y se muestran todos juntos al final (lo pide el TP3)
# ----------------------------------------------------------------------------
class Errores:
    def __init__(self):
        self.lista = []

    def semantico(self, linea, mensaje):
        self.lista.append((linea, f"Error Semántico: {mensaje}"))

    def warning(self, linea, mensaje):
        self.lista.append((linea, f"Warning: {mensaje}"))

    def hay_errores(self):
        return any(m.startswith('Error') for _, m in self.lista)

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
        self.valores_comptime = {}
        self.clase_actual = None
        self.amigos_por_clase = {}

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
        (de adentro hacia afuera). Devuelve (nombre_mangleado, info) o (None, None).
        [PASO 5] Al llegar al ámbito de la clase en curso, busca entre sus miembros
        (incluidos los heredados) antes de seguir hacia afuera."""
        for i in range(len(self.pila), 0, -1):
            if self.clase_actual and self.pila[i - 1] == self.clase_actual:
                if self.buscar_miembros(self.clase_actual, nombre):
                    info = self.validar_y_obtener_miembro(self.clase_actual, nombre, linea)
                    if info is None:
                        return None, None          # el error ya fue informado
                    return info['lexema'], info
            mangleado = f"{nombre}:{':'.join(self.pila[:i])}"
            info = self.tabla.buscar(mangleado)
            if info is not None:
                return mangleado, info
        self.errores.semantico(linea, f"'{nombre}' no está declarado o no es visible desde el ámbito '{self.ambito_actual()}'.")
        return None, None

    def registrar_valor_comptime(self, nombre_mangleado, valor_operando, linea):
        info = self.tabla.buscar(nombre_mangleado)
        if info and info.get('comptime'):
            self.valores_comptime[nombre_mangleado] = valor_operando
        else:
            self.errores.semantico(linea, f"La variable '{nombre_mangleado}' no es de tipo COMPTIME.")

    def obtener_valor_comptime(self, nombre_mangleado):
        """Devuelve el valor registrado si es una variable comptime."""
        return self.valores_comptime.get(nombre_mangleado)

    # ---------------- clases ----------------
    def iniciar_clase(self, nombre_clase, linea, clase_padre=None):
        if self.tabla.buscar(nombre_clase, token='CLASS') is not None:
            self.errores.semantico(linea, f"la clase '{nombre_clase}' ya está declarada.")
        else:
            if clase_padre is not None and self.tabla.buscar(clase_padre, token='CLASS') is None:
                self.errores.semantico(linea, f"la clase base '{clase_padre}' no está declarada.")
                clase_padre = None
            self.tabla.registrar(
                nombre_clase,
                'CLASS',
                uso='clase',
                ambito='global',
                amigos=set(),
                padre=clase_padre
            )
        self.clase_actual = nombre_clase
        self.entrar(nombre_clase)          # [PASO 5] la clase es un ámbito más

    def registrar_amigo(self, nombre_amigo, linea):
        if self.clase_actual:
            info_clase = self.tabla.buscar(self.clase_actual, token='CLASS')
            if info_clase and 'amigos' in info_clase:
                info_clase['amigos'].add(nombre_amigo)
        else:
            self.errores.semantico(linea, "La declaración 'friend' debe estar dentro del cuerpo de una clase.")

    def es_amigo_de(self, ambito_o_entidad, nombre_clase):
        info_clase = self.tabla.buscar(nombre_clase, token='CLASS')
        if info_clase and 'amigos' in info_clase:
            return ambito_o_entidad in info_clase['amigos']
        return False

    def declarar_miembro(self, tipo, nombre, uso, visibilidad, linea, **extra):
        """Registra un atributo o método de la clase actual como 'Clase.nombre'."""
        if not self.clase_actual:
            self.errores.semantico(linea, f"el miembro '{nombre}' debe declararse dentro de una clase.")
            return None
        nombre_interno = f"{self.clase_actual}.{nombre}"
        if self.tabla.buscar(nombre_interno) is not None:
            self.errores.semantico(linea, f"el miembro '{nombre}' ya está declarado en la clase '{self.clase_actual}'.")
            return None

        self.tabla.registrar(
            nombre_interno,
            "ID",
            tipo=tipo,
            uso=uso,
            ambito=self.clase_actual,
            visibilidad=visibilidad,
            miembro_de=self.clase_actual,     # [PASO 5] para listar los miembros de una clase
            miembro=nombre,
            **extra
        )
        return nombre_interno

    def cadena_de_clases(self, clase):
        """[clase, padre, abuela, ...]"""
        cadena, c = [], clase
        while c and c not in cadena:
            cadena.append(c)
            info = self.tabla.buscar(c, token='CLASS')
            c = info.get('padre') if info else None
        return cadena

    def buscar_miembros(self, clase, nombre_miembro):
        """Búsqueda SILENCIOSA: [(clase_propietaria, info)] en toda la jerarquía."""
        res = []
        for c in self.cadena_de_clases(clase):
            info = self.tabla.buscar(f"{c}.{nombre_miembro}")
            if info:
                res.append((c, info))
        return res

    def atributos_de_jerarquia(self, clase):
        """[(clase_propietaria, nombre, info)] de todos los ATRIBUTOS de la clase y sus bases."""
        res = []
        for c in self.cadena_de_clases(clase):
            for s in self.tabla.miembros_de(c):
                if s.get('uso') == 'variable':
                    res.append((c, s['miembro'], s))
        return res

    def validar_y_obtener_miembro(self, clase_propietaria, nombre_miembro, linea):
        coincidencias = self.buscar_miembros(clase_propietaria, nombre_miembro)

        # 1. Chequeo de existencia
        if not coincidencias:
            self.errores.semantico(linea, f"El miembro '{nombre_miembro}' no existe en la clase '{clase_propietaria}' ni en sus clases base.")
            return None

        # 2. Chequeo de ambigüedad (tema 32): el miembro existe en más de una clase de la cadena
        if len(coincidencias) > 1:
            clases_implicadas = ", ".join([c[0] for c in coincidencias])
            self.errores.semantico(linea, f"El miembro '{nombre_miembro}' es ambiguo; está declarado en múltiples clases de la jerarquía: [{clases_implicadas}].")
            return None

        propietario_real, info = coincidencias[0]

        # 3. Miembro público: se permite
        if info.get('visibilidad', 'public') != 'private':
            return info

        # 4. Miembro PRIVADO (tema 27): solo la misma clase o sus amigos
        es_propio = (self.clase_actual == propietario_real)
        info_clase_prop = self.tabla.buscar(propietario_real, token='CLASS')
        amigos_de_la_clase = info_clase_prop.get('amigos', set()) if info_clase_prop else set()
        es_amigo = any(ambito in amigos_de_la_clase for ambito in self.pila)

        if es_propio or es_amigo:
            return info

        self.errores.semantico(linea, f"Acceso denegado: El miembro '{nombre_miembro}' de la clase '{propietario_real}' es privado.")
        return None

    def cerrar_clase(self, nombre_clase, linea):
        self.clase_actual = None
        if self.pila and self.pila[-1] == nombre_clase:
            self.salir()

    def iniciar_ambito(self, nombre_ambito, linea):
        self.entrar(nombre_ambito)

    def cerrar_ambito(self):
        self.salir()


# ----------------------------------------------------------------------------
# Tercetos
# ----------------------------------------------------------------------------
@dataclass
class Terceto:
    op: str
    a1: Union[int, str, None] = None   # int -> referencia a otro terceto [n] ; str -> símbolo de la TS
    a2: Union[int, str, None] = None
    tipo: Optional[str] = None         # tipo del resultado


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
        """
        Lectura (rvalue): Se usa cuando la variable aparece en expresiones.
        Si es COMPTIME, exige que ya tenga un valor registrado; si no, da error.
        """
        mangleado, info = self.ambitos.resolver(nombre, linea)
        if info is None:
            return ERR
        if info.get('uso') not in ('variable', 'parametro'):
            self.errores.semantico(linea, f"'{nombre}' es {info.get('uso')} y se usa como variable.")
            return ERR

        if info.get('comptime'):
            valor_constante = self.ambitos.obtener_valor_comptime(mangleado)
            if valor_constante is not None:
                return valor_constante
            self.errores.semantico(linea, f"La variable COMPTIME '{nombre}' se usa antes de que se le asigne un valor conocido en compilación.")
            return ERR

        return Operando(mangleado, info['tipo'])

    def variable_destino(self, nombre, linea) -> Operando:
        """
        Escritura (lvalue): Se usa cuando la variable va al LADO IZQUIERDO de una asignación.
        NO exige valor previo porque se le asignará uno en este paso.
        """
        mangleado, info = self.ambitos.resolver(nombre, linea)
        if info is None:
            return ERR
        if info.get('uso') not in ('variable', 'parametro'):
            self.errores.semantico(linea, f"'{nombre}' es {info.get('uso')} y se usa como variable.")
            return ERR

        return Operando(mangleado, info['tipo'])

    def constante_ui(self, valor) -> Operando:
        lexema = f"{valor}$ui"          # misma clave que usa el léxico al insertar
        self.tabla.registrar(lexema, 'CONST_UI', tipo=UINTEGER)
        return Operando(lexema, UINTEGER)

    def constante_float(self, lexema) -> Operando:
        self.tabla.registrar(lexema, 'FLOAT', tipo=DOUBLEF)
        return Operando(lexema, DOUBLEF)

    # ---------------- declaración de variables ----------------
    def declarar_variables(self, tipo, nombres, linea, comptime=False):
        """Registra cada variable en el ámbito actual (con name mangling) con su tipo.
        [PASO 5] Si el tipo es una CLASE, la variable es un objeto y se le crea una copia
        de cada atributo de la clase (y de sus bases)."""
        es_clase = self.tabla.buscar(tipo, token='CLASS') is not None
        if tipo not in TIPOS_BASICOS and not es_clase:
            self.errores.semantico(linea, f"el tipo '{tipo}' no es UINTEGER, DOUBLEF ni una clase declarada.")
            tipo = ERROR
        if es_clase and comptime:
            self.errores.semantico(linea, "COMPTIME solo se puede usar con UINTEGER o DOUBLEF.")
            comptime = False
        for nombre in nombres:
            mangleado = self.ambitos.declarar(nombre, tipo, 'variable', linea, comptime=comptime)
            if mangleado and es_clase:
                self._instanciar_objeto(mangleado, tipo)

    def _nombre_instancia(self, objeto_mangleado, miembro):
        """v:main + velocidad  ->  v.velocidad:main"""
        nombre, _, ambito = objeto_mangleado.partition(':')
        return f"{nombre}.{miembro}:{ambito}"

    def _instanciar_objeto(self, mangleado, clase):
        ambito = self.ambitos.ambito_actual()
        for propietario, miembro, info in self.ambitos.atributos_de_jerarquia(clase):
            inst = self._nombre_instancia(mangleado, miembro)
            if self.tabla.buscar(inst) is None:
                self.tabla.registrar(inst, 'ID', tipo=info['tipo'], uso='variable',
                                     ambito=ambito, objeto=mangleado, propietario=propietario)

    # ---------------- acceso con '.' (tema 28) ----------------
    def acceso_miembro_punto(self, obj: Operando, miembro, linea) -> Operando:
        """obj.miembro  ->  símbolo de la copia del atributo dentro del objeto."""
        if obj.tipo == ERROR:
            return ERR
        if self.tabla.buscar(obj.tipo, token='CLASS') is None:
            self.errores.semantico(linea, f"se usa '.' sobre algo que no es un objeto (tipo {obj.tipo}).")
            return ERR
        info = self.ambitos.validar_y_obtener_miembro(obj.tipo, miembro, linea)
        if info is None:
            return ERR
        if info.get('uso') != 'variable':
            self.errores.semantico(linea, f"'{miembro}' es un método; hay que invocarlo con paréntesis.")
            return ERR
        inst = self._nombre_instancia(obj.ref, miembro)
        if self.tabla.buscar(inst) is None:
            self.errores.semantico(linea, f"el objeto no tiene el atributo '{miembro}'.")
            return ERR
        return Operando(inst, info['tipo'])

    def acceso_miembro_punto_destino(self, obj: Operando, miembro, linea) -> Operando:
        return self.acceso_miembro_punto(obj, miembro, linea)

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

        # [PASO 4 - COMPTIME / Constant Folding] Plegado de constantes aritméticas.
        # [TP4] Solo se pliega si el resultado entra en [0, 65535]; si no, se emite el
        # terceto para que el control de overflow / resta negativa se haga en ejecución.
        if (isinstance(izq.ref, str) and isinstance(der.ref, str)
                and izq.ref.endswith('$ui') and der.ref.endswith('$ui')):
            try:
                val1 = int(izq.ref[:-3])
                val2 = int(der.ref[:-3])
            except ValueError:
                val1 = val2 = None
            if val1 is not None:
                if op == '/' and val2 == 0:
                    self.errores.semantico(linea, "División por cero en tiempo de compilación.")
                    return ERR
                resultado_val = {'+': lambda: val1 + val2, '-': lambda: val1 - val2,
                                 '*': lambda: val1 * val2, '/': lambda: val1 // val2}[op]()
                if 0 <= resultado_val <= MAX_UI:
                    return self.constante_ui(resultado_val)

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

    def _es_constante(self, ref) -> bool:
        return isinstance(ref, str) and (ref.endswith('$ui') or self.tabla.buscar(ref, 'FLOAT') is not None)

    def asignacion(self, destino, expr, linea) -> Operando:
        if ERROR in (destino.tipo, expr.tipo):
            return destino

        compatible = destino.tipo == expr.tipo or (
            PERMITE_ENTERO_A_FLOAT and destino.tipo == DOUBLEF and expr.tipo == UINTEGER)

        if not compatible:
            extra = " Usar TOUI(...)." if destino.tipo == UINTEGER and expr.tipo == DOUBLEF else ""
            self.errores.semantico(linea, f"asignación incompatible: destino {destino.tipo}, expresión {expr.tipo}.{extra}")
            return destino

        # [PASO 4 - COMPTIME] Validación estricta y registro de valor estático
        info_destino = self.tabla.buscar(destino.ref)
        if info_destino and info_destino.get('comptime'):
            if self._es_constante(expr.ref):
                self.ambitos.registrar_valor_comptime(destino.ref, expr, linea)
            else:
                self.errores.semantico(
                    linea,
                    f"A la variable COMPTIME '{info_destino['lexema']}' solo se le pueden asignar valores determinables en tiempo de compilación (no variables comunes)."
                )

        self.unidad.emitir(':=', destino.ref, expr.ref, destino.tipo)
        return destino

    # ---------------- salida y retorno ----------------
    def salida_expresion(self, expr):
        if expr.tipo != ERROR:
            self.unidad.emitir('POUT', expr.ref, None, expr.tipo)

    def salida_cadena(self, texto):
        # El léxico entrega el texto SIN llaves, pero la clave en la TS es el lexema original
        # CON llaves; se reconstruye acá para referenciar la TS.
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
                f['tipos_ret'].append(expr.tipo)       # el tipo final se resuelve al cerrar la función
            elif f['tipo'] != ERROR and f['tipo'] != expr.tipo:
                self.errores.semantico(linea, f"'ret' devuelve {expr.tipo} pero la función '{f['nombre']}' devuelve {f['tipo']}.")
            self.unidad.emitir('RET', expr.ref, None, expr.tipo)

    # ---------------- funciones: una unidad de código por función [PASO 3] ----------------
    def iniciar_funcion(self, nombre_mangleado, tipo_retorno):
        self.pila_unidades.append(UnidadCodigo(nombre_mangleado))
        self.pila_funciones.append({'nombre': nombre_mangleado, 'tipo': tipo_retorno,
                                    'cant_ret': 0, 'tipos_ret': []})

    def finalizar_funcion(self, linea):
        info = self.pila_funciones.pop()
        if info['tipo'] == 'AUTO' and info['cant_ret'] == 0:
            self.errores.semantico(linea, f"la función AUTO '{info['nombre']}' debe tener al menos un 'ret'.")
        elif info['tipo'] in TIPOS_BASICOS and info['cant_ret'] == 0:
            self.errores.semantico(linea, f"la función '{info['nombre']}' devuelve {info['tipo']} y no tiene ningún 'ret'.")
        self.terminadas.append(self.pila_unidades.pop())
        return info

    def _declarar_parametros(self, parametros, linea):
        """Declara los parámetros en el ámbito actual (ya dentro de la función).
        Devuelve [(nombre_mangleado, tipo)]."""
        resultado = []
        for prm in parametros:
            tipo = prm['tipo_dato']
            if tipo not in TIPOS_BASICOS:
                self.errores.semantico(linea, f"el parámetro '{prm['id']}' debe ser UINTEGER o DOUBLEF.")
                tipo = ERROR
            mang = self.ambitos.declarar(prm['id'], tipo, 'parametro', linea)
            resultado.append((mang or f"{prm['id']}:{self.ambitos.ambito_actual()}", tipo))
        return resultado

    def iniciar_funcion_decl(self, tipo_retorno, nombre, parametros, linea):
        """Se llama al terminar la cabecera:  [tipo] FUNCTION nombre ( parametros )"""
        if tipo_retorno not in TIPOS_BASICOS and tipo_retorno not in ('AUTO', VOID):
            self.errores.semantico(linea, f"la función '{nombre}' debe devolver UINTEGER, DOUBLEF o AUTO.")
            tipo_retorno = ERROR
        mang = self.ambitos.declarar(nombre, tipo_retorno, 'funcion', linea)
        declarada = mang is not None
        if not declarada:
            mang = f"{nombre}:{self.ambitos.ambito_actual()}"
        self.ambitos.entrar(nombre)
        params = self._declarar_parametros(parametros, linea)
        if declarada:
            self.tabla.registrar(mang, 'ID', parametros=params, unidad=mang)
        self.iniciar_funcion(mang, tipo_retorno)
        return mang

    def _resolver_tipo_auto(self, info, linea):
        if info['tipo'] != 'AUTO':
            return
        tipos = set(info['tipos_ret'])
        if len(tipos) > 1:
            self.errores.semantico(linea, f"la función AUTO '{info['nombre']}' tiene 'ret' de tipos distintos: {sorted(tipos)}.")
        nuevo = tipos.pop() if len(tipos) == 1 else ERROR
        simbolo = self.tabla.buscar(info['nombre'])
        if simbolo is not None:
            simbolo['tipo'] = nuevo

    def finalizar_funcion_decl(self, linea):
        info = self.finalizar_funcion(linea)
        self._resolver_tipo_auto(info, linea)
        self.ambitos.salir()

    # ---------------- invocaciones [PASO 3] ----------------
    def _emitir_llamada(self, info, args, linea, nombre, antes=(), despues=()):
        params = info.get('parametros', [])
        if any(a.tipo == ERROR for a in args) or info.get('tipo') == ERROR:
            return ERR
        if len(args) != len(params):
            self.errores.semantico(linea, f"'{nombre}' espera {len(params)} argumento(s) y recibió {len(args)}.")
            return ERR
        ok = True
        for i, (a, (_, tipo_param)) in enumerate(zip(args, params), 1):
            if a.tipo != tipo_param:
                extra = " Usar TOUI(...)." if tipo_param == UINTEGER and a.tipo == DOUBLEF else ""
                self.errores.semantico(linea, f"argumento {i} de '{nombre}': se esperaba {tipo_param} y es {a.tipo}.{extra}")
                ok = False
        if not ok:
            return ERR
        unidad = info['unidad']
        if any(f['nombre'] == unidad for f in self.pila_funciones):
            self.errores.semantico(linea, f"'{nombre}' se invoca a sí misma: la recursión no está soportada.")
            return ERR

        for destino, origen, tipo in antes:
            self.unidad.emitir(':=', destino, origen, tipo)
        for a, (param, tipo_param) in zip(args, params):
            self.unidad.emitir('ARG', a.ref, param, tipo_param)
        idx = self.unidad.emitir('CALL', unidad, None, info['tipo'])
        for destino, origen, tipo in despues:
            self.unidad.emitir(':=', destino, origen, tipo)
        return Operando(idx, info['tipo'])

    def invocar_funcion(self, nombre, args, linea) -> Operando:
        mang, info = self.ambitos.resolver(nombre, linea)
        if info is None:
            return ERR
        if info.get('uso') != 'funcion':
            self.errores.semantico(linea, f"'{nombre}' no es una función.")
            return ERR
        return self._emitir_llamada(info, args, linea, nombre)

    def valor_de_llamada(self, op: Operando, linea) -> Operando:
        """Una invocación usada como EXPRESIÓN no puede ser de una función VOID."""
        if op.tipo == VOID:
            self.errores.semantico(linea, "una función sin tipo de retorno no puede usarse dentro de una expresión.")
            return ERR
        return op

    # ---------------- métodos [PASO 5] ----------------
    def iniciar_metodo(self, tipo_retorno, nombre, parametros, linea):
        clase = self.ambitos.clase_actual
        if tipo_retorno not in TIPOS_BASICOS:
            self.errores.semantico(linea, f"el método '{nombre}' debe devolver UINTEGER o DOUBLEF.")
            tipo_retorno = ERROR
        unidad = f"{clase}.{nombre}"
        interno = self.ambitos.declarar_miembro(tipo_retorno, nombre, 'funcion', 'public', linea)
        self.ambitos.entrar(nombre)
        params = self._declarar_parametros(parametros, linea)
        if interno:
            self.tabla.registrar(interno, 'ID', parametros=params, unidad=unidad)
        self.iniciar_funcion(unidad, tipo_retorno)
        self.pila_funciones[-1]['clase'] = clase
        return nombre

    def finalizar_metodo(self, nombre, visibilidad, linea):
        self.finalizar_funcion(linea)
        self.ambitos.salir()
        info = self.tabla.buscar(f"{self.ambitos.clase_actual}.{nombre}")
        if info is not None and info.get('uso') == 'funcion':
            info['visibilidad'] = visibilidad

    def invocar_metodo(self, obj: Operando, nombre, args, linea) -> Operando:
        """obj.metodo(args): copia los atributos del objeto a la plantilla de la clase,
        pasa los argumentos, llama, y copia los atributos de vuelta."""
        if obj.tipo == ERROR:
            return ERR
        if self.tabla.buscar(obj.tipo, token='CLASS') is None:
            self.errores.semantico(linea, f"se usa '.' sobre algo que no es un objeto (tipo {obj.tipo}).")
            return ERR
        info = self.ambitos.validar_y_obtener_miembro(obj.tipo, nombre, linea)
        if info is None:
            return ERR
        if info.get('uso') != 'funcion':
            self.errores.semantico(linea, f"'{nombre}' es un atributo, no un método.")
            return ERR
        propietario = info['miembro_de']
        cadena = set(self.ambitos.cadena_de_clases(propietario))
        for f in self.pila_funciones:
            c = f.get('clase')
            if c and (c in cadena or propietario in self.ambitos.cadena_de_clases(c)):
                self.errores.semantico(linea, f"no se puede invocar el método '{nombre}' desde un método de la misma jerarquía de clases.")
                return ERR
        adentro, afuera = [], []
        for _, miembro, ainfo in self.ambitos.atributos_de_jerarquia(propietario):
            plantilla = ainfo['lexema']
            inst = self._nombre_instancia(obj.ref, miembro)
            adentro.append((plantilla, inst, ainfo['tipo']))
            afuera.append((inst, plantilla, ainfo['tipo']))
        return self._emitir_llamada(info, args, linea, nombre, adentro, afuera)

    # ------------------------------------------------------------------
    # [PASO 2 - REVISIÓN] Sentencias de control SIN tercetos LABEL.
    #
    # Convención:  DIR_ACTUAL = número del ÚLTIMO terceto emitido.
    #              self.unidad.proximo() = DIR_ACTUAL + 1 = próximo terceto a emitir.
    #
    # pila_control guarda tuplas (tipo, nro_terceto):
    #     ('BF', n)      BF incompleto           ('BI', n)      BI incompleto
    #     ('INICIO', n)  terceto donde empieza la condición de un WHILE
    #
    #   IF (c) A end_if        ->  [cond] BF(c,->fin) [A]  fin:
    #   IF (c) A else B end_if ->  [cond] BF(c,->B) [A] BI(->fin) B: [B]  fin:
    #   WHILE (c) repeat A     ->  ini: [cond] BF(c,->fin) [A] BI(->ini)  fin:
    #
    # OJO: un destino puede ser == len(tercetos) si la sentencia es lo último de la
    # unidad (no hay terceto "siguiente"); el Assembler lo trata como una etiqueta al final.
    # ------------------------------------------------------------------
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
        """FIN DEL THEN (hay ELSE): desapila el BF, crea el BI incompleto, completa el BF
        con el primer terceto del else y apila el BI."""
        if not self._tope_es('BF'):
            return
        _, bf = self.pila_control.pop()
        bi = self.unidad.emitir('BI')
        self.unidad.completar_salto(bf, self.unidad.proximo())
        self.pila_control.append(('BI', bi))

    def if_fin(self):
        """FIN DEL IF: desapila el salto pendiente y lo completa con el próximo terceto."""
        if not self._tope_es('BF', 'BI'):
            return
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
        """FIN DEL CUERPO: desapila BF e inicio, genera el BI al inicio y completa el BF."""
        if (len(self.pila_control) < 2 or self.pila_control[-1][0] != 'BF'
                or self.pila_control[-2][0] != 'INICIO'):
            return
        _, bf = self.pila_control.pop()
        _, inicio = self.pila_control.pop()
        self.unidad.emitir('BI', inicio)
        self.unidad.completar_salto(bf, self.unidad.proximo())

    def control_pendiente(self):
        """Para depurar: saltos que quedaron sin completar (debería ser lista vacía)."""
        return list(self.pila_control)

    # =========================================================================
    # PUENTES HACIA GESTOR DE ÁMBITOS (clases)
    # =========================================================================
    def iniciar_clase(self, nombre_clase, linea, clase_padre=None):
        return self.ambitos.iniciar_clase(nombre_clase, linea, clase_padre)

    def cerrar_clase(self, nombre_clase, linea):
        return self.ambitos.cerrar_clase(nombre_clase, linea)

    def declarar_atributo(self, tipo, nombre, visibilidad, linea):
        if tipo not in TIPOS_BASICOS:
            self.errores.semantico(linea, f"el atributo '{nombre}' debe ser UINTEGER o DOUBLEF (no se soportan atributos de tipo clase).")
            tipo = ERROR
        return self.ambitos.declarar_miembro(tipo, nombre, 'variable', visibilidad, linea)

    def registrar_amigo(self, nombre_amigo, linea):
        return self.ambitos.registrar_amigo(nombre_amigo, linea)

    # ---------------- salida ----------------
    def imprimir(self):
        for u in self.terminadas:
            u.imprimir()
        self.unidad.imprimir()