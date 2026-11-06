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

PRÓXIMOS PASOS PREVISTOS
  [PASO 3] ámbitos de función, invocaciones, RET, AUTO  (+ correcciones: >=1 parámetro,
           falta de RET en AUTO)
  [PASO 4] COMPTIME
  [PASO 5] clases, private/friend, acceso con '.', herencia (+ corrección de 'extends')
=====================================================================================
"""

import json
from sly import Parser
from AnalizadorLexico import AnalizadorLexico
# [PASO 1] CAMBIO: se importa la infraestructura de tercetos desde el archivo aparte.
from CodigoIntermedio import (GeneradorCodigo, GestorAmbitos, Errores,
                               TablaSimbolosSemantica, ERR)

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

    @_('tipo_dato FUNCTION ID "(" lista_parametros ")" bloque_declarativo bloque_obligatorio ";"')
    def declaracion_funcion(self, p):
        return {
            'tipo': 'DECLARACION_FUNCION',
            'retorno': p.tipo_dato,
            'nombre': p.ID,
            'parametros': p.lista_parametros,
            'declaraciones_locales': p.bloque_declarativo,
            'cuerpo_ejecutable': p.bloque_obligatorio,
        }

    # El bloque_auto es para que tenga ret explícito
    @_('AUTO FUNCTION ID "(" lista_parametros ")" bloque_declarativo bloque_auto ";"')
    def declaracion_funcion(self, p):
        return {
            'tipo': 'DECLARACION_FUNCION',
            'retorno': 'AUTO',
            'nombre': p.ID,
            'parametros': p.lista_parametros,
            'declaraciones_locales': p.bloque_declarativo,
            'cuerpo_ejecutable': p.bloque_auto['cuerpo'],
            'expresion_retorno': p.bloque_auto['retorno']
        }

    @_('FUNCTION ID "(" lista_parametros ")" bloque_declarativo bloque_obligatorio ";"')
    def declaracion_funcion(self, p):
        return {
            'tipo': 'DECLARACION_FUNCION',
            'retorno': 'VOID',
            'nombre': p.ID,
            'parametros': p.lista_parametros,
            'declaraciones_locales': p.bloque_declarativo,
            'cuerpo_ejecutable': p.bloque_obligatorio,
        }

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

    @_('BEGIN sentencias_no_retorno sentencia_retorno ";" END')
    def bloque_auto(self, p):
        return {
            'cuerpo': p.sentencias_no_retorno + [p.sentencia_retorno],
            'retorno': p.sentencia_retorno['expresion']
        }

    @_('BEGIN sentencia_retorno ";" END')
    def bloque_auto(self, p):
        return {
            'cuerpo': [p.sentencia_retorno],
            'retorno': p.sentencia_retorno['expresion']
        }

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
        # [PASO 1] SIN CAMBIOS en la forma (se migra en el PASO 3); 'expresion' ya es un Operando.
        return {
            'tipo': 'RETORNO',
            'expresion': p.expresion
        }

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
        return {
            'tipo': 'INVOCACION_FUNCION',
            'nombre': p.ID,
            'argumentos': p.lista_expresiones,
        }

    @_('ID "(" ")"')
    def invocacion_funcion(self, p):
        return {
            'tipo': 'INVOCACION_FUNCION',
            'nombre': p.ID,
            'argumentos': []
        }

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
        # [PASO 1] TEMPORAL: se migra en el PASO 3. Se devuelve ERR (no el dict).
        return ERR

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

    @_('tipo_dato FUNCTION error "(" lista_parametros ")" bloque_declarativo bloque_obligatorio ";"')
    def declaracion_funcion(self, p):
        print('ERROR: falta el nombre de la funcion')
        return {
            'tipo': 'DECLARACION_FUNCION',
            'retorno': p.tipo_dato,
            'nombre': 'UNKNOWN',
            'parametros': p.lista_parametros,
            'declaraciones_locales': p.bloque_declarativo,
            'cuerpo_ejecutable': p.bloque_obligatorio,
        }

    @_('AUTO FUNCTION error "(" lista_parametros ")" bloque_declarativo bloque_auto ";"')
    def declaracion_funcion(self, p):
        print('ERROR: falta el nombre de la funcion')
        return {
            'tipo': 'DECLARACION_FUNCION',
            'retorno': 'AUTO',
            'nombre': 'UNKNOWN',
            'parametros': p.lista_parametros,
            'declaraciones_locales': p.bloque_declarativo,
            'cuerpo_ejecutable': p.bloque_auto['cuerpo'],
            'expresion_retorno': p.bloque_auto['retorno']
        }

    @_('FUNCTION error "(" lista_parametros ")" bloque_declarativo bloque_obligatorio ";"')
    def declaracion_funcion(self, p):
        print('ERROR: falta el nombre de la funcion')
        return {
            'tipo': 'DECLARACION_FUNCION',
            'retorno': 'VOID',
            'nombre': 'UNKNOWN',
            'parametros': p.lista_parametros,
            'declaraciones_locales': p.bloque_declarativo,
            'cuerpo_ejecutable': p.bloque_obligatorio,
        }

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
    # [PASO 1] CAMBIO: ahora hay que armar toda la infraestructura del TP3 y pasársela
    # al parser. Se usa TablaSimbolosSemantica (tu TablaSimbolos + tipo/uso/ámbito).
    ts = TablaSimbolosSemantica()
    errores = Errores()
    ambitos = GestorAmbitos(ts, errores)
    gen = GeneradorCodigo(ts, errores, ambitos)

    lexer = AnalizadorLexico(ts)
    parser = AnalizadorSintactico(ts, gen)

    # [PASO 1] CAMBIO: programa de prueba reducido a lo ya migrado (sin funciones,
    # clases, IF ni WHILE). Los comentarios indican lo esperado.
    codigo_prueba_paso1 = '''
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
    '''
    parser.parse(lexer.tokenize(codigo_prueba_paso1))

    # [PASO 2 - REVISIÓN] segundo programa: errores SINTÁCTICOS en IF/WHILE.
    # Lo importante: el parser debe seguir, y al final 'Saltos sin completar' debe ser [].
    ts2 = TablaSimbolosSemantica(); er2 = Errores()
    gen2 = GeneradorCodigo(ts2, er2, GestorAmbitos(ts2, er2))
    codigo_errores_paso2 = '''
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
    '''
    print("\n######## PRUEBA DE ERRORES SINTÁCTICOS (PASO 2) ########")
    AnalizadorSintactico(ts2, gen2).parse(AnalizadorLexico(ts2).tokenize(codigo_errores_paso2))
    gen2.imprimir()
    print('Saltos sin completar (debe ser []):', gen2.control_pendiente())
    print("######## FIN PRUEBA DE ERRORES ########\n")

    # [PASO 1] NUEVO: salidas pedidas por el TP3 (código intermedio, errores, TS).
    gen.imprimir()
    print('Saltos sin completar (debe ser []):', gen.control_pendiente())
    errores.imprimir()
    ts.imprimir_tabla()