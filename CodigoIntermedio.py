from dataclasses import dataclass
from typing import Optional, Union
from TablaSimbolos import TablaSimbolos

UINTEGER = 'UINTEGER'   
DOUBLEF = 'DOUBLEF'   
BOOL = 'BOOL'           # tipo interno: resultado de una comparación
ERROR = 'ERROR'         # tipo interno: evita errores en cascada
VOID = 'VOID'           # tipo de retorno de las funciones sin tipo
TIPOS_BASICOS = {UINTEGER, DOUBLEF}
MAX_UI = 65535
MIN_POS = 2.2250738585072014e-308
MAX_POS = 1.7976931348623157e+308
ARIT_OPS = {'+', '-', '*', '/'}

# Asignar entero a flotante sin conversión sigue sin permitirse.
PERMITE_ENTERO_A_FLOAT = False

JERARQUIA = {UINTEGER: 0, DOUBLEF: 1}   # el mayor es el más abarcativo

VALOR_DEFECTO = {UINTEGER: '0$ui', DOUBLEF: '0.0'}


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
        return [s for (n, tok), s in self._simbolos.items()
                if tok == 'ID' and s.get('miembro_de') == clase]


class Errores:
    def __init__(self):
        self.lista = []

    def lexico(self, linea, mensaje):  
        self.lista.append((linea, f"Error Léxico: {mensaje}"))

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


class GestorAmbitos:
    """
    Mantiene la PILA de ámbitos. Cada símbolo se guarda en la Tabla de Símbolos
    con su nombre + ':' + ámbito completo:
        a declarada en main            ->  a:main
        parámetro x de la función aa   ->  x:main:aa
    """

    def __init__(self, tabla, errores, global_='main'):
        self.tabla = tabla
        self.errores = errores
        self.pila = [global_]
        self.valores_comptime = {}
        self.clase_actual = None
        self.amigos_por_clase = {}

    """
    al llamarse una funcion o clase el gestor de ambitos usa entrar() y salir(), para poder 
    definir el ambito actual donde está
    """
    def ambito_actual(self):
        return ':'.join(self.pila)

    def entrar(self, nombre):
        self.pila.append(nombre)

    def salir(self):
        self.pila.pop()
        
    # da de alta un identificador en la tabla de simbolos teniendo en cuenta su ambito actual. por ejemplo x:main:funcion_a
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
        """
        **extra es debido a que las diferentes entidades traen diferentes metadatos consigo
        a la hora de guardarse en la ts. Para el caso de los ID, guarda si es una variable comptime
        """
        
        return mangleado
    
    """
    se encarga de buscar una variable desde el ámbito local hacia el más externo,
    de tal modo que puede identificar que valor se usando o cual se debe modificar.
    Por ejemplo, si tenemos x:main y x:main:func; esto se encarga de verificar en que ambitos estamos,
    y a partir de allí ver cual es la más apropiada 
    """
    def resolver(self, nombre, linea):
        for i in range(len(self.pila), 0, -1):
            if self.clase_actual and self.pila[i - 1] == self.clase_actual:
                if self.buscar_miembros(self.clase_actual, nombre):
                    info = self.validar_y_obtener_miembro(self.clase_actual, nombre, linea)
                    if info is None:
                        return None, None         
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
        return self.valores_comptime.get(nombre_mangleado)


    def iniciar_clase(self, nombre_clase, linea, clase_padre=None):
        if self.tabla.buscar(nombre_clase, token='CLASS') is not None:
            self.errores.semantico(linea, f"la clase '{nombre_clase}' ya está declarada.")
        else:
            self.tabla.registrar(
                nombre_clase,
                'CLASS',
                uso='clase',
                ambito='global',
                amigos=set(),
                padres=[]               
            )
            """
            en este caso amigos y padres funciona porque en la TS, en el metodo registrar llega **atributos.
            Este es flexible y permite empaquetar en un diccionario (nuestra ts) los datos necesarios para cada entidad
            """
            
        self.clase_actual = nombre_clase
        self.entrar(nombre_clase)        
        if clase_padre is not None:       
            self.registrar_herencia([clase_padre], linea)

    def registrar_herencia(self, nombres, linea):
        if not self.clase_actual:
            self.errores.semantico(linea, "la declaración 'extends' debe estar dentro del cuerpo de una clase.")
            return
        info_clase = self.tabla.buscar(self.clase_actual, token='CLASS')
        if info_clase is None:
            return
        
        #set default permite desempaquetar correctamente los metadatos guardados en la ts (si no tiene padre, crea una lista vacía)
        padres = info_clase.setdefault('padres', [])
        
        for nombre in nombres:
            if nombre == self.clase_actual:
                self.errores.semantico(linea, f"la clase '{nombre}' no puede heredar de sí misma.")
            elif self.tabla.buscar(nombre, token='CLASS') is None:
                self.errores.semantico(linea, f"la clase base '{nombre}' no está declarada.")
            elif nombre in padres:
                self.errores.semantico(linea, f"la clase base '{nombre}' está repetida en 'extends'.")
            else:
                padres.append(nombre)

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
            miembro_de=self.clase_actual,    
            miembro=nombre,
            **extra
        )
        return nombre_interno

    def cadena_de_clases(self, clase):
        resultado = []

        def visitar(c):
            if c in resultado:
                return
            resultado.append(c)
            info = self.tabla.buscar(c, token='CLASS')
            for p in (info.get('padres', []) if info else []):
                visitar(p)

        visitar(clase)
        return resultado

    def buscar_miembros(self, clase, nombre_miembro):
        res = []
        for c in self.cadena_de_clases(clase):
            info = self.tabla.buscar(f"{c}.{nombre_miembro}")
            if info:
                res.append((c, info))
        return res

    def atributos_de_jerarquia(self, clase):
        res = []
        for c in self.cadena_de_clases(clase):
            for s in self.tabla.miembros_de(c):
                if s.get('uso') == 'variable':
                    res.append((c, s['miembro'], s))
        return res

    def validar_y_obtener_miembro(self, clase_propietaria, nombre_miembro, linea):
        coincidencias = self.buscar_miembros(clase_propietaria, nombre_miembro)

        if not coincidencias:
            self.errores.semantico(linea, f"El miembro '{nombre_miembro}' no existe en la clase '{clase_propietaria}' ni en sus clases base.")
            return None

        if len(coincidencias) > 1:
            clases_implicadas = ", ".join([c[0] for c in coincidencias])
            self.errores.semantico(linea, f"El miembro '{nombre_miembro}' es ambiguo; está declarado en múltiples clases de la jerarquía: [{clases_implicadas}].")
            return None

        propietario_real, info = coincidencias[0]
        if info.get('visibilidad', 'public') != 'private':
            return info

        # 4. Miembro privado: solo la misma clase o sus amigos
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


@dataclass
class Terceto:
    op: str
    a1: Union[int, str, None] = None   
    a2: Union[int, str, None] = None
    tipo: Optional[str] = None       

#auxiliar para imprimir mejor los resultados de los tercetos
def _fmt(x):
    if x is None:
        return '-'
    if isinstance(x, int):
        return f'[{x}]'
    return str(x)


class UnidadCodigo:
    """lista de tercetos. 
    Una por el programa principal y una por cada función"""

    def __init__(self, nombre):
        self.nombre = nombre
        self.tercetos = []

    def emitir(self, op, a1=None, a2=None, tipo=None) -> int:
        self.tercetos.append(Terceto(op, a1, a2, tipo))
        return len(self.tercetos) - 1

    def proximo(self) -> int:
        return len(self.tercetos)

    def completar_salto(self, idx, destino):
        #Backpatching: completa el destino de un salto emitido antes de conocerlo
        t = self.tercetos[idx]
        if t.op == 'BI':
            t.a1 = destino
        else:               # BF
            t.a2 = destino

    def reemplazar(self, idx, op, a1=None, a2=None, tipo=None):
        t = self.tercetos[idx]
        t.op, t.a1, t.a2, t.tipo = op, a1, a2, tipo

    def ref(self, idx):
        # una referencia a un terceto es el propio índice (int); _fmt lo imprime como [n]
        return idx

    def imprimir(self):
        print(f"\n=== Código intermedio: {self.nombre} ===")
        for i, t in enumerate(self.tercetos):
            print(f"{i:>3}  ( {t.op} , {_fmt(t.a1)} , {_fmt(t.a2)} )")


@dataclass(frozen=True)
class Operando:
    ref: Union[int, str, None]   
    tipo: str
    conv: bool = False           


ERR = Operando(None, ERROR)


class GeneradorCodigo:
    def __init__(self, tabla, errores, ambitos):
        self.tabla = tabla
        self.errores = errores
        self.ambitos = ambitos
        self.pila_unidades = [UnidadCodigo('main')]
        self.terminadas = []        # unidades de funciones ya cerradas
        self.pila_control = []      # saltos pendientes de completar (if / while)
        self.pila_funciones = []    # contexto de la función que se está compilando
        self.nivel_while = 0          # [COMPTIME] cantidad de WHILE abiertos (condición incluida)
        self.ct_en_ejecucion = set()  # [COMPTIME] comptime cuyo valor ya no es conocido en compilación
        self.pila_dinamica = []       # [COMPTIME] por cada if/while abierto: True si su condición NO es estática
        self.pila_ct_if = []          # [COMPTIME] por cada if abierto: estado comptime inicial y del then

    @property
    def unidad(self) -> UnidadCodigo:
        return self.pila_unidades[-1]

    # ---------------- operandos ----------------
    def variable(self, nombre, linea) -> Operando:
        """
        Lectura (rvalue): Se usa cuando la variable aparece en expresiones.
        Si es comptime, exige que ya tenga un valor registrado; si no, da error.
        """
        mangleado, info = self.ambitos.resolver(nombre, linea)
        if info is None:
            return ERR
        if info.get('uso') not in ('variable', 'parametro'):
            self.errores.semantico(linea, f"'{nombre}' es {info.get('uso')} y se usa como variable.")
            return ERR

        if info.get('comptime') and info.get('uso') != 'parametro':
            valor_constante = self.ambitos.obtener_valor_comptime(mangleado)
            # Valor desconocido en compilación (modificada en un while/if) o dentro de un
            # while (el valor cambia en cada vuelta): se usa la variable en ejecución.
            if (mangleado in self.ct_en_ejecucion
                    or (self.nivel_while > 0 and valor_constante is not None)):
                return Operando(mangleado, info['tipo'])
            if valor_constante is not None:
                return valor_constante
            self.errores.semantico(linea, f"La variable COMPTIME '{nombre}' se usa antes de que se le asigne un valor conocido en compilación.")
            return ERR

        return Operando(mangleado, info['tipo'])

    def variable_destino(self, nombre, linea) -> Operando:
        """
        Escritura (lvalue): Se usa cuando la variable va al lado izquierdo de una asignación.
        NO exige valor previo porque se le asignará uno en este paso.
        """
        mangleado, info = self.ambitos.resolver(nombre, linea)
        if info is None:
            return ERR
        if info.get('uso') not in ('variable', 'parametro'):
            self.errores.semantico(linea, f"'{nombre}' es {info.get('uso')} y se usa como variable.")
            return ERR

        return Operando(mangleado, info['tipo'])


    """
    a diferencia de lo que pasaba en gestor de ambitos, estos tipos de datos son inmutables y globales a lo largo
    de todo el programa, por eso se tratan aquí directamente
    """
    def constante_ui(self, valor) -> Operando:
        lexema = f"{valor}$ui"   
        self.tabla.registrar(lexema, 'CONST_UI', tipo=UINTEGER)
        return Operando(lexema, UINTEGER)

    def constante_float(self, lexema) -> Operando:
        self.tabla.registrar(lexema, 'FLOAT', tipo=DOUBLEF)
        return Operando(lexema, DOUBLEF)


    """
    se ayuda de gestor de ámbitos para declarar variables, ya que el gestor no sabe cuando es válido.
    Solo se usa para declararlo en tabla de simbolos de forma correcta
    """
    def declarar_variables(self, tipo, nombres, linea, comptime=False):
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
        nombre, _, ambito = objeto_mangleado.partition(':')
        return f"{nombre}.{miembro}:{ambito}"

    def _instanciar_objeto(self, mangleado, clase):
        ambito = self.ambitos.ambito_actual()
        for propietario, miembro, info in self.ambitos.atributos_de_jerarquia(clase):
            inst = self._nombre_instancia(mangleado, miembro)
            if self.tabla.buscar(inst) is None:
                self.tabla.registrar(inst, 'ID', tipo=info['tipo'], uso='variable',
                                     ambito=ambito, objeto=mangleado, propietario=propietario)


    def acceso_miembro_punto(self, obj: Operando, miembro, linea) -> Operando:
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


    """
    resuelve si dos expresiones con distintos tipos pueden 
    compatibilizarse bajo un mismo tipo al usarse TOUI
    """
    def _unificar(self, izq: Operando, der: Operando, linea):
        t1, t2 = izq.tipo, der.tipo
        if t1 not in TIPOS_BASICOS or t2 not in TIPOS_BASICOS:
            self.errores.semantico(linea, f"operación no válida entre '{t1}' y '{t2}'.")
            return None
        if t1 == t2:
            return t1, izq.ref, der.ref
        if not (izq.conv or der.conv):
            self.errores.semantico(
                linea, f"operandos de tipos distintos ({t1} y {t2}) sin conversión explícita; "
                       f"hace falta TOUI.")
            return None
        # El operando DOUBLEF se convierte a UINTEGER (conversión implícita) y el
        # resultado queda UINTEGER.
        if t1 == DOUBLEF:
            return UINTEGER, self.unidad.emitir('TOUI', izq.ref, None, UINTEGER), der.ref
        return UINTEGER, izq.ref, self.unidad.emitir('TOUI', der.ref, None, UINTEGER)


    def operacion(self, op, izq, der, linea) -> Operando:
        if ERROR in (izq.tipo, der.tipo):
            return ERR
        r = self._unificar(izq, der, linea)
        if r is None:
            return ERR
        tipo, ref1, ref2 = r
        conv = izq.conv or der.conv

        
        # Reduce expresiones constantes en tiempo de compilación (transformando 2$ui + 3$ui directamente en 5$ui)
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

        # Plegado de constantes flotantes (2.0 + 3.0 -> 5.0)
        elif tipo == DOUBLEF and self._es_constante(izq.ref) and self._es_constante(der.ref):
            val1, val2 = self._flt(izq.ref), self._flt(der.ref)
            if op == '/' and val2 == 0.0:
                self.errores.semantico(linea, "División por cero en tiempo de compilación.")
                return ERR
            res = {'+': lambda: val1 + val2, '-': lambda: val1 - val2,
                   '*': lambda: val1 * val2, '/': lambda: val1 / val2}[op]()
            cero_exacto = res == 0.0 and (val1 == 0.0 or val2 == 0.0 or op in '+-')
            # Fuera de rango (overflow/underflow) no se pliega: el terceto conserva el
            # control de ejecución.
            if cero_exacto or MIN_POS < abs(res) < MAX_POS:
                return self.constante_float(repr(res + 0.0))

        return Operando(self.unidad.emitir(op, ref1, ref2, tipo), tipo, conv)

    def negar(self, expr, linea) -> Operando:
        if expr.tipo == ERROR:
            return ERR
        if expr.tipo == UINTEGER:
            self.errores.semantico(linea, "no se puede aplicar signo negativo a un UINTEGER.")
            return ERR
        if expr.tipo == DOUBLEF and self._es_constante(expr.ref):
            return self.constante_float(repr(-self._flt(expr.ref) + 0.0))
        return Operando(self.unidad.emitir('NEG', expr.ref, None, expr.tipo), expr.tipo, expr.conv)

    def comparacion(self, op, izq, der, linea) -> Operando:
        if ERROR in (izq.tipo, der.tipo):
            return ERR
        r = self._unificar(izq, der, linea)
        if r is None:
            return ERR
        _, ref1, ref2 = r
        return Operando(self.unidad.emitir(op, ref1, ref2, BOOL), BOOL)

    def convertir_toui(self, expr, linea) -> Operando:
        if expr.tipo == ERROR:
            return ERR
        if expr.tipo != DOUBLEF:
            self.errores.semantico(linea, f"TOUI espera una expresión DOUBLEF y recibió {expr.tipo}.")
            return ERR
        return Operando(self.unidad.emitir('TOUI', expr.ref, None, UINTEGER), UINTEGER, True)

    def _es_comptime_puro(self, ref) -> bool:
        if isinstance(ref, int):
            t = self.unidad.tercetos[ref]
            if t.op in ARIT_OPS or t.op in ('NEG', 'TOUI', 'CONV'):
                return self._es_comptime_puro(t.a1) and (t.a2 is None or self._es_comptime_puro(t.a2))
            return False
        if not isinstance(ref, str):
            return False
        if self._es_constante(ref):
            return True
        info = self.tabla.buscar(ref)
        return bool(info and info.get('comptime'))

    def _cond_estatica(self, cond) -> bool:
        """para variables comptime la condición de un IF o WHILE se puede resolver en compilación si ambos operandos de la
        comparación son constantes (las variables comptime ya fueron reemplazadas por su valor)."""
        if cond.tipo == ERROR:
            return True                 
        if not isinstance(cond.ref, int):
            return False
        t = self.unidad.tercetos[cond.ref]
        return self._es_comptime_puro(t.a1) and self._es_comptime_puro(t.a2)

    def _es_constante(self, ref) -> bool:
        return isinstance(ref, str) and (ref.endswith('$ui') or self.tabla.buscar(ref, 'FLOAT') is not None)

    @staticmethod
    def _flt(ref) -> float:
        """Lexema de constante flotante (admite exponente con 'd') -> float."""
        return float(ref.lower().replace('d', 'e'))

    # ---------------- estado COMPTIME (para IF) ----------------
    def _estado_ct(self):
        return (dict(self.ambitos.valores_comptime), set(self.ct_en_ejecucion))

    def _poner_estado_ct(self, estado):
        valores, ejec = estado
        vc = self.ambitos.valores_comptime
        vc.clear()
        vc.update(valores)
        self.ct_en_ejecucion.clear()
        self.ct_en_ejecucion.update(ejec)

    def _fusionar_ct(self, a, b):
        """Une los estados de dos caminos posibles. Lo que coincide se conserva;
        lo que difiere pasa a ser variable de ejecución (valor desconocido en compilación)."""
        va, ea = a
        vb, eb = b
        nuevos_v, nuevos_e = {}, set()
        for n in set(va) | set(vb) | ea | eb:
            if (va.get(n), n in ea) == (vb.get(n), n in eb):
                if n in va:
                    nuevos_v[n] = va[n]
                if n in ea:
                    nuevos_e.add(n)
            else:
                nuevos_e.add(n)
        self._poner_estado_ct((nuevos_v, nuevos_e))

    def asignacion(self, destino, expr, linea) -> Operando:
        if ERROR in (destino.tipo, expr.tipo):
            return destino
        
        compatible = destino.tipo == expr.tipo or (
            PERMITE_ENTERO_A_FLOAT and destino.tipo == DOUBLEF and expr.tipo == UINTEGER)

        if not compatible:
            self.errores.semantico(linea, f"asignación incompatible: destino {destino.tipo}, expresión {expr.tipo}.")
            return destino

        info_destino = self.tabla.buscar(destino.ref)
        if info_destino and info_destino.get('comptime') and info_destino.get('uso') != 'parametro':
            if any(self.pila_dinamica):
                self.errores.semantico(
                    linea,
                    f"La variable COMPTIME '{info_destino['lexema']}' no puede modificarse dentro de un IF/WHILE "
                    f"cuya condición no se puede determinar en tiempo de compilación.")
                return destino
            if self.nivel_while > 0 and self._es_comptime_puro(expr.ref):
                # dentro de un WHILE el valor deja de ser conocido, también al salir del bucle
                self.ambitos.valores_comptime.pop(destino.ref, None)
                self.ct_en_ejecucion.add(destino.ref)
            elif self._es_constante(expr.ref):
                self.ambitos.registrar_valor_comptime(destino.ref, expr, linea)
                self.ct_en_ejecucion.discard(destino.ref)   # vuelve a ser conocida
            else:
                self.errores.semantico(
                    linea,
                    f"A la variable COMPTIME '{info_destino['lexema']}' solo se le pueden asignar valores determinables en tiempo de compilación (no variables comunes)."
                )

        self.unidad.emitir(':=', destino.ref, expr.ref, destino.tipo)
        return destino

    def salida_expresion(self, expr):
        if expr.tipo != ERROR:
            self.unidad.emitir('POUT', expr.ref, None, expr.tipo)

    def salida_cadena(self, texto):
        # El léxico entrega el texto SIN llaves, pero la clave en la TS es el lexema original
        # CON llaves; se reconstruye acá para referenciar la TS.
        lexema_ts = '{' + texto + '}'
        self.unidad.emitir('POUT', lexema_ts, None, 'CADENA')

    def iniciar_funcion(self, nombre_mangleado, tipo_retorno):
        self.pila_unidades.append(UnidadCodigo(nombre_mangleado))
        self.pila_funciones.append({'nombre': nombre_mangleado, 'tipo': tipo_retorno,
                                    'cant_ret': 0, 'rets': []})   # [(idx_terceto, tipo)]

    def retorno(self, expr, linea):
        if not self.pila_funciones:
            self.errores.semantico(linea, "'ret' fuera de una función.")
            return
        f = self.pila_funciones[-1]
        f['cant_ret'] += 1
        if expr.tipo == ERROR:
            return
        if f['tipo'] == 'AUTO':
            idx_ph = self.unidad.emitir('NOP', expr.ref, None, expr.tipo)
            idx_ret = self.unidad.emitir('RET', expr.ref, None, expr.tipo)
            f['rets'].append((idx_ph, idx_ret, expr.ref, expr.tipo))
        else:
            self.unidad.emitir('RET', expr.ref, None, expr.tipo)
            if f['tipo'] != expr.tipo:
                self.errores.semantico(linea,
                    f"'ret' devuelve {expr.tipo} pero la función '{f['nombre']}' devuelve {f['tipo']}.")

    def finalizar_funcion(self, linea):
        info = self.pila_funciones[-1]        
        tipo = info['tipo']

        if tipo == 'AUTO':
            info['auto'] = True
            if info['rets']:
                tipo = max((r[3] for r in info['rets']), key=JERARQUIA.get)
                for idx_ph, idx_ret, ref, t in info['rets']:
                    if t != tipo:
                        self.unidad.reemplazar(idx_ph, 'CONV', ref, None, tipo)
                        self.unidad.reemplazar(idx_ret, 'RET', self.unidad.ref(idx_ph), None, tipo)
                    else:
                        self.unidad.reemplazar(idx_ph, 'NOP', None, None, None)
            else:
                if info['cant_ret'] == 0:
                    self.errores.semantico(linea,
                        f"La función AUTO '{info['nombre']}' debe tener al menos un 'ret'.")
                tipo = ERROR                   
            info['tipo'] = tipo                 

        if tipo in VALOR_DEFECTO:
            if tipo == UINTEGER:
                self.constante_ui(0)
            else:
                self.constante_float('0.0')
            self.unidad.emitir('RET', VALOR_DEFECTO[tipo], None, tipo)

        self.pila_funciones.pop()
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
            mang = self.ambitos.declarar(prm['id'], tipo, 'parametro', linea,
                                         comptime=bool(prm.get('comptime')))
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
            self.tabla.registrar(mang, 'ID', parametros=params, unidad=mang,
                                 ct_params=[bool(p.get('comptime')) for p in parametros])
        self.iniciar_funcion(mang, tipo_retorno)
        return mang

    def _resolver_tipo_auto(self, info, linea):
        """El tipo ya fue calculado en finalizar_funcion; acá se propaga a la TS
        para que las invocaciones posteriores vean el tipo real y no 'AUTO'."""
        if not info.get('auto'):
            return
        simbolo = self.tabla.buscar(info['nombre'])
        if simbolo is not None:
            simbolo['tipo'] = info['tipo']

    def finalizar_funcion_decl(self, linea):
        info = self.finalizar_funcion(linea)
        self._resolver_tipo_auto(info, linea)
        self.ambitos.salir()


    def _emitir_llamada(self, info, args, linea, nombre, antes=(), despues=()):
        params = info.get('parametros', [])
        if any(a.tipo == ERROR for a in args) or info.get('tipo') == ERROR:
            return ERR
        if len(args) != len(params):
            self.errores.semantico(linea, f"'{nombre}' espera {len(params)} argumento(s) y recibió {len(args)}.")
            return ERR
        ok = True
        ct = info.get('ct_params') or []
        for i, (a, (_, tipo_param)) in enumerate(zip(args, params), 1):
            if a.tipo == tipo_param and i <= len(ct) and ct[i - 1] and not self._es_constante(a.ref):
                self.errores.semantico(linea, f"argumento {i} de '{nombre}': el parámetro es COMPTIME y el "
                                              f"argumento debe ser un valor conocido en tiempo de compilación.")
                ok = False
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

    def _tope_es(self, *tipos) -> bool:
        return bool(self.pila_control) and self.pila_control[-1][0] in tipos

    def if_condicion(self, cond, linea):
        """TERMINA LA CONDICIÓN: 1) crea el BF incompleto  2) apila su número."""
        if cond.tipo not in (BOOL, ERROR):
            self.errores.semantico(linea, "la condición del IF debe ser una comparación.")
        self.pila_dinamica.append(not self._cond_estatica(cond))
        self.pila_ct_if.append({'ini': self._estado_ct(), 'then': None})
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
        # el else parte del estado previo al if; se guarda lo que dejó el then
        if self.pila_ct_if:
            e = self.pila_ct_if[-1]
            e['then'] = self._estado_ct()
            self._poner_estado_ct(e['ini'])

    def if_fin(self):
        """FIN DEL IF: desapila el salto pendiente y lo completa con el próximo terceto.
        Fusiona los estados comptime de los dos caminos posibles."""
        if not self._tope_es('BF', 'BI'):
            return
        _, pendiente = self.pila_control.pop()
        if self.pila_dinamica:
            self.pila_dinamica.pop()
        if self.pila_ct_if:
            e = self.pila_ct_if.pop()
            otro = e['then'] if e['then'] is not None else e['ini']   # sin else: el camino "no entra"
            self._fusionar_ct(otro, self._estado_ct())
        self.unidad.completar_salto(pendiente, self.unidad.proximo())

    def while_inicio(self):
        """ANTES DE LA CONDICIÓN: apila el número del terceto donde empieza."""
        self.nivel_while += 1
        self.pila_control.append(('INICIO', self.unidad.proximo()))

    def while_condicion(self, cond, linea):
        """TERMINA LA CONDICIÓN: crea el BF incompleto y apila su número."""
        if cond.tipo not in (BOOL, ERROR):
            self.errores.semantico(linea, "la condición del WHILE debe ser una comparación.")
        self.pila_dinamica.append(not self._cond_estatica(cond))
        bf = self.unidad.emitir('BF', cond.ref, None)
        self.pila_control.append(('BF', bf))

    def while_fin(self):
        """FIN DEL CUERPO: desapila BF e inicio, genera el BI al inicio y completa el BF."""
        if (len(self.pila_control) < 2 or self.pila_control[-1][0] != 'BF'
                or self.pila_control[-2][0] != 'INICIO'):
            return
        _, bf = self.pila_control.pop()
        _, inicio = self.pila_control.pop()
        if self.pila_dinamica:
            self.pila_dinamica.pop()
        self.nivel_while -= 1
        self.unidad.emitir('BI', inicio)
        self.unidad.completar_salto(bf, self.unidad.proximo())

    def control_pendiente(self):
        """Para depurar: saltos que quedaron sin completar (debería ser lista vacía)."""
        return list(self.pila_control)

    def iniciar_clase(self, nombre_clase, linea, clase_padre=None):
        return self.ambitos.iniciar_clase(nombre_clase, linea, clase_padre)

    def cerrar_clase(self, nombre_clase, linea):
        return self.ambitos.cerrar_clase(nombre_clase, linea)

    def declarar_atributo(self, tipo, nombre, visibilidad, linea):
        if tipo not in TIPOS_BASICOS:
            self.errores.semantico(linea, f"el atributo '{nombre}' debe ser UINTEGER o DOUBLEF (no se soportan atributos de tipo clase).")
            tipo = ERROR
        return self.ambitos.declarar_miembro(tipo, nombre, 'variable', visibilidad, linea)

    def registrar_herencia(self, nombres, linea):
        return self.ambitos.registrar_herencia(nombres, linea)

    def registrar_amigo(self, nombre_amigo, linea):
        return self.ambitos.registrar_amigo(nombre_amigo, linea)

    def imprimir(self):
        for u in self.terminadas:
            u.imprimir()
        self.unidad.imprimir()