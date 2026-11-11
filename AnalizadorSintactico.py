import json
from sly import Parser
from AnalizadorLexico import AnalizadorLexico
from TablaSimbolos import TablaSimbolos


class AnalizadorSintactico(Parser):
    tokens = AnalizadorLexico.tokens
    start = 'programa'

    def __init__(self, tabla_simbolos):
        self.tabla = tabla_simbolos

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
        print(json.dumps(ast, indent=2, ensure_ascii=False))
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
        return {
            'tipo': 'DECLARACION_VARIABLES',
            'tipo_dato': p.var_decl_base['tipo_dato'],
            'variables': p.var_decl_base['variables'],
        }

    @_('COMPTIME var_decl_base ";"')
    def declaracion_comptime(self, p):
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

    @_('IF "(" condicion ")" bloque_o_sentencia ELSE bloque_o_sentencia END_IF')
    def sentencia_if(self, p):
        return {
            'tipo': 'IF_ELSE',
            'condicion': p.condicion,
            'bloque_then': p.bloque_o_sentencia0,
            'bloque_else': p.bloque_o_sentencia1,
        }

    @_('IF "(" condicion ")" bloque_o_sentencia END_IF')
    def sentencia_if(self, p):
        return {
            'tipo': 'IF',
            'condicion': p.condicion,
            'bloque_then': p.bloque_o_sentencia,
        }

    @_('WHILE "(" condicion ")" REPEAT bloque_o_sentencia')
    def sentencia_while(self, p):
        return {
            'tipo': 'SENTENCIA_WHILE',
            'condicion': p.condicion,
            'cuerpo': p.bloque_o_sentencia,
        }

    @_('expresion comparador expresion')
    def condicion(self, p):
        return {
            'izquierda': p.expresion0,
            'operador': p.comparador,
            'derecha': p.expresion1,
        }

    @_(
        'LESS',
        'LESS_EQUAL',
        'GREATER',
        'GREATER_EQUAL',
        'EQUALS_EQUALS',
        'NOT_EQUALS',
    )
    def comparador(self, p):
        return p[0]

    @_('ref_variable TWO_POINTS_ASSING expresion')
    def asignacion(self, p):
        return {
            'tipo': 'ASIGNACION',
            'destino': p.ref_variable,
            'expresion': p.expresion
        }

    @_('ID DOT ID')
    def ref_variable(self, p):
        return {
            'tipo': 'ACCESO_ATRIBUTO',
            'objeto': p.ID0,
            'atributo': p.ID1
        }

    @_('ID')
    def ref_variable(self, p):
        return {
            'tipo': 'VARIABLE',
            'nombre': p.ID
        }

    @_('RET "(" expresion ")"')
    def sentencia_retorno(self, p):
        return {
            'tipo': 'RETORNO',
            'expresion': p.expresion
        }

    @_('POUT "(" TEXT_STRING ")"')
    def salida(self, p):
        return {
            'tipo': 'SALIDA_POUT',
            'subtipo': 'CADENA',
            'valor': p.TEXT_STRING
        }

    @_('POUT "(" expresion ")"')
    def salida(self, p):
        return {
            'tipo': 'SALIDA_POUT',
            'subtipo': 'EXPRESION',
            'valor': p.expresion
        }


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
        return {
            'op': '+',
            'izq': p.expresion,
            'der': p.termino
        }

    @_('expresion MINUS termino')
    def expresion(self, p):
        return {
            'op': '-',
            'izq': p.expresion,
            'der': p.termino
        }

    @_('MINUS expresion %prec UMINUS')
    def expresion(self, p):
        return {
            'op': 'NEGATIVO',
            'expresion': p.expresion
        }

    @_('termino')
    def expresion(self, p):
        return p.termino

    @_('ref_variable ASSIGN expresion')
    def expresion(self, p):
        return {
            'tipo': 'ASIGNACION_EMBEBIDA',
            'destino': p.ref_variable,
            'expresion': p.expresion
        }

    @_('DOUBLEF', 'UINTEGER', 'ID')
    def tipo_dato(self, p):
        return p[0]

    @_('termino TIMES factor')
    def termino(self, p):
        return {
            'op': '*',
            'izq': p.termino,
            'der': p.factor
        }

    @_('termino DIVIDE factor')
    def termino(self, p):
        return {
            'op': '/',
            'izq': p.termino,
            'der': p.factor
        }

    @_('factor')
    def termino(self, p):
        return p.factor

    @_('invocacion_funcion')
    def factor(self, p):
        return p.invocacion_funcion

    @_('invocacion_metodo_objeto')
    def factor(self, p):
        return p.invocacion_metodo_objeto

    @_('ref_variable')
    def factor(self, p):
        return p.ref_variable

    @_('DOUBLEF', 'CONST_UI')
    def factor(self, p):
        return p[0]

    @_('TOUI "(" expresion ")"')
    def factor(self, p):
        return {
            'tipo': 'CONVERSION_TOUI',
            'expresion': p.expresion
        }

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
        print(json.dumps(ast, indent=2, ensure_ascii=False))
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

    # El bloque_auto es para que tenga ret explícito
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
        return {
            'op': '+',
            'izq': p.expresion,
            'der': {
                'op': 'UNKNOWN'
            }
        }


    @_('expresion MINUS error')
    def expresion(self, p):
        print(f'ERROR: falta el operando después de - en la línea {p.lineno}')
        return {
            'op': '-',
            'izq': p.expresion,
            'der': {
                'op': 'UNKNOWN'
            }
        }

    @_('POUT "(" error ")"')
    def salida(self, p):
        print('ERROR: falta argumento de salida')
        return {
            'tipo': 'SALIDA_POUT',
            'subtipo': 'EXPRESION',
            'valor': 'UNKNOWN'
        } 

    @_('IF error condicion ")" bloque_o_sentencia ELSE bloque_o_sentencia END_IF')
    def sentencia_if(self, p):
        print('ERROR: falta "(" en la sentencia if')
        return {
            'tipo': 'IF_ELSE',
            'condicion': p.condicion,
            'bloque_then': p.bloque_o_sentencia0,
            'bloque_else': p.bloque_o_sentencia1,
        }

    @_('IF "(" condicion error bloque_o_sentencia ELSE bloque_o_sentencia END_IF')
    def sentencia_if(self, p):
        print('ERROR: falta ")" en la sentencia if')
        return {
            'tipo': 'IF_ELSE',
            'condicion': p.condicion,
            'bloque_then': p.bloque_o_sentencia0,
            'bloque_else': p.bloque_o_sentencia1,
        }

    @_('IF error condicion ")" bloque_o_sentencia END_IF')
    def sentencia_if(self, p):
        print('ERROR: falta "(" en la sentencia if')
        return {
            'tipo': 'IF',
            'condicion': p.condicion,
            'bloque_then': p.bloque_o_sentencia,
        }

    @_('IF "(" condicion error bloque_o_sentencia END_IF')
    def sentencia_if(self, p):
        print('ERROR: falta ")" en la sentencia if')
        return {
            'tipo': 'IF',
            'condicion': p.condicion,
            'bloque_then': p.bloque_o_sentencia,
        }

    @_('WHILE error condicion ")" REPEAT bloque_o_sentencia')
    def sentencia_while(self, p):
        print('ERROR: falta "(" en la sentencia while')
        return {
            'tipo': 'SENTENCIA_WHILE',
            'condicion': p.condicion,
            'cuerpo': p.bloque_o_sentencia,
        }

    @_('WHILE "(" condicion error REPEAT bloque_o_sentencia')
    def sentencia_while(self, p):
        print('ERROR: falta "(" en la sentencia while')
        return {
            'tipo': 'SENTENCIA_WHILE',
            'condicion': p.condicion,
            'cuerpo': p.bloque_o_sentencia,
        }

    @_('IF "(" condicion ")" error ELSE bloque_o_sentencia END_IF')
    def sentencia_if(self, p):
        print('ERROR: falta cuerpo en la sentencia if')
        return {
            'tipo': 'IF_ELSE',
            'condicion': p.condicion,
            'bloque_then': 'UNKNOWN',
            'bloque_else': p.bloque_o_sentencia,
        }

    @_('IF "(" condicion ")" bloque_o_sentencia ELSE error END_IF')
    def sentencia_if(self, p):
        print('ERROR: falta cuerpo en la sentencia if')
        return {
            'tipo': 'IF_ELSE',
            'condicion': p.condicion,
            'bloque_then': p.bloque_o_sentencia,
            'bloque_else': "UNKNOWN",
        }

    @_('IF "(" condicion ")" error END_IF')
    def sentencia_if(self, p):
        print('ERROR: falta cuerpo en la sentencia if')
        return {
            'tipo': 'IF',
            'condicion': p.condicion,
            'bloque_then': "UNKNOWN",
        }

    @_('WHILE "(" condicion ")" REPEAT error')
    def sentencia_while(self, p):
        print('ERROR: falta cuerpo en la sentencia while')
        return {
            'tipo': 'SENTENCIA_WHILE',
            'condicion': p.condicion,
            'cuerpo': "UNKNOWN",
        }

    @_('IF "(" condicion ")" bloque_o_sentencia ELSE bloque_o_sentencia error')
    def sentencia_if(self, p):
        print('ERROR: falta "end_if" en la sentencia if')
        return {
            'tipo': 'IF_ELSE',
            'condicion': p.condicion,
            'bloque_then': p.bloque_o_sentencia0,
            'bloque_else': p.bloque_o_sentencia1,
        }

    @_('IF "(" condicion ")" bloque_o_sentencia error')
    def sentencia_if(self, p):
        print('ERROR: falta "end_if" en la sentencia if')
        return {
            'tipo': 'IF',
            'condicion': p.condicion,
            'bloque_then': p.bloque_o_sentencia,
        }

    @_('WHILE "(" condicion ")" error bloque_o_sentencia')
    def sentencia_while(self, p):
        print('ERROR: falta "repeat" en la sentencia while')
        return {
            'tipo': 'SENTENCIA_WHILE',
            'condicion': p.condicion,
            'cuerpo': p.bloque_o_sentencia,
        }

    def error(self, token):
        if token:
            print(f"Línea {token.lineno}: Error: Símbolo inesperado '{token.value}'.")
        else:
            print("Error: Se alcanzó el fin de archivo (EOF) inesperadamente.")

if __name__ == '__main__':
    ts = TablaSimbolos()
    lexer = AnalizadorLexico(ts)
    parser = AnalizadorSintactico(ts)


    codigo_prueba_funcional = '''
    mi_programa

    {{ Declaraciones globales }}
    UINTEGER aux, c;
    comptime DOUBLEF val_constante;

    {{ Declaracion de Clases }}
    CLASS punto2d
    BEGIN
        PRIVATE DOUBLEF x, y;
        Friend f1;

        DOUBLEF escalar(DOUBLEF factor)
            DOUBLEF temp;
        BEGIN
            temp := factor * 1.2d+10;
            ret (temp);
        END;
    END;

    CLASS ca
    BEGIN
        PRIVATE DOUBLEF a; 
        PRIVATE DOUBLEF m(DOUBLEF pa)
        BEGIN 
            pout({Invocando metodo m});
            ret(a +pa);
        END;
        Friend cb; 
    END;

    {{ Variables de clase }}
    punto2d p1, p2;
    ca a1;

    {{ Funciones }}
    auto function f() 
    begin 
        aux := 10$ui;
        ret (aux + 5.0);
    end;

    DOUBLEF function f1 (DOUBLEF x, doublef y)
        DOUBLEF w ;
        {{ Funcion anidada }}
        DOUBLEF function f11 (DOUBLEF x1, DOUBLEF x2)
        begin
            x2 := x1;
            ret (2$ui);
        end;
    begin
        w := f11(x, 0$ui);
        if (w > 1$ui)
           ret (w * 2$ui);
        else
            begin
                w := 2$ui;
                ret (w * 2$ui);
            end
        end_if;
        ret (1$ui);
    end;

    {{ Bloque principal }}
    BEGIN
        {{ Asignaciones y expresiones complejas }}
        val_constante := .6;
        aux := 1.0 + 3.0d-5 - .2d34 * 2.5d-1 / 15.2 + 0.0;

        p1.x := 3.5;
        p2.x := p1.x;
        aux := p1.escalar(2.0);

        {{ Ciclos e iteraciones }}
        aux := 10$ui;
        while (aux < 20$ui) repeat 
        begin
            aux := aux - 1$ui; 
        end;

        {{ Condicionales, llamadas a funcion y conversiones }}
        c := f(val_constante = 3.0);
        aux := toui(2.5 * aux);

        {{ Pruebas de salida }}
        pout ({Prueba combinada finalizada con éxito});
        pout (aux);
    END
    '''
    tokens = lexer.tokenize(codigo_prueba_funcional)
    parser.parse(tokens)
    ts.imprimir_tabla()
    