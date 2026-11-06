"""
AnalizadorSintactico.py  -  TP2 -> TP3  (Grupo 19)

=====================================================================================
REGISTRO DE CAMBIOS  (todo lo modificado respecto de la versión del TP2 lleva la
marca  [PASO n]  en un comentario, para poder buscarlo con Ctrl+F)
=====================================================================================
OBJETIVO DE LA MIGRACIÓN: pasar de "reglas que arman un pseudo-árbol (diccionarios)"
a "reglas que generan tercetos" llamando al GeneradorCodigo de codigo_intermedio.py.
Se hace de a poco: lo migrado devuelve Operando (expresiones) o None (sentencias ya
generadas); lo NO migrado sigue devolviendo diccionarios hasta su paso.

[PASO 1]  (este archivo)
  - Migrado a tercetos : expresiones (+ - * /, signo menos, TOUI, constantes, variables),
                         asignación ':=', asignación embebida '=' (tema 18), POUT,
                         declaración de variables en el ámbito global (main).
  - Sigue como AST     : declaraciones de funciones/clases, condicion, IF, WHILE, RET,
                         invocaciones, acceso a atributos.   (pasos 2 a 5)
  - TEMPORAL           : invocaciones y 'ID.ID' devuelven ERR (un Operando de error) para que
                         no se generen errores en cascada hasta que se migren.
  - __init__ recibe ahora el GeneradorCodigo.
  - Las constantes flotantes llegan como el LEXEMA de la TS (ver cambio en el léxico).
  - Las reglas de error 'expresion PLUS/MINUS error' devuelven ERR en vez de un dict.
  - MOSTRAR_AST permite apagar la impresión del pseudo-árbol cuando ya no haga falta.
  - json.dumps usa default=str porque el AST ahora puede contener Operandos.

[PASO 2]
  - Migrado a tercetos : condicion, IF, IF-ELSE, WHILE ... REPEAT (tema 11).
  - Nuevos no terminales marcador: inicio_if, rama_else, inicio_while, cabecera_while
    (SLY no admite acciones a mitad de regla; ver comentarios en las reglas).
  - Las reglas de error de IF/WHILE se reescribieron sobre esos marcadores. Cada una
    sigue emitiendo/cerrando los saltos para no desbalancear la pila de control.
  - 'comparador' devuelve (operador, línea).
  - CORREGIDO: el mensaje de 'falta ")"' en WHILE decía 'falta "("'.
  - Ya no se construye ningún dict para IF / WHILE / condicion.

[PASO 2 - REVISIÓN]
  - Las reglas de error de IF/WHILE seguían escritas en la forma VIEJA (IF "(" condicion
    ")" bloque ...) y devolvían dicts. Compartían prefijo con los marcadores y generaban
    conflictos shift/reduce que impedían reducir 'inicio_if'. Ahora TODAS están sobre los
    marcadores (inicio_if / rama_else / cabecera_while) y llaman a gen.if_fin()/while_fin().
  - Los errores de paréntesis y de 'repeat' pasaron DENTRO de los marcadores (inicio_if,
    cabecera_while), así el BF se emite igual aunque falte un símbolo.
  - Generador sin tercetos LABEL (ver CodigoIntermedio.py).
  - main: imprime los saltos sin completar (debe ser []).

[PASO 3]  Funciones, invocaciones, RET y AUTO migrados a tercetos
  - Marcadores (igual que en IF/WHILE) para abrir y cerrar el ÁMBITO de la función:
        nombre_funcion  : <tipo> FUNCTION ID | FUNCTION ID | (variantes con 'error')
        nombre_auto     : AUTO FUNCTION ID | AUTO FUNCTION error
        encabezado_funcion / encabezado_auto : nombre "(" lista_parametros ")"
        declaracion_funcion : encabezado bloque_declarativo cuerpo ";"
    Se mantienen DOS encabezados para conservar la distinción original: AUTO exige
    'bloque_auto' (termina con ret) y las demás 'bloque_obligatorio'.
  - Las 3 reglas de declaración de función y sus 3 reglas de error ('falta el nombre')
    dejaron de armar dicts: ahora declaran, abren el ámbito y devuelven None.
  - sentencia_retorno : genera (RET, expr, -) y chequea el tipo contra la función.
  - invocacion_funcion: chequea existencia, uso, cantidad y tipos de parámetros; genera la
    copia de cada real sobre su formal y el terceto CALL. Devuelve un Operando.
  - factor : invocacion_funcion  ->  una función VOID no puede usarse en una expresión.
  - CORRECCIONES pedidas al analizador:
      * funciones con al menos UN parámetro (se informa si no hay ninguno)
      * AUTO sin ret: nueva regla 'BEGIN sentencias_no_retorno END' (antes el parser decía
        "símbolo inesperado 'end'"; ahora informa la falta de retorno)
  - LIMITACIÓN TEMPORAL: los MÉTODOS de clase siguen sin ámbito propio (PASO 5): si el
    cuerpo de un método usa 'ret' o variables, se compila contra 'main' y puede dar
    errores falsos. Los tests de este paso no usan clases.

PRÓXIMOS PASOS PREVISTOS
  [PASO 4] COMPTIME
  [PASO 4] COMPTIME
  [PASO 5] clases, private/friend, acceso con '.', herencia (+ corrección de 'extends')
=====================================================================================
"""

import json
from sly import Parser
from AnalizadorLexico import AnalizadorLexico
# [PASO 1] CAMBIO: se importa la infraestructura de tercetos desde el archivo aparte.
# [PASO 3] CAMBIO: además se importan VOID y AUTO (tipos de retorno de las funciones).
from CodigoIntermedio import (GeneradorCodigo, GestorAmbitos, Errores,
                               TablaSimbolosSemantica, ERR, VOID, AUTO)

# [PASO 1] NUEVO: interruptor para el pseudo-árbol. Dejarlo en True mientras queden
# partes sin migrar; ponerlo en False cuando todo genere tercetos.
MOSTRAR_AST = True


class AnalizadorSintactico(Parser):
    tokens = AnalizadorLexico.tokens
    start = 'programa'

    # [PASO 1] NUEVO (herramienta de SLY): descomentar para que SLY escriba 'parser.out'
    # con los estados, la gramática y TODOS los conflictos shift/reduce y reduce/reduce.
    # debugfile = 'parser.out'

    # [PASO 1] CAMBIO: el constructor recibe también el generador de código intermedio.
    def __init__(self, tabla_simbolos, generador):
        self.tabla = tabla_simbolos
        self.gen = generador

    # [PASO 1] NUEVO: número de línea de una producción.
    # En SLY, p.lineno devuelve la línea del primer TERMINAL de la regla; si la regla
    # tiene solo no-terminales (ej. 'expresion : termino') lanza AttributeError.
    def _linea(self, p):
        try:
            return p.lineno
        except AttributeError:
            return 0

    precedence = (
        ('right', 'ASSIGN'),
        ('left', 'PLUS', 'MINUS'),
        ('left', 'TIMES', 'DIVIDE'),
        ('right', 'UMINUS'),
    )

    @_('ID bloque_declarativo bloque_obligatorio')
    def programa(self, p):
        ast = {
            'nodo': 'PROGRAMA',
            'nombre': p.ID,
            'declaraciones': p.bloque_declarativo,
            'ejecutables': p.bloque_obligatorio,
        }
        # [PASO 1] CAMBIO: impresión condicionada por MOSTRAR_AST y con default=str
        if MOSTRAR_AST:
            print(json.dumps(ast, indent=2, ensure_ascii=False, default=str))
        return ast

    @_('declaraciones')
    def bloque_declarativo(self, p):
        return p.declaraciones

    @_('')
    def bloque_declarativo(self, p):
        return []

    @_('declaracion declaraciones')
    def declaraciones(self, p):
        return [p.declaracion] + p.declaraciones

    @_('declaracion')
    def declaraciones(self, p):
        return [p.declaracion]

    @_(
        'declaracion_comun',
        'declaracion_comptime',
        'declaracion_funcion',
        'declaracion_clase'
    )
    def declaracion(self, p):
        return p[0]

    @_('var_decl_base ";"')
    def declaracion_comun(self, p):
        # [PASO 1] NUEVO: se registran las variables en la TS con su tipo y ámbito.
        # LIMITACIÓN TEMPORAL: todavía no hay ámbitos de función/clase (paso 3 y 5),
        # así que lo declarado dentro de una función o clase cae en 'main'.
        self.gen.declarar_variables(p.var_decl_base['tipo_dato'],
                                    p.var_decl_base['variables'],
                                    self._linea(p))
        return {
            'tipo': 'DECLARACION_VARIABLES',
            'tipo_dato': p.var_decl_base['tipo_dato'],
            'variables': p.var_decl_base['variables'],
        }

    @_('COMPTIME var_decl_base ";"')
    def declaracion_comptime(self, p):
        # [PASO 1] NUEVO: se declara igual que una variable común, marcada comptime=True.
        # La semántica real del tema 22 se agrega en el PASO 4.
        self.gen.declarar_variables(p.var_decl_base['tipo_dato'],
                                    p.var_decl_base['variables'],
                                    self._linea(p), comptime=True)
        return {
            'tipo': 'DECLARACION_COMPTIME',
            'tipo_dato': p.var_decl_base['tipo_dato'],
            'variables': p.var_decl_base['variables'],
        }

    @_('tipo_dato lista_ids')
    def var_decl_base(self, p):
        return {
            'tipo_dato': p.tipo_dato,
            'variables': p.lista_ids
        }

    # ------------------------------------------------------------------
    # [PASO 3] FUNCIONES migradas a tercetos.
    #
    # PROBLEMA: el ámbito de la función hay que abrirlo ANTES de leer sus parámetros y su
    # cuerpo (para que queden como x:main:aa) y cerrarlo al final. SLY no permite acciones a
    # mitad de regla, así que (igual que en IF/WHILE) la declaración se parte en no
    # terminales "marcador":
    #
    #   nombre_funcion      : <tipo> FUNCTION ID | FUNCTION ID   -> declara la función y ABRE su ámbito
    #   nombre_auto         : AUTO FUNCTION ID                   -> idem, con tipo AUTO (tema 21)
    #   encabezado_*        : nombre "(" lista_parametros ")"    -> declara los parámetros formales
    #   declaracion_funcion : encabezado bloque_declarativo cuerpo ";"   -> CIERRA el ámbito
    #
    # Se mantienen DOS encabezados (normal / AUTO) para no perder la distinción de la
    # gramática original: la AUTO exige 'bloque_auto' (termina con ret) y las demás usan
    # 'bloque_obligatorio'. Ya no se arma ningún dict: estas reglas devuelven None.
    # ------------------------------------------------------------------

    # [PASO 3] NUEVO: tipada. El nombre y el tipo se declaran en la TS (nombre:ámbito).
    @_('tipo_dato FUNCTION ID')
    def nombre_funcion(self, p):
        self.gen.iniciar_funcion(p.ID, p.tipo_dato, self._linea(p))
        return None

    # [PASO 3] NUEVO: sin tipo = VOID.
    @_('FUNCTION ID')
    def nombre_funcion(self, p):
        self.gen.iniciar_funcion(p.ID, VOID, self._linea(p))
        return None

    # [PASO 3] NUEVO: AUTO (tema 21). Su tipo real se fija al terminar de compilarla.
    @_('AUTO FUNCTION ID')
    def nombre_auto(self, p):
        self.gen.iniciar_funcion(p.ID, AUTO, self._linea(p))
        return None

    # [PASO 3] NUEVO: se reduce al leer el ")" de los parámetros, antes del cuerpo.
    @_('nombre_funcion "(" lista_parametros ")"')
    def encabezado_funcion(self, p):
        self._encabezado(p.lista_parametros, self._linea(p))
        return None

    @_('nombre_auto "(" lista_parametros ")"')
    def encabezado_auto(self, p):
        self._encabezado(p.lista_parametros, self._linea(p))
        return None

    # [PASO 3] NUEVO (no es regla): lógica común de los dos encabezados.
    def _encabezado(self, parametros, linea):
        # CORRECCIÓN pedida: antes el parser admitía funciones sin parámetros; ahora se
        # exige al menos uno. Se informa y se sigue (la función queda sin parámetros).
        if not parametros:
            self.gen.errores.sintactico(linea, "la función debe declarar al menos un parámetro.")
        self.gen.declarar_parametros(parametros, linea)

    # [PASO 3] CAMBIO: antes devolvía {'tipo': 'DECLARACION_FUNCION', ...} (tipada y VOID).
    @_('encabezado_funcion bloque_declarativo bloque_obligatorio ";"')
    def declaracion_funcion(self, p):
        self.gen.finalizar_funcion()        # RET por defecto + cierra estructura y ámbito
        return None

    # [PASO 3] CAMBIO: antes devolvía un dict con 'expresion_retorno'. 'bloque_auto' vale
    # False cuando el cuerpo no termina con ret (ver más abajo).
    @_('encabezado_auto bloque_declarativo bloque_auto ";"')
    def declaracion_funcion(self, p):
        if not p.bloque_auto:
            self.gen.falta_retorno()
        self.gen.finalizar_funcion()        # fija el tipo AUTO + cierra estructura y ámbito
        return None

    @_('CLASS ID BEGIN miembros_clase END ";"')
    def declaracion_clase(self, p):
        return {
            'tipo': 'DECLARACION_CLASE',
            'nombre': p.ID,
            'miembros': p.miembros_clase
        }

    @_('miembro_clase miembros_clase')
    def miembros_clase(self, p):
        return [p.miembro_clase] + p.miembros_clase

    @_('')
    def miembros_clase(self, p):
        return []

    @_(
        'declaracion_private_miembro',
        'declaracion_normal_miembro',
        'declaracion_friend'
    )
    def miembro_clase(self, p):
        return p[0]

    @_(
        'declaracion_comun',
        'declaracion_comptime',
        'declaracion_metodo'
    )
    def declaracion_normal_miembro(self, p):
        return p[0]

    @_('PRIVATE declaracion_normal_miembro')
    def declaracion_private_miembro(self, p):
        miembro = p[1].copy()
        miembro['privado'] = True
        return miembro

    @_('FRIEND ID ";"')
    def declaracion_friend(self, p):
        return {
            'tipo': 'DECLARACION_FRIEND',
            'nombre': p.ID
        }

    @_('tipo_dato ID "(" lista_parametros ")" bloque_declarativo bloque_obligatorio ";"')
    def declaracion_metodo(self, p):
        return {
            'tipo': 'DECLARACION_METODO',
            'retorno': p.tipo_dato,
            'nombre': p.ID,
            'parametros': p.lista_parametros,
            'declaraciones_locales': p.bloque_declarativo,
            'cuerpo_ejecutable': p.bloque_obligatorio
        }

    @_('ID "(" lista_parametros ")" bloque_declarativo bloque_obligatorio ";"')
    def declaracion_metodo(self, p):
        return {
            'tipo': 'DECLARACION_METODO',
            'retorno': 'VOID',
            'nombre': p.ID,
            'parametros': p.lista_parametros,
            'declaraciones_locales': p.bloque_declarativo,
            'cuerpo_ejecutable': p.bloque_obligatorio
        }

    @_('ID "," lista_ids')
    def lista_ids(self, p):
        return [p.ID] + p.lista_ids

    @_('ID')
    def lista_ids(self, p):
        return [p.ID]

    @_('')
    def lista_parametros(self, p):
        return []

    @_('parametro "," lista_parametros')
    def lista_parametros(self, p):
        return [p.parametro] + p.lista_parametros

    @_('parametro')
    def lista_parametros(self, p):
        return [p.parametro]

    @_('tipo_dato ID')
    def parametro(self, p):
        return {
            'tipo_dato': p.tipo_dato,
            'id': p.ID
        }

    @_('sentencia ";" sentencias_ejecutables')
    def sentencias_ejecutables(self, p):
        return [p.sentencia] + p.sentencias_ejecutables

    @_('sentencia ";"')
    def sentencias_ejecutables(self, p):
        return [p.sentencia]

    @_('BEGIN sentencias_ejecutables END')
    def bloque_obligatorio(self, p):
        return p.sentencias_ejecutables

    @_('bloque_obligatorio')
    def bloque_o_sentencia(self, p):
        return p.bloque_obligatorio

    @_('sentencia ";"')
    def bloque_o_sentencia(self, p):
        return [p.sentencia]

    @_(
        'asignacion',
        'salida',
        'sentencia_if',
        'sentencia_while',
        'invocacion_funcion',
        'invocacion_metodo_objeto'
    )
    def sentencia_no_retorno(self, p):
        return p[0]

    @_('sentencia_no_retorno ";" sentencias_no_retorno')
    def sentencias_no_retorno(self, p):
        return [p.sentencia_no_retorno] + p.sentencias_no_retorno

    @_('sentencia_no_retorno ";"')
    def sentencias_no_retorno(self, p):
        return [p.sentencia_no_retorno]

    @_('sentencia_no_retorno', 'sentencia_retorno')
    def sentencia(self, p):
        return p[0]

    # [PASO 3] CAMBIO: antes devolvían {'cuerpo': ..., 'retorno': ...}. El ret ya generó su
    # terceto en 'sentencia_retorno'; ahora devuelven True = "el cuerpo termina con ret".
    @_('BEGIN sentencias_no_retorno sentencia_retorno ";" END')
    def bloque_auto(self, p):
        return True

    @_('BEGIN sentencia_retorno ";" END')
    def bloque_auto(self, p):
        return True

    # [PASO 3] NUEVO (corrección pedida): cuerpo AUTO sin retorno. Antes el parser informaba
    # "símbolo inesperado 'end'". Ahora la regla acepta ese cuerpo, devuelve False y
    # declaracion_funcion informa claramente la falta de retorno.
    @_('BEGIN sentencias_no_retorno END')
    def bloque_auto(self, p):
        return False

    # ------------------------------------------------------------------
    # [PASO 2] IF / WHILE migrados a tercetos.
    #
    # PROBLEMA: los saltos hay que emitirlos en puntos INTERMEDIOS de la regla
    # (después de la condición, al llegar al ELSE, etc.) y SLY no permite acciones a
    # mitad de regla. SOLUCIÓN: partir la regla en no terminales "marcador"
    # (inicio_if, rama_else, inicio_while, cabecera_while). Cada uno se reduce justo
    # en el punto donde hace falta emitir el terceto.
    #
    # Los destinos de salto que aún no se conocen se completan después
    # (BACKPATCHING) usando la pila de control del generador.
    #
    #   (sin tercetos LABEL: los destinos son números de terceto)
    #   IF (c) A end_if           ->  c ; BF c,->fin ; A
    #   IF (c) A else B end_if    ->  c ; BF c,->B ; A ; BI ->fin ; B
    #   WHILE (c) repeat A        ->  [ini:] c ; BF c,->fin ; A ; BI ->ini
    # ------------------------------------------------------------------

    # [PASO 2] NUEVO: se reduce al terminar de leer la condición, antes del cuerpo.
    @_('IF "(" condicion ")"')
    def inicio_if(self, p):
        self.gen.if_condicion(p.condicion, self._linea(p))      # emite BF pendiente
        return None

    # [PASO 2 - REVISIÓN] errores de paréntesis DENTRO del marcador: el BF se emite igual.
    @_('IF error condicion ")"')
    def inicio_if(self, p):
        print(f'ERROR (Línea {self._linea(p)}): falta "(" en la sentencia if')
        self.gen.if_condicion(p.condicion, self._linea(p))
        return None

    @_('IF "(" condicion error')
    def inicio_if(self, p):
        print(f'ERROR (Línea {self._linea(p)}): falta ")" en la sentencia if')
        self.gen.if_condicion(p.condicion, self._linea(p))
        return None

    # [PASO 2] NUEVO: se reduce al leer el ELSE, antes de la rama else.
    @_('ELSE')
    def rama_else(self, p):
        self.gen.if_else()      # emite BI (cierra el then) y completa el BF con DIR_ACTUAL+2
        return None

    # [PASO 2] CAMBIO: antes devolvía {'tipo': 'IF_ELSE', ...}. Ahora solo cierra el IF.
    @_('inicio_if bloque_o_sentencia rama_else bloque_o_sentencia END_IF')
    def sentencia_if(self, p):
        self.gen.if_fin()       # completa el BI del then con DIR_ACTUAL+1
        return None

    # [PASO 2] CAMBIO: antes devolvía {'tipo': 'IF', ...}.
    @_('inicio_if bloque_o_sentencia END_IF')
    def sentencia_if(self, p):
        self.gen.if_fin()       # completa el BF con DIR_ACTUAL+1
        return None

    # [PASO 2] NUEVO: se reduce ANTES de leer '(' para apilar el número del terceto donde
    # empieza la condición (los tercetos de la condición se emiten al reducir sus expresiones).
    @_('WHILE')
    def inicio_while(self, p):
        self.gen.while_inicio()
        return None

    # [PASO 2] NUEVO: se reduce después de REPEAT, antes del cuerpo.
    @_('inicio_while "(" condicion ")" REPEAT')
    def cabecera_while(self, p):
        self.gen.while_condicion(p.condicion, self._linea(p))   # emite BF pendiente
        return None

    # [PASO 2 - REVISIÓN] errores dentro del marcador: el BF se emite igual.
    @_('inicio_while error condicion ")" REPEAT')
    def cabecera_while(self, p):
        print(f'ERROR (Línea {self._linea(p)}): falta "(" en la sentencia while')
        self.gen.while_condicion(p.condicion, self._linea(p))
        return None

    @_('inicio_while "(" condicion error REPEAT')
    def cabecera_while(self, p):
        print(f'ERROR (Línea {self._linea(p)}): falta ")" en la sentencia while')
        self.gen.while_condicion(p.condicion, self._linea(p))
        return None

    @_('inicio_while "(" condicion ")" error')
    def cabecera_while(self, p):
        print(f'ERROR (Línea {self._linea(p)}): falta "repeat" en la sentencia while')
        self.gen.while_condicion(p.condicion, self._linea(p))
        return None

    # [PASO 2] CAMBIO: antes devolvía {'tipo': 'SENTENCIA_WHILE', ...}.
    @_('cabecera_while bloque_o_sentencia')
    def sentencia_while(self, p):
        self.gen.while_fin()    # emite BI al inicio de la condición y completa el BF
        return None

    # [PASO 2 - REVISIÓN] falta el cuerpo: se cierra igual para no desbalancear la pila.
    @_('cabecera_while error')
    def sentencia_while(self, p):
        print('ERROR: falta cuerpo en la sentencia while')
        self.gen.while_fin()
        return None

    # [PASO 2] CAMBIO: antes devolvía un dict {'izquierda', 'operador', 'derecha'}.
    # Ahora emite (op, izq, der) con tipo BOOL (con chequeo de tipos del tema 34).
    @_('expresion comparador expresion')
    def condicion(self, p):
        operador, linea = p.comparador
        return self.gen.comparacion(operador, p.expresion0, p.expresion1, linea)

    @_(
        'LESS',
        'LESS_EQUAL',
        'GREATER',
        'GREATER_EQUAL',
        'EQUALS_EQUALS',
        'NOT_EQUALS',
    )
    def comparador(self, p):
        # [PASO 2] CAMBIO: devuelve (operador, línea). La regla 'condicion' solo tiene
        # no terminales, entonces no puede pedir p.lineno; la línea la aporta este token.
        return (p[0], p.lineno)

    @_('ref_variable TWO_POINTS_ASSING expresion')
    def asignacion(self, p):
        # [PASO 1] CAMBIO: antes devolvía {'tipo': 'ASIGNACION', ...}. Ahora genera el
        # terceto (:=, destino, expr) con chequeo de tipos y no devuelve nada (None).
        self.gen.asignacion(p.ref_variable, p.expresion, self._linea(p))
        return None

    @_('ID DOT ID')
    def ref_variable(self, p):
        # [PASO 1] TEMPORAL: el acceso a atributos se migra en el PASO 5. Se devuelve ERR
        # para que las expresiones que lo usen no generen errores en cascada.
        return ERR

    @_('ID')
    def ref_variable(self, p):
        # [PASO 1] CAMBIO: antes devolvía {'tipo': 'VARIABLE', ...}. Ahora resuelve el
        # nombre en la TS (visibilidad, uso, tipo) y devuelve un Operando con el nombre
        # mangleado (ej. 'a:main').
        return self.gen.variable(p.ID, self._linea(p))

    @_('RET "(" expresion ")"')
    def sentencia_retorno(self, p):
        # [PASO 3] CAMBIO: antes devolvía {'tipo': 'RETORNO', ...}. Ahora genera (RET, expr, -),
        # chequea el tipo contra el de la función (o lo acumula si es AUTO) y devuelve None.
        self.gen.retorno(p.expresion, self._linea(p))
        return None

    @_('POUT "(" TEXT_STRING ")"')
    def salida(self, p):
        # [PASO 1] CAMBIO: genera el terceto (POUT, {cadena}, -).
        self.gen.salida_cadena(p.TEXT_STRING)
        return None

    @_('POUT "(" expresion ")"')
    def salida(self, p):
        # [PASO 1] CAMBIO: genera el terceto (POUT, expr, -).
        self.gen.salida_expresion(p.expresion)
        return None

    @_('ID "(" lista_expresiones ")"')
    def invocacion_funcion(self, p):
        # [PASO 3] CAMBIO: antes devolvía {'tipo': 'INVOCACION_FUNCION', ...}. Ahora chequea
        # (existe, es función, cantidad y tipos de parámetros), genera la copia de cada real
        # sobre su formal y el terceto CALL. Devuelve un Operando (el CALL) o ERR.
        return self.gen.invocacion(p.ID, p.lista_expresiones, self._linea(p))

    @_('ID "(" ")"')
    def invocacion_funcion(self, p):
        # [PASO 3] CAMBIO: igual que arriba, sin argumentos.
        return self.gen.invocacion(p.ID, [], self._linea(p))

    @_('ID DOT ID "(" lista_expresiones ")"')
    def invocacion_metodo_objeto(self, p):
        return {
            'tipo': 'INVOCACION_METODO',
            'objeto': p.ID0,
            'metodo': p.ID1,
            'argumentos': p.lista_expresiones,
        }

    @_('ID DOT ID "(" ")"')
    def invocacion_metodo_objeto(self, p):
        return {
            'tipo': 'INVOCACION_METODO',
            'objeto': p.ID0,
            'metodo': p.ID1,
            'argumentos': []
        }

    @_('expresion "," lista_expresiones')
    def lista_expresiones(self, p):
        return [p.expresion] + p.lista_expresiones

    @_('expresion')
    def lista_expresiones(self, p):
        return [p.expresion]

    # ------------------------------------------------------------------
    # EXPRESIONES  [PASO 1]: migradas a tercetos
    # Cada regla devuelve un Operando (referencia + tipo). Como el análisis es
    # ascendente, los tercetos se emiten en el orden correcto de evaluación
    # (los operandos se reducen antes que el operador que los usa).
    # ------------------------------------------------------------------
    @_('expresion PLUS termino')
    def expresion(self, p):
        # [PASO 1] CAMBIO: antes {'op': '+', ...}. Ahora emite (+, izq, der).
        return self.gen.operacion('+', p.expresion, p.termino, self._linea(p))

    @_('expresion MINUS termino')
    def expresion(self, p):
        # [PASO 1] CAMBIO: emite (-, izq, der).
        return self.gen.operacion('-', p.expresion, p.termino, self._linea(p))

    @_('MINUS expresion %prec UMINUS')
    def expresion(self, p):
        # [PASO 1] CAMBIO: emite (NEG, expr, -); error si la expresión es UINTEGER.
        return self.gen.negar(p.expresion, self._linea(p))

    @_('termino')
    def expresion(self, p):
        return p.termino

    @_('ref_variable ASSIGN expresion')
    def expresion(self, p):
        # [PASO 1] CAMBIO (tema 18 + corrección pedida): antes devolvía un dict y,
        # según lo observado, el lado DERECHO terminaba siendo el operando de la
        # expresión contenedora. Ahora emite (:=, izq, der) y devuelve el Operando del
        # LADO IZQUIERDO, que es el valor que debe usar la expresión que lo contiene.
        return self.gen.asignacion(p.ref_variable, p.expresion, self._linea(p))

    @_('DOUBLEF', 'UINTEGER', 'ID')
    def tipo_dato(self, p):
        return p[0]

    @_('termino TIMES factor')
    def termino(self, p):
        # [PASO 1] CAMBIO: emite (*, izq, der).
        return self.gen.operacion('*', p.termino, p.factor, self._linea(p))

    @_('termino DIVIDE factor')
    def termino(self, p):
        # [PASO 1] CAMBIO: emite (/, izq, der).
        return self.gen.operacion('/', p.termino, p.factor, self._linea(p))

    @_('factor')
    def termino(self, p):
        return p.factor

    @_('invocacion_funcion')
    def factor(self, p):
        # [PASO 3] CAMBIO: antes devolvía ERR (temporal). Ahora el valor de la invocación es
        # el terceto CALL; si la función es VOID se informa que no puede usarse en una expresión.
        return self.gen.valor_invocacion(p.invocacion_funcion)

    @_('invocacion_metodo_objeto')
    def factor(self, p):
        # [PASO 1] TEMPORAL: se migra en el PASO 5.
        return ERR

    @_('ref_variable')
    def factor(self, p):
        return p.ref_variable

    # [PASO 1] CAMBIO: antes era una sola regla ('DOUBLEF', 'CONST_UI') que devolvía el
    # valor crudo. Se separan en dos porque cada una tiene tipo distinto.
    # OBSERVACIÓN: el token DOUBLEF se usa para la palabra reservada Y para la constante
    # flotante. Funciona porque la regla decide, pero conviene renombrar el de la
    # constante (ej. CONST_DOUBLE) para evitar conflictos futuros.
    @_('DOUBLEF')
    def factor(self, p):
        return self.gen.constante_float(p.DOUBLEF)

    @_('CONST_UI')
    def factor(self, p):
        return self.gen.constante_ui(p.CONST_UI)

    @_('TOUI "(" expresion ")"')
    def factor(self, p):
        # [PASO 1] CAMBIO (tema 34): emite (TOUI, expr, -) y el resultado es UINTEGER.
        return self.gen.convertir_toui(p.expresion, self._linea(p))

    # ==============================================================================
    # SECCIÓN DE DETECCIÓN DE ERRORES ESPECÍFICOS
    # ==============================================================================

    @_('error bloque_declarativo bloque_obligatorio')
    def programa(self, p):
        print("ERROR: Falta el nombre del programa antes del bloque declarativo.")
        ast = {
            'nodo': 'PROGRAMA',
            'nombre': 'UNKNOWN',
            'declaraciones': p.bloque_declarativo,
            'ejecutables': p.bloque_obligatorio,
        }
        if MOSTRAR_AST:     # [PASO 1] CAMBIO: igual que en la regla principal
            print(json.dumps(ast, indent=2, ensure_ascii=False, default=str))
        return ast

    @_('error sentencias_ejecutables END')
    def bloque_obligatorio(self, p):
        print('ERROR: falta "BEGIN" al comienzo del bloque ejecutable')
        return p.sentencias_ejecutables

    @_('BEGIN sentencias_ejecutables error')
    def bloque_obligatorio(self, p):
        print('ERROR: falta "END" al final del bloque ejecutable')
        return p.sentencias_ejecutables

    @_('sentencia error sentencias_ejecutables')
    def sentencias_ejecutables(self, p):
        print('ERROR: falta ";" antes de la proxima sentencia ejecutable')
        return [p.sentencia] + p.sentencias_ejecutables

    @_('sentencia error')
    def sentencias_ejecutables(self, p):
        print('ERROR: falta ";" al final de la sentencia ejecutable')
        return [p.sentencia]

    @_('sentencia error')
    def bloque_o_sentencia(self, p):
        print('ERROR: falta ";" al final de la sentencia ejecutable')
        return [p.sentencia]

    # [PASO 3] CAMBIO: los errores de "falta el nombre de la función" pasaron a los marcadores
    # (antes eran 3 reglas de declaración completa que devolvían dicts). La función se declara
    # con un nombre generado (sin_nombre_N) para poder seguir compilando su cuerpo y su ámbito.
    @_('tipo_dato FUNCTION error')
    def nombre_funcion(self, p):
        print(f'ERROR (Línea {self._linea(p)}): falta el nombre de la funcion')
        self.gen.iniciar_funcion(None, p.tipo_dato, self._linea(p), sin_nombre=True)
        return None

    @_('FUNCTION error')
    def nombre_funcion(self, p):
        print(f'ERROR (Línea {self._linea(p)}): falta el nombre de la funcion')
        self.gen.iniciar_funcion(None, VOID, self._linea(p), sin_nombre=True)
        return None

    @_('AUTO FUNCTION error')
    def nombre_auto(self, p):
        print(f'ERROR (Línea {self._linea(p)}): falta el nombre de la funcion')
        self.gen.iniciar_funcion(None, AUTO, self._linea(p), sin_nombre=True)
        return None

    @_('tipo_dato error "(" lista_parametros ")" bloque_declarativo bloque_obligatorio ";"')
    def declaracion_metodo(self, p):
        print('ERROR: falta el nombre del metodo')
        return {
            'tipo': 'DECLARACION_METODO',
            'retorno': p.tipo_dato,
            'nombre': 'UNKNOWN',
            'parametros': p.lista_parametros,
            'declaraciones_locales': p.bloque_declarativo,
            'cuerpo_ejecutable': p.bloque_obligatorio
        }

    @_('error "(" lista_parametros ")" bloque_declarativo bloque_obligatorio ";"')
    def declaracion_metodo(self, p):
        print('ERROR: falta el nombre del metodo')
        return {
            'tipo': 'DECLARACION_METODO',
            'retorno': 'VOID',
            'nombre': 'UNKNOWN',
            'parametros': p.lista_parametros,
            'declaraciones_locales': p.bloque_declarativo,
            'cuerpo_ejecutable': p.bloque_obligatorio
        }

    @_('ID error lista_ids')
    def lista_ids(self, p):
        print('ERROR: falta "," al declarar las variables')
        return [p.ID] + p.lista_ids

    # esto no funciona, ya que el tipo de dato puede ser un id (como el nombre de una clase)
    # por lo que no detecta si el tipo de dato esta ausente
    @_('error ID')
    def parametro(self, p):
        print('ERROR: Definicion erronea del parametro')
        return {
            'tipo_dato': 'UNKNOWN',
            'id': p.ID
        }

    @_('tipo_dato error')
    def parametro(self, p):
        print('ERROR: Definicion erronea del parametro')
        return {
            'tipo_dato': p.tipo_dato,
            'id': 'UNKNOWN'
        }

    @_('expresion PLUS error')
    def expresion(self, p):
        print(f'ERROR: falta el operando después de + en la línea {p.lineno}')
        # [PASO 1] CAMBIO: antes devolvía un dict; ahora ERR (un Operando de error) para
        # que las reglas que lo consuman no fallen ni generen errores en cascada.
        return ERR

    @_('expresion MINUS error')
    def expresion(self, p):
        print(f'ERROR: falta el operando después de - en la línea {p.lineno}')
        # [PASO 1] CAMBIO: igual que arriba.
        return ERR

    @_('POUT "(" error ")"')
    def salida(self, p):
        print('ERROR: falta argumento de salida')
        # [PASO 1] CAMBIO: antes devolvía un dict; no se genera terceto, se devuelve None.
        return None

    # [PASO 2 - REVISIÓN] Errores de IF reescritos sobre 'inicio_if' / 'rama_else'.
    # (Los de paréntesis y los de WHILE están dentro de inicio_if / cabecera_while.)
    # Todas cierran con gen.if_fin() para no dejar saltos sin completar.

    @_('inicio_if error rama_else bloque_o_sentencia END_IF')
    def sentencia_if(self, p):
        print('ERROR: falta cuerpo en la sentencia if (rama then)')
        self.gen.if_fin()
        return None

    @_('inicio_if bloque_o_sentencia rama_else error END_IF')
    def sentencia_if(self, p):
        print('ERROR: falta cuerpo en la sentencia if (rama else)')
        self.gen.if_fin()
        return None

    @_('inicio_if error END_IF')
    def sentencia_if(self, p):
        print('ERROR: falta cuerpo en la sentencia if')
        self.gen.if_fin()
        return None

    @_('inicio_if bloque_o_sentencia rama_else bloque_o_sentencia error')
    def sentencia_if(self, p):
        print('ERROR: falta "end_if" en la sentencia if')
        self.gen.if_fin()
        return None

    @_('inicio_if bloque_o_sentencia error')
    def sentencia_if(self, p):
        print('ERROR: falta "end_if" en la sentencia if')
        self.gen.if_fin()
        return None

    def error(self, token):
        if token:
            print(f"Línea {token.lineno}: Error: Símbolo inesperado '{token.value}'.")
        else:
            print("Error: Se alcanzó el fin de archivo (EOF) inesperadamente.")


if __name__ == '__main__':
    # [PASO 3] CAMBIO: los programas de prueba se ejecutan con una función auxiliar, cada uno
    # con su propia TS / errores / generador (antes eran bloques repetidos).
    # Los tests solo usan construcciones ya migradas, así que se apaga el pseudo-árbol.
    MOSTRAR_AST = False

    def compilar(titulo, codigo):
        ts = TablaSimbolosSemantica()
        errores = Errores()
        gen = GeneradorCodigo(ts, errores, GestorAmbitos(ts, errores))
        print("\n" + "#" * 8 + f" {titulo} " + "#" * 8)
        AnalizadorSintactico(ts, gen).parse(AnalizadorLexico(ts).tokenize(codigo))
        gen.imprimir()
        print('Saltos sin completar (debe ser []):', gen.control_pendiente())
        errores.imprimir()
        return ts

    # ---------------- PASO 1 y 2: expresiones, asignaciones, IF, WHILE ----------------
    ts = compilar("PASO 1 y 2: expresiones, IF, WHILE", '''
    prueba_paso1
    UINTEGER a, b, c;
    DOUBLEF x, y;
    BEGIN
        a := 5$ui;
        b := a + 2$ui * a;
        c := b = 3$ui;
        x := 1.5 * 2.0;
        y := -x;
        a := toui(x) + b;
        pout(a);
        pout({fin del programa});

        {{ [PASO 2] WHILE con cuerpo en bloque }}
        while (a < 10$ui) repeat
        begin
            a := a + 1$ui;
        end;

        {{ [PASO 2] IF con ELSE (then de una sentencia, else en bloque) }}
        if (a == 5$ui)
            pout(a);
        else
            begin
                b := a;
                c := b;
            end
        end_if;

        {{ [PASO 2] IF sin ELSE, con condicion flotante }}
        if (x > 1.0)
            y := x;
        end_if;

        {{ ---- errores esperados ---- }}
        if (a < y)
            pout(a);
        end_if;
        a := x;
        b := a + y;
        a := -b;
        z := 1$ui;
    END
    ''')

    # ---------------- PASO 2 (revisión): errores SINTÁCTICOS en IF/WHILE ----------------
    compilar("PASO 2: errores sintácticos en IF/WHILE", '''
    prueba_errores
    UINTEGER a, b;
    BEGIN
        if a < 5$ui)            {{ falta "(" }}
            a := 1$ui;
        end_if;
        if (a < 5$ui            {{ falta ")" }}
            a := 2$ui;
        end_if;
        while (a < 5$ui) 
            a := a + 1$ui;      {{ falta repeat }}
        pout(a);
    END
    ''')

    # ---------------- PASO 3: funciones, invocaciones, ret, AUTO ----------------
    ts3 = compilar("PASO 3: funciones, invocaciones, ret, AUTO", '''
    prueba_paso3
    UINTEGER a, b;
    DOUBLEF x;

    UINTEGER FUNCTION suma(UINTEGER p, UINTEGER q)
        UINTEGER r;
    BEGIN
        r := p + q;
        ret(r);
    END;

    DOUBLEF FUNCTION mitad(DOUBLEF v)
    BEGIN
        ret(v / 2.0);
    END;

    FUNCTION informar(UINTEGER n)
    BEGIN
        pout({valor:});
        pout(n);
    END;

    {{ AUTO: retornos de tipos distintos -> el tipo es el mas abarcativo (DOUBLEF) }}
    AUTO FUNCTION elegir(UINTEGER n)
    BEGIN
        if (n > 0$ui)
            ret(1.5);
        end_if;
        ret(n);
    END;

    {{ funcion anidada: interna solo es visible dentro de externa }}
    UINTEGER FUNCTION externa(UINTEGER y)
        UINTEGER FUNCTION interna(UINTEGER y)
        BEGIN
            ret(y + 1$ui);
        END;
    BEGIN
        ret(interna(y));
    END;

    BEGIN
        a := suma(1$ui, 2$ui);
        informar(a);
        x := mitad(5.0);
        x := elegir(a);
        b := externa(a) + suma(a, 1$ui);
        b := toui(mitad(4.0));

        {{ ---- errores esperados ---- }}
        a := suma(1$ui);
        a := suma(1.5, 2$ui);
        a := informar(1$ui);
        a := interna(1$ui);
        a := a(1$ui);
        a := suma;
        ret(1$ui);
    END
    ''')

    # ---------------- PASO 3: errores en la DECLARACIÓN de funciones ----------------
    compilar("PASO 3: errores en declaraciones de funciones", '''
    prueba_errores_funciones
    UINTEGER a;

    UINTEGER FUNCTION sinparam()
    BEGIN
        ret(1$ui);
    END;

    UINTEGER FUNCTION devuelve_mal(UINTEGER p)
    BEGIN
        ret(1.5);
    END;

    FUNCTION con_ret(UINTEGER p)
    BEGIN
        ret(p);
    END;

    AUTO FUNCTION sin_retorno(UINTEGER p)
    BEGIN
        pout(p);
    END;

    UINTEGER FUNCTION f(UINTEGER p)
    BEGIN
        ret(p);
    END;

    UINTEGER FUNCTION f(UINTEGER p)
    BEGIN
        ret(p);
    END;

    BEGIN
        a := f(1$ui);
        a := sin_retorno(1$ui);
    END
    ''')

    # TABLA DE SÍMBOLOS del programa de funciones
    ts3.imprimir_tabla()