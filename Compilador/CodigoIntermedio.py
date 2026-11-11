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
        (de adentro hacia afuera). Devuelve (nombre_mangleado, info) o (None, None)."""
        for i in range(len(self.pila), 0, -1):
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

    def iniciar_clase(self, nombre_clase, linea, clase_padre=None):
        self.clase_actual = nombre_clase
        # Registramos la clase en la tabla incluyendo su padre y su conjunto de amigos
        self.tabla.registrar(
            nombre_clase, 
            'CLASS', 
            uso='clase', 
            ambito='global',
            amigos=set(),
            padre=clase_padre # <--- Guardamos la relación de herencia en la Tabla de Símbolos
        )

    def registrar_amigo(self, nombre_amigo, linea):
        if self.clase_actual:
            # Buscamos la info de la clase actual en la tabla de símbolos
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
    
    
    def declarar_miembro(self, tipo, nombre, uso, visibilidad, linea):
        # El ámbito o nombre interno incluirá la clase actual si corresponde
        nombre_interno = f"{self.clase_actual}.{nombre}" if self.clase_actual else nombre
        
        # Usamos .registrar() (o .declarar() según cómo lo tengas mapeado) pasando nombre y token posicionales
        self.tabla.registrar(
            nombre_interno,
            "ID",
            tipo=tipo,
            uso=uso,
            ambito=self.clase_actual or "global",
            visibilidad=visibilidad # <--- Guardamos 'private' o 'public'
        )


    def validar_y_obtener_miembro(self, clase_propietaria, nombre_miembro, linea):
            clase_actual_busqueda = clase_propietaria
            coincidencias = []

            # Búsqueda recursiva a través de toda la jerarquía recolectando TODAS las apariciones
            while clase_actual_busqueda:
                nombre_interno = f"{clase_actual_busqueda}.{nombre_miembro}"
                info = self.tabla.buscar(nombre_interno)
                if info:
                    coincidencias.append((clase_actual_busqueda, info))
                
                # Consultamos la clase padre para seguir ascendiendo en la jerarquía
                info_clase = self.tabla.buscar(clase_actual_busqueda, token='CLASS')
                clase_actual_busqueda = info_clase.get('padre') if info_clase else None

            # 1. Chequeo de existencia: Si no existe en ninguna clase de la jerarquía
            if not coincidencias:
                self.errores.semantico(linea, f"El miembro '{nombre_miembro}' no existe en la clase '{clase_propietaria}' ni en sus clases base.")
                return None
                
            # 2. Chequeo de ambigüedad (Opción 3): Si el miembro existe en más de una clase de la cadena
            if len(coincidencias) > 1:
                clases_implicadas = ", ".join([c[0] for c in coincidencias])
                self.errores.semantico(linea, f"Error semántico: El miembro '{nombre_miembro}' es ambiguo; está declarado en múltiples clases de la jerarquía: [{clases_implicadas}].")
                return None

            # Si hay exactamente una única coincidencia, extraemos su propietario real y metadatos
            propietario_real, info = coincidencias[0]

            # 3. Si el miembro encontrado es público, se permite directamente
            if info.get('visibilidad', 'public') != 'private':
                return info
                
            # 4. Si el miembro es PRIVADO, aplicamos las reglas de acceso:
            # ¿Estamos dentro de la misma clase EXACTA donde fue declarado el miembro privado?
            es_propio = (self.clase_actual == propietario_real)
            
            # ¿El ámbito actual es amigo de la clase propietaria real del miembro?
            info_clase_prop = self.tabla.buscar(propietario_real, token='CLASS')
            amigos_de_la_clase = info_clase_prop.get('amigos', set()) if info_clase_prop else set()
            es_amigo = any(ambito in amigos_de_la_clase for ambito in self.pila)
            
            if es_propio or es_amigo:
                return info
                
            # Si no cumple ninguna condición, bloqueamos por acceso denegado a miembro privado
            self.errores.semantico(linea, f"Acceso denegado: El miembro '{nombre_miembro}' de la clase '{propietario_real}' es privado.")
            return None

    
    def cerrar_clase(self, nombre_clase, linea):
        self.clase_actual = None

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

        # [PASO 4 - COMPTIME / Constant Folding] Plegado de constantes aritméticas
        if isinstance(izq.ref, str) and isinstance(der.ref, str) and '$ui' in izq.ref and '$ui' in der.ref:
            try:
                val1 = int(izq.ref.split('$')[0])
                val2 = int(der.ref.split('$')[0])
                resultado_val = 0
                if op == '+': resultado_val = val1 + val2
                elif op == '-': resultado_val = val1 - val2
                elif op == '*': resultado_val = val1 * val2
                elif op == '/': 
                    if val2 != 0: resultado_val = val1 // val2
                    else: self.errores.semantico(linea, "División por cero en tiempo de compilación.")
                return self.constante_ui(resultado_val)
            except ValueError:
                pass

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
            # Debe ser un literal que contenga '$' (ej. '3$ui') o un valor comptime ya registrado
            es_literal_o_constante = isinstance(expr.ref, str) and '$' in expr.ref
            
            if es_literal_o_constante:
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

    def operacion(self, op, izq, der, linea) -> Operando:
        """op en {'+','-','*','/'}"""
        if ERROR in (izq.tipo, der.tipo):
            return ERR
        tipo = self._tipo_resultado(izq.tipo, der.tipo, linea)
        if tipo is None:
            return ERR

        # [PASO 4 - COMPTIME / Constant Folding] Si ambos operandos son constantes puras en texto (ej. "3$ui" y "1$ui"),
        # podemos calcular el resultado directamente en compilación para mantener el valor estático de las comptime.
        if isinstance(izq.ref, str) and isinstance(der.ref, str) and '$ui' in izq.ref and '$ui' in der.ref:
            try:
                val1 = int(izq.ref.split('$')[0])
                val2 = int(der.ref.split('$')[0])
                resultado_val = 0
                if op == '+': resultado_val = val1 + val2
                elif op == '-': resultado_val = val1 - val2
                elif op == '*': resultado_val = val1 * val2
                elif op == '/': 
                    if val2 != 0: resultado_val = val1 // val2
                    else: self.errores.semantico(linea, "División por cero en tiempo de compilación.")
                
                # Devolvemos un nuevo operando constante ya plegado
                return self.constante_ui(resultado_val)
            except ValueError:
                pass

        return Operando(self.unidad.emitir(op, izq.ref, der.ref, tipo), tipo)

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

    def validar_acceso(self, clase_propietaria, miembro_nombre, linea):
        info_miembro = self.tabla.buscar_en_clase(clase_propietaria, miembro_nombre)
        
        # Si es público, pasa sin problemas
        if info_miembro.get('visibilidad') != 'private':
            return True
            
        # Si es private, verificamos quién intenta acceder (contexto del ámbito actual)
        ambito_actual = self.ambitos.ambito_actual()
        
        # Condición 1: ¿Estamos dentro de un método de la misma clase propietaria?
        if self.ambitos.es_miembro_de_clase(ambito_actual, clase_propietaria):
            return True
            
        # Condición 2: ¿El ámbito actual (clase o función) está en la lista de 'amigos' de la clase propietaria?
        if self.ambitos.es_amigo_de(ambito_actual, clase_propietaria):
            return True
            
        # Si no cumple ninguna, se rechaza
        self.errores.semantico(linea, f"Acceso denegado: El miembro '{miembro_nombre}' es privado.")
        return False
    
    # =========================================================================
    # PUENTES / DELEGADORES HACIA GESTOR DE ÁMBITOS (PASO 5)
    # =========================================================================
    def iniciar_clase(self, nombre_clase, linea, clase_padre=None):
        return self.ambitos.iniciar_clase(nombre_clase, linea, clase_padre)

    def cerrar_clase(self, nombre_clase, linea):
        return self.ambitos.cerrar_clase(nombre_clase, linea)

    def declarar_atributo(self, tipo, nombre, visibilidad, linea):
        return self.ambitos.declarar_miembro(tipo, nombre, 'variable', visibilidad, linea)

    def declarar_metodo(self, tipo, nombre, parametros, declaraciones, cuerpo, visibilidad, linea):
        # Si los métodos se registran como miembros en el ámbito de la clase:
        return self.ambitos.declarar_miembro(tipo, nombre, 'funcion', visibilidad, linea)

    def registrar_amigo(self, nombre_amigo, linea):
        return self.ambitos.registrar_amigo(nombre_amigo, linea)
    
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

    print("\n=== INICIO DE PRUEBAS RIGUROSAS: HERENCIA Y AMBIGÜEDAD (OPCIÓN 3) ===")

    # Limpiamos o inicializamos un nuevo flujo de prueba
    # Escenario base: Abuela -> Padre -> Hija

    # 1. Definición de Clases
    amb.iniciar_clase('Abuela', linea=1)
    amb.declarar_miembro('UINTEGER', 'prop_comun', 'variable', 'public', linea=2)
    amb.declarar_miembro('UINTEGER', 'prop_abuela', 'variable', 'public', linea=3)
    amb.cerrar_clase('Abuela', linea=4)

    amb.iniciar_clase('Padre', linea=5, clase_padre='Abuela')
    amb.declarar_miembro('UINTEGER', 'prop_padre', 'variable', 'public', linea=6)
    # NOTA: 'prop_comun' NO se declara aquí, se hereda de Abuela.
    amb.cerrar_clase('Padre', linea=7)

    amb.iniciar_clase('Hija', linea=8, clase_padre='Padre')
    amb.declarar_miembro('UINTEGER', 'prop_hija', 'variable', 'public', linea=9)
    amb.cerrar_clase('Hija', linea=10)


    # --- TEST 1: Acceso a miembro heredado único sin colisión (Debe pasar limpio) ---
    print("\n--- Test 1: Acceso a 'prop_abuela' desde Hija (Debe pasar limpio) ---")
    amb.iniciar_ambito('Hija', 15)
    res1 = amb.validar_y_obtener_miembro('Hija', 'prop_abuela', linea=16)
    assert res1 is not None, "Test 1 Falló: Debería haber encontrado 'prop_abuela'"
    amb.cerrar_ambito()


    # --- TEST 2: Ambigüedad real - Colisión de nombres en la jerarquía (Debe fallar) ---
    # Vamos a simular una rama colisionada donde Abuela y Padre tienen una propiedad con el mismo nombre 'colision'
    amb.iniciar_clase('BaseA', linea=20)
    amb.declarar_miembro('UINTEGER', 'colision', 'variable', 'public', linea=21)
    amb.cerrar_clase('BaseA', linea=22)

    amb.iniciar_clase('BaseB', linea=23)
    amb.declarar_miembro('UINTEGER', 'colision', 'variable', 'public', linea=24)
    amb.cerrar_clase('BaseB', linea=25)

    # Supongamos temporalmente una clase con múltiples padres o una jerarquía lineal cruzada
    # Para probar el bucle actual de herencia simple: si Padre y Abuela tienen 'prop_comun'
    # Espere: En herencia simple (un solo padre), una clase hija hereda de Padre, y Padre de Abuela. 
    # Si Padre define 'prop_comun' y Abuela también define 'prop_comun', ¡se produce ambigüedad entre Padre y Abuela!
    # --- TEST 3: Colisión vertical entre Padre y Abuela (Debe fallar por ambigüedad) ---
    amb.iniciar_clase('AbuelaCol', linea=30)
    amb.declarar_miembro('UINTEGER', 'duplicado', 'variable', 'public', linea=31)
    amb.cerrar_clase('AbuelaCol', linea=32)

    amb.iniciar_clase('PadreCol', linea=33, clase_padre='AbuelaCol')
    amb.declarar_miembro('UINTEGER', 'duplicado', 'variable', 'public', linea=34) # ¡Colisiona con AbuelaCol!
    amb.cerrar_clase('PadreCol', linea=35)

    amb.iniciar_clase('HijaCol', linea=36, clase_padre='PadreCol')
    amb.cerrar_clase('HijaCol', linea=37)

    print("\n--- Test 3: Acceso a 'duplicado' presente en PadreCol y AbuelaCol (Debe fallar por ambigüedad) ---")
    amb.iniciar_ambito('HijaCol', 40)
    amb.validar_y_obtener_miembro('HijaCol', 'duplicado', linea=41) # Debe arrojar error de ambigüedad
    amb.cerrar_ambito()

    print("\n=== FIN DE PRUEBAS RIGUROSAS ===")

    errores.imprimir()
    tabla.imprimir_tabla()