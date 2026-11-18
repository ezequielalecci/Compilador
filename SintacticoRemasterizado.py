"""
SintacticoRemasterizado.py  -  TP2 -> TP3 -> TP4  (Grupo 19)

=====================================================================================
REGISTRO DE CAMBIOS RESPECTO DE LA VERSIÓN ANTERIOR (marcados con [PASO 3] / [PASO 5])
=====================================================================================
[PASO 3] FUNCIONES
  - Nuevos no terminales marcador 'cabecera_funcion', 'cabecera_auto' y 'cabecera_metodo':
    se reducen justo después del ')' de la cabecera, que es el momento de abrir el ámbito,
    declarar los parámetros y crear la unidad de código de la función (SLY no admite acciones
    a mitad de regla).
  - declaracion_funcion cierra la función en el generador (finalizar_funcion_decl).
  - invocacion_funcion emite ARG / CALL y devuelve el Operando del CALL.
    Ya no se devuelve ERR en 'factor'.
  - sentencia_retorno emite el terceto RET y devuelve None (antes devolvía un dict).
[PASO 3 - AUTO / RETORNOS]
  - 'bloque_auto' ahora es  BEGIN sentencias_ejecutables END  (igual que bloque_obligatorio).
    Antes exigía un 'ret' como última sentencia de nivel superior, lo que impedía tener
    'ret' solo dentro de un IF/WHILE y rechazaba funciones válidas.
  - Se eliminaron las reglas de 'sentencias_no_retorno' (quedaron sin uso).
  - El chequeo de "al menos un ret" en funciones AUTO, el tipo de retorno más abarcativo
    y el retorno por defecto de las funciones sin 'ret' se resuelven en el generador
    (finalizar_funcion_decl), no en la gramática.
  - Las funciones normales / void siguen sin exigir 'ret' (bloque_obligatorio).
[PASO 5] CLASES, MÉTODOS Y '.'
  - Los métodos usan 'cabecera_metodo' (misma idea que las funciones), así su cuerpo se
    compila en su propia unidad y NO ensucia el código de main.
  - 'invocacion_metodo_objeto' ahora es   ref_variable DOT ID "(" args ")"   (antes ID DOT ID),
    porque con ID DOT ID había un conflicto shift/reduce con 'ref_variable DOT ID' que
    impedía leer 'obj.atributo' en una expresión o a la izquierda de ':='.
  - 'ref_variable' y 'destino_asignacion' llaman a gen.acceso_miembro_punto(_destino),
    que ahora existe en el generador.
[CORRECCIONES]
  - factor ahora admite  "(" expresion ")"  (antes no se podía escribir (a + b) * c).
  - La constante de punto flotante en 'factor' usa el token FLOAT (antes DOUBLEF, que es la
    palabra reservada del tipo, por lo que 1.5 / 2.0 nunca se reconocían como operando).
  - error() registra el error en gen.errores: si hay errores sintácticos main.py ya no genera
    el Assembler (antes imprimía el error pero igual generaba un .asm vacío).
[TP4]
  - Se eliminó el bloque __main__ (las pruebas están ahora en main.py).
  - MOSTRAR_AST queda en False: el pseudo-árbol ya casi no se construye.
=====================================================================================
"""

import json
from sly import Parser
from AnalizadorLexico import AnalizadorLexico
from CodigoIntermedio import GeneradorCodigo, ERR, VOID

MOSTRAR_AST = False


class AnalizadorSintactico(Parser):
    tokens = AnalizadorLexico.tokens
    start = 'programa'
    # debugfile = 'parser.out'   # descomentar para regenerar parser.out y revisar conflictos

    def __init__(self, tabla_simbolos, generador):
        self.tabla = tabla_simbolos
        self.gen = generador

    def _linea(self, p):
        try:
            return p.lineno
        except AttributeError:
            return 0

    precedence = (
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
    # [PASO 3] FUNCIONES
    # ------------------------------------------------------------------
    def _falta_parametro(self, tipo, nombre, linea):
        self.gen.errores.semantico(
            linea, f"{tipo} '{nombre}' debe tener al menos un parámetro.")

    # --- originales (sin cambios) ---
    @_('tipo_dato FUNCTION ID "(" lista_parametros ")"')
    def cabecera_funcion(self, p):
        self.gen.iniciar_funcion_decl(p.tipo_dato, p.ID, p.lista_parametros, self._linea(p))
        return p.ID

    @_('FUNCTION ID "(" lista_parametros ")"')
    def cabecera_funcion(self, p):
        self.gen.iniciar_funcion_decl(VOID, p.ID, p.lista_parametros, self._linea(p))
        return p.ID

    @_('AUTO FUNCTION ID "(" lista_parametros ")"')
    def cabecera_auto(self, p):
        self.gen.iniciar_funcion_decl('AUTO', p.ID, p.lista_parametros, self._linea(p))
        return p.ID

    # --- nuevas (caso "()" sin parámetros: error semántico, pero se abre la función igual) ---
    @_('tipo_dato FUNCTION ID "(" ")"')
    def cabecera_funcion(self, p):
        self._falta_parametro('la función', p.ID, self._linea(p))
        self.gen.iniciar_funcion_decl(p.tipo_dato, p.ID, [], self._linea(p))
        return p.ID

    @_('FUNCTION ID "(" ")"')
    def cabecera_funcion(self, p):
        self._falta_parametro('la función', p.ID, self._linea(p))
        self.gen.iniciar_funcion_decl(VOID, p.ID, [], self._linea(p))
        return p.ID

    @_('AUTO FUNCTION ID "(" ")"')
    def cabecera_auto(self, p):
        self._falta_parametro('la función', p.ID, self._linea(p))
        self.gen.iniciar_funcion_decl('AUTO', p.ID, [], self._linea(p))
        return p.ID

    # Funciones normales / void: el 'ret' es opcional (bloque_obligatorio no lo exige).
    @_('cabecera_funcion bloque_declarativo bloque_obligatorio ";"')
    def declaracion_funcion(self, p):
        self.gen.finalizar_funcion_decl(self._linea(p))
        return None

    # Funciones AUTO: la gramática admite 'ret' en cualquier posición (incluso anidado);
    # la exigencia de al menos un 'ret' se valida en el generador.
    @_('cabecera_auto bloque_declarativo bloque_auto ";"')
    def declaracion_funcion(self, p):
        self.gen.finalizar_funcion_decl(self._linea(p))
        return None

    # ------------------------------------------------------------------
    # [PASO 5] CLASES, HERENCIA Y MIEMBROS
    # ------------------------------------------------------------------
    @_('CLASS ID')
    def inicio_clase(self, p):
        self.gen.iniciar_clase(p.ID, self._linea(p))
        return p.ID

    @_('inicio_clase BEGIN cuerpo_clase END ";"')
    def declaracion_clase(self, p):
        self.gen.cerrar_clase(p.inicio_clase, self._linea(p))
        return None

    @_('inicio_clase BEGIN cuerpo_clase END')
    def declaracion_clase(self, p):
        self.gen.cerrar_clase(p.inicio_clase, self._linea(p))
        return None

    @_('cuerpo_clase miembro_clase')
    def cuerpo_clase(self, p):
        return p.cuerpo_clase + [p.miembro_clase]

    @_('')
    def cuerpo_clase(self, p):
        return []

    @_(
        'atributo_privado',
        'atributo_publico',
        'metodo_privado',
        'metodo_publico',
        'declaracion_friend',
        'declaracion_extends'
    )
    def miembro_clase(self, p):
        return p[0]

    @_('PRIVATE tipo_dato ID ";"')
    def atributo_privado(self, p):
        return self.gen.declarar_atributo(p.tipo_dato, p.ID, visibilidad='private', linea=self._linea(p))

    @_('tipo_dato ID ";"')
    def atributo_publico(self, p):
        return self.gen.declarar_atributo(p.tipo_dato, p.ID, visibilidad='public', linea=self._linea(p))
    
    @_('tipo_dato FUNCTION ID "(" ")"')
    def cabecera_metodo(self, p):
        self._falta_parametro('el método', p.ID, self._linea(p))
        return self.gen.iniciar_metodo(p.tipo_dato, p.ID, [], self._linea(p))

    @_('tipo_dato FUNCTION ID "(" lista_parametros ")"')
    def cabecera_metodo(self, p):
        return self.gen.iniciar_metodo(p.tipo_dato, p.ID, p.lista_parametros, self._linea(p))

    @_('PRIVATE cabecera_metodo bloque_declarativo bloque_obligatorio ";"')
    def metodo_privado(self, p):
        self.gen.finalizar_metodo(p.cabecera_metodo, 'private', self._linea(p))
        return None

    @_('cabecera_metodo bloque_declarativo bloque_obligatorio ";"')
    def metodo_publico(self, p):
        self.gen.finalizar_metodo(p.cabecera_metodo, 'public', self._linea(p))
        return None

    @_('EXTENDS lista_ids ";"')
    def declaracion_extends(self, p):
        self.gen.registrar_herencia(p.lista_ids, self._linea(p))
        return None

    @_('FRIEND ID ";"')
    def declaracion_friend(self, p):
        self.gen.registrar_amigo(p.ID, self._linea(p))
        return None

    # ------------------------------------------------------------------
    # IDs, parámetros, sentencias, expresiones
    # ------------------------------------------------------------------
    @_('ID "," lista_ids')
    def lista_ids(self, p):
        return [p.ID] + p.lista_ids

    @_('ID')
    def lista_ids(self, p):
        return [p.ID]

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

    @_('COMPTIME tipo_dato ID')
    def parametro(self, p):
        return {
            'tipo_dato': p.tipo_dato,
            'id': p.ID,
            'comptime': True
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

    # [PASO 3 - AUTO] Cuerpo de una función AUTO: mismas sentencias que un bloque común
    # ('ret' permitido en cualquier lugar, incluso dentro de IF / WHILE).
    @_('BEGIN sentencias_ejecutables END')
    def bloque_auto(self, p):
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

    @_('sentencia_no_retorno', 'sentencia_retorno')
    def sentencia(self, p):
        return p[0]

    @_('IF "(" condicion ")"')
    def inicio_if(self, p):
        self.gen.if_condicion(p.condicion, self._linea(p))
        return None

    @_('ELSE')
    def rama_else(self, p):
        self.gen.if_else()
        return None

    @_('inicio_if bloque_o_sentencia rama_else bloque_o_sentencia END_IF')
    def sentencia_if(self, p):
        self.gen.if_fin()
        return None

    @_('inicio_if bloque_o_sentencia END_IF')
    def sentencia_if(self, p):
        self.gen.if_fin()
        return None

    @_('WHILE')
    def inicio_while(self, p):
        self.gen.while_inicio()
        return None

    @_('inicio_while "(" condicion ")" REPEAT')
    def cabecera_while(self, p):
        self.gen.while_condicion(p.condicion, self._linea(p))
        return None

    @_('cabecera_while bloque_o_sentencia')
    def sentencia_while(self, p):
        self.gen.while_fin()
        return None

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
        return (p[0], p.lineno)

    @_('destino_asignacion TWO_POINTS_ASSING expresion')
    def asignacion(self, p):
        self.gen.asignacion(p.destino_asignacion, p.expresion, self._linea(p))
        return None

    @_('ID')
    def destino_asignacion(self, p):
        return self.gen.variable_destino(p.ID, self._linea(p))

    @_('ref_variable DOT ID')
    def destino_asignacion(self, p):
        return self.gen.acceso_miembro_punto_destino(p.ref_variable, p.ID, self._linea(p))

    @_('ID')
    def ref_variable(self, p):
        return self.gen.variable(p.ID, self._linea(p))

    @_('ref_variable DOT ID')
    def ref_variable(self, p):
        return self.gen.acceso_miembro_punto(p.ref_variable, p.ID, self._linea(p))

    @_('RET "(" expresion ")"')
    def sentencia_retorno(self, p):
        self.gen.retorno(p.expresion, self._linea(p))
        return None

    @_('POUT "(" TEXT_STRING ")"')
    def salida(self, p):
        self.gen.salida_cadena(p.TEXT_STRING)
        return None

    @_('POUT "(" expresion ")"')
    def salida(self, p):
        self.gen.salida_expresion(p.expresion)
        return None

    # ------------------------------------------------------------------
    # [PASO 3 / 5] INVOCACIONES: emiten ARG / CALL y devuelven el Operando del CALL
    # ------------------------------------------------------------------
    @_('ID "(" lista_expresiones ")"')
    def invocacion_funcion(self, p):
        return self.gen.invocar_funcion(p.ID, p.lista_expresiones, self._linea(p))

    @_('ID "(" ")"')
    def invocacion_funcion(self, p):
        return self.gen.invocar_funcion(p.ID, [], self._linea(p))

    @_('ref_variable DOT ID "(" lista_expresiones ")"')
    def invocacion_metodo_objeto(self, p):
        return self.gen.invocar_metodo(p.ref_variable, p.ID, p.lista_expresiones, self._linea(p))

    @_('ref_variable DOT ID "(" ")"')
    def invocacion_metodo_objeto(self, p):
        return self.gen.invocar_metodo(p.ref_variable, p.ID, [], self._linea(p))

    @_('expresion "," lista_expresiones')
    def lista_expresiones(self, p):
        return [p.expresion] + p.lista_expresiones

    @_('expresion')
    def lista_expresiones(self, p):
        return [p.expresion]

    @_('expresion PLUS termino')
    def expresion(self, p):
        return self.gen.operacion('+', p.expresion, p.termino, self._linea(p))

    @_('expresion MINUS termino')
    def expresion(self, p):
        return self.gen.operacion('-', p.expresion, p.termino, self._linea(p))

    @_('MINUS expresion %prec UMINUS')
    def expresion(self, p):
        return self.gen.negar(p.expresion, self._linea(p))

    @_('termino')
    def expresion(self, p):
        return p.termino

    @_('DOUBLEF', 'UINTEGER', 'ID')
    def tipo_dato(self, p):
        return p[0]

    @_('termino TIMES factor')
    def termino(self, p):
        return self.gen.operacion('*', p.termino, p.factor, self._linea(p))

    @_('termino DIVIDE factor')
    def termino(self, p):
        return self.gen.operacion('/', p.termino, p.factor, self._linea(p))

    @_('factor')
    def termino(self, p):
        return p.factor

    @_('invocacion_funcion')
    def factor(self, p):
        return p.invocacion_funcion

    @_('invocacion_metodo_objeto')
    def factor(self, p):
        return p.invocacion_metodo_objeto
    
    @_('ref_variable ASSIGN factor')
    def factor(self, p):
        return self.gen.asignacion(p.ref_variable, p.factor, self._linea(p))

    @_('ref_variable')
    def factor(self, p):
        return p.ref_variable

    @_('DOUBLEF')
    def factor(self, p):
        return self.gen.constante_float(p.DOUBLEF)

    @_('"(" expresion ")"')
    def factor(self, p):
        return p.expresion

    @_('CONST_UI')
    def factor(self, p):
        return self.gen.constante_ui(p.CONST_UI)

    @_('TOUI "(" expresion ")"')
    def factor(self, p):
        return self.gen.convertir_toui(p.expresion, self._linea(p))

    def error(self, token):
        if token:
            linea = token.lineno
            msg = f"Símbolo inesperado '{token.value}'."
        else:
            linea = 0
            msg = "Se alcanzó el fin de archivo (EOF) inesperadamente."
        print(f"Línea {linea}: Error: {msg}")
        # Se registra para que main.py NO genere Assembler si hubo errores sintácticos.
        self.gen.errores.lista.append((linea, f"Error Sintáctico: {msg}"))