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
from CodigoIntermedio import (GeneradorCodigo, GestorAmbitos, Errores,
                               TablaSimbolosSemantica, ERR)

MOSTRAR_AST = True


class AnalizadorSintactico(Parser):
    tokens = AnalizadorLexico.tokens
    start = 'programa'

    def __init__(self, tabla_simbolos, generador):
        self.tabla = tabla_simbolos
        self.gen = generador

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

    # ------------------------------------------------------------------
    # SECCIÓN DE CLASES, HERENCIA Y MIEMBROS (PASO 5)
    # ------------------------------------------------------------------

    @_('CLASS ID')
    def inicio_clase(self, p):
        self.gen.iniciar_clase(p.ID, self._linea(p))
        return p.ID

    @_('CLASS ID EXTENDS ID')
    def inicio_clase(self, p):
        self.gen.iniciar_clase(p.ID0, self._linea(p), clase_padre=p.ID1)
        return p.ID0

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
        'declaracion_friend'
    )
    def miembro_clase(self, p):
        return p[0]

    @_('PRIVATE tipo_dato ID ";"')
    def atributo_privado(self, p):
        return self.gen.declarar_atributo(p.tipo_dato, p.ID, visibilidad='private', linea=self._linea(p))

    @_('tipo_dato ID ";"')
    def atributo_publico(self, p):
        return self.gen.declarar_atributo(p.tipo_dato, p.ID, visibilidad='public', linea=self._linea(p))

    @_('PRIVATE tipo_dato FUNCTION ID "(" lista_parametros ")" bloque_declarativo bloque_obligatorio ";"')
    def metodo_privado(self, p):
        return self.gen.declarar_metodo(p.tipo_dato, p.ID, p.lista_parametros, p.bloque_declarativo, p.bloque_obligatorio, visibilidad='private', linea=self._linea(p))

    @_('tipo_dato FUNCTION ID "(" lista_parametros ")" bloque_declarativo bloque_obligatorio ";"')
    def metodo_publico(self, p):
        return self.gen.declarar_metodo(p.tipo_dato, p.ID, p.lista_parametros, p.bloque_declarativo, p.bloque_obligatorio, visibilidad='public', linea=self._linea(p))

    @_('FRIEND ID ";"')
    def declaracion_friend(self, p):
        self.gen.registrar_amigo(p.ID, self._linea(p))
        return None

    # ------------------------------------------------------------------
    # RESTO DE REGLAS (IDs, Parámetros, Sentencias, Expresiones y Errores)
    # ------------------------------------------------------------------

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
        return {
            'tipo': 'RETORNO',
            'expresion': p.expresion
        }

    @_('POUT "(" TEXT_STRING ")"')
    def salida(self, p):
        self.gen.salida_cadena(p.TEXT_STRING)
        return None

    @_('POUT "(" expresion ")"')
    def salida(self, p):
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

    @_('ref_variable ASSIGN expresion')
    def expresion(self, p):
        return self.gen.asignacion(p.ref_variable, p.expresion, self._linea(p))

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
        return ERR

    @_('invocacion_metodo_objeto')
    def factor(self, p):
        return ERR

    @_('ref_variable')
    def factor(self, p):
        return p.ref_variable

    @_('DOUBLEF')
    def factor(self, p):
        return self.gen.constante_float(p.DOUBLEF)

    @_('CONST_UI')
    def factor(self, p):
        return self.gen.constante_ui(p.CONST_UI)

    @_('TOUI "(" expresion ")"')
    def factor(self, p):
        return self.gen.convertir_toui(p.expresion, self._linea(p))

    def error(self, token):
        if token:
            print(f"Línea {token.lineno}: Error: Símbolo inesperado '{token.value}'.")
        else:
            print("Error: Se alcanzó el fin de archivo (EOF) inesperadamente.")

if __name__ == '__main__':
    # [PASO 1] Infraestructura base del compilador

    ts = TablaSimbolosSemantica()
    errores = Errores()
    ambitos = GestorAmbitos(ts, errores)
    gen = GeneradorCodigo(ts, errores, ambitos)

    lexer = AnalizadorLexico(ts)
    parser = AnalizadorSintactico(ts, gen)

    # [PASO 1 & 2] Programa de prueba estándar (Variables, Expresiones, WHILE, IF)
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

        while (a < 10$ui) repeat
        begin
            a := a + 1$ui;
        end;

        if (a == 5$ui)
            pout(a);
        else
            begin
                b := a;
                c := b;
            end
        end_if;

        if (x > 1.0)
            y := x;
        end_if;

        if (a < y)
            pout(a);
        end_if;
        a := x;
        b := a + y;
        a := -b;
        z := 1$ui;
    END
    '''
    #parser.parse(lexer.tokenize(codigo_prueba_paso1))


    # Salidas generales del primer programa analizado
    #gen.imprimir()
    #print('Saltos sin completar (debe ser []):', gen.control_pendiente())
    #errores.imprimir()
    #ts.imprimir_tabla()

   
# [PASO 5 - BATERÍA AVANZADA] Pruebas de Herencia, Privacidad, Friend y Ambigüedad
    ts_avanzada = TablaSimbolosSemantica()
    er_avanzada = Errores()
    amb_avanzada = GestorAmbitos(ts_avanzada, er_avanzada)
    gen_avanzada = GeneradorCodigo(ts_avanzada, er_avanzada, amb_avanzada)

    codigo_pruebas_avanzadas = '''
    prueba_avanzada_oop
    
    CLASS vehiculo BEGIN
        UINTEGER velocidad;
        PRIVATE UINTEGER codigo_interno;
        FRIEND taller;
    END;

    CLASS coche extends vehiculo BEGIN
        UINTEGER cantidad_puertas;
    END;

    CLASS taller BEGIN
    END;

    CLASS base_a BEGIN
        UINTEGER id_colision;
    END;

    CLASS base_b extends base_a BEGIN
        UINTEGER id_colision;
    END;

    CLASS hija_colision extends base_b BEGIN
    END;

    BEGIN
        pout({ejecutando pruebas avanzadas});
    END
    '''

    print("\n######## PRUEBA AVANZADA: OOP, PRIVACIDAD Y AMBIGÜEDAD ########")
    AnalizadorSintactico(ts_avanzada, gen_avanzada).parse(
        AnalizadorLexico(ts_avanzada).tokenize(codigo_pruebas_avanzadas)
    )

    # --- PRUEBA MANUAL DE AMBIGÜEDAD (OPCIÓN 3) ---
    # Simulamos entrar al ámbito de 'hija_colision' y buscar el miembro colisionado 'id_colision'
    print("\n--- Verificando Detección de Ambigüedad en 'hija_colision' ---")
    amb_avanzada.iniciar_ambito('hija_colision', linea=50)
    resultado = amb_avanzada.validar_y_obtener_miembro('hija_colision', 'id_colision', linea=51)
    amb_avanzada.cerrar_ambito()
    
    if resultado is None:
        print("[ÉXITO] El sistema detectó correctamente la ambigüedad o bloqueo del miembro.")

    ts_avanzada.imprimir_tabla()
    er_avanzada.imprimir()
    print("######## FIN PRUEBA AVANZADA ########\n")