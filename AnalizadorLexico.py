from sly import Lexer
from TablaSimbolos import TablaSimbolos

OPERANDOS = {'ID', 'CONST_UI', 'DOUBLEF', ')'}

MIN_POS = 2.2250738585072014e-308
MAX_POS = 1.7976931348623157e+308
MAX_UI = 65535


class AnalizadorLexico(Lexer):
    tokens = {IF, ELSE, END_IF, BEGIN, END, POUT, RET, CLASS, FUNCTION, DOUBLEF, UINTEGER,
              ID, CONST_UI, PLUS, MINUS, TIMES, DIVIDE, TWO_POINTS_ASSING, ASSIGN,
              LESS, LESS_EQUAL, GREATER, GREATER_EQUAL, EQUALS_EQUALS, NOT_EQUALS,
              TEXT_STRING, DOT, WHILE, REPEAT, AUTO, COMPTIME, FRIEND, PRIVATE, TOUI}

    literals = {'(', ')', ',', ';'}

    reserved_words = {
        'IF': 'IF', 'ELSE': 'ELSE', 'END_IF': 'END_IF', 'BEGIN': 'BEGIN',
        'END': 'END', 'POUT': 'POUT', 'RET': 'RET', 'CLASS': 'CLASS',
        'FUNCTION': 'FUNCTION', 'DOUBLEF': 'DOUBLEF', 'REPEAT': 'REPEAT',
        'WHILE': 'WHILE', 'AUTO': 'AUTO', 'COMPTIME': 'COMPTIME',
        'FRIEND': 'FRIEND', 'PRIVATE': 'PRIVATE', 'TOUI': 'TOUI',
        'UINTEGER': 'UINTEGER'
    }

    ignore = ' \t'

    def __init__(self, tabla_simbolos):
        self.tabla_simbolos = tabla_simbolos
        self.prev_type = None


    def tokenize(self, text, lineno=1, index=0):
        # Recordamos el tipo del token anterior para distinguir "a -1.5" (resta) de "-1.5" (constante)
        self.prev_type = None
        for tok in super().tokenize(text, lineno, index):
            self.prev_type = tok.type
            yield tok


    def _signo_como_operador(self, t):
        """Si el signo inicial es en realidad un operador binario, devuelve
        un token PLUS/MINUS y retrocede el índice para releer el número."""
        if t.value[0] in '+-' and self.prev_type in OPERANDOS:
            self.index = t.index + 1
            t.type = 'PLUS' if t.value[0] == '+' else 'MINUS'
            t.value = t.value[0]
            return t
        return None



    @_(r'\{\{[\s\S]*?\}\}')
    def ignore_comment(self, t):
        self.lineno += t.value.count('\n')


    @_(r'\{\{[\s\S]*')
    def ignore_comment_unclosed(self, t):
        print(f"Warning Léxico (Línea {t.lineno}): Comentario '{{{{' sin cerrar; se ignora hasta el fin del archivo.")
        self.lineno += t.value.count('\n')


    
    @_(r'\{[^}\n]*\}')
    def TEXT_STRING(self, t):
        lexema_orig = t.value
        t.value = t.value[1:-1]
        self.tabla_simbolos.insertar(lexema_orig, 'TEXT_STRING', valor=t.value)
        return t


    @_(r'\{[^}\n]*')
    def ignore_llave_sin_cierre(self, t):
        print(f"Error Léxico (Línea {t.lineno}): Cadena sin llave de cierre '}}'.")


    @_(r'\}')
    def ignore_llave_sin_apertura(self, t):
        print(f"Error Léxico (Línea {t.lineno}): Cadena sin llave de apertura '{{'.")


  
    @_(r'[+-]?\d+\$ui')
    def CONST_UI(self, t):
        separado = self._signo_como_operador(t)
        if separado:
            return separado

        lexema_orig = t.value
        if lexema_orig[0] == '-':
            print(f"Error Léxico (Línea {t.lineno}): La constante unsigned '{lexema_orig}' no puede llevar signo negativo.")

        digitos = lexema_orig.lstrip('+-')[:-3]
        valor = int(digitos)
        if valor > MAX_UI:
            print(f"Error Léxico (Línea {t.lineno}): La constante '{lexema_orig}' está fuera del rango [0, {MAX_UI}].")
            valor = MAX_UI          # valor de recuperación: el parser sigue

        t.value = valor
        self.tabla_simbolos.insertar(f"{valor}$ui", 'CONST_UI', valor=valor)
        return t
    


    @_(r'[+-]?(?:\d+\.\d+|\.\d+)(?:[dD][+-]?\d*)?|[+-]?\d+(?:[dD][+-]?\d*)?')
    def DOUBLEF(self, t):
        separado = self._signo_como_operador(t)
        if separado:
            return separado

        lexema_orig = t.value

        if lexema_orig.lower().endswith(('d', 'd+', 'd-')):
            print(f"Error Léxico (Línea {t.lineno}): Falta el valor del exponente después de la 'd' en '{lexema_orig}'.")
            return 
        
        if '.' not in lexema_orig:
            print(f"Error Léxico (Línea {t.lineno}): '{lexema_orig}' no es una constante válida "
                  f"(flotante sin parte decimal o entero sin sufijo $ui).")
            return 

        cadena_std = lexema_orig.lower().replace('d', 'e')
        valor = float(cadena_std)   # puede dar inf o 0.0 por over/underflow

    
        mantisa = cadena_std.split('e')[0] #nos quedamos con la parte no decimal
        es_cero = not any(c in '123456789' for c in mantisa) #pregunta si son todos 0 

        lexema_ts = lexema_orig
        if es_cero:
            valor = 0.0
        else:
            signo = -1.0 if valor < 0 or lexema_orig.startswith('-') else 1.0
            valor_abs = abs(valor)
            if not (MIN_POS < valor_abs < MAX_POS):
                print(f"Error Léxico (Línea {t.lineno}): El valor flotante '{lexema_orig}' está fuera del rango permitido de 64 bits.")
                valor = signo * (MAX_POS if valor_abs >= MAX_POS else MIN_POS)
                lexema_ts = repr(valor)

        t.value = valor
        self.tabla_simbolos.insertar(lexema_ts, 'FLOAT', valor=valor)
        t.value = lexema_ts
        return t

  
    @_(r'[a-zA-Z][a-zA-Z0-9_]*')
    def ID(self, t):
        t_mayus = t.value.upper()

        if t_mayus in self.reserved_words:
            t.type = self.reserved_words[t_mayus]
            t.value = t_mayus
            return t

        if not t.value.islower():
            print(f"Error Léxico (Línea {t.lineno}): Identificador '{t.value}' no permite mayúsculas.")
            t.value = t.value.lower()

        if len(t.value) > 22:
            original = t.value
            t.value = t.value[:22]
            print(f"Warning (Línea {t.lineno}): ID '{original}' supera 22 caracteres. Truncado a '{t.value}'.")

        t.type = 'ID'
        self.tabla_simbolos.insertar(t.value, 'ID')
        return t


    @_(r'\.')
    def DOT(self, t):
        return t

    @_(r'\n+')
    def ignore_newline(self, t):
        self.lineno += t.value.count('\n')

    def error(self, t):
        print(f"Error Léxico (Línea {self.lineno}): Carácter ilegal '{t.value[0]}'")
        self.index += 1

    # OPERADORES 
    NOT_EQUALS = r'\!='
    GREATER_EQUAL = r'\>='
    LESS_EQUAL = r'\<='
    TWO_POINTS_ASSING = r'\:='
    EQUALS_EQUALS = r'=='

    PLUS = r'\+'
    MINUS = r'-'
    TIMES = r'\*'
    DIVIDE = r'/'
    ASSIGN = r'='
    LESS = r'\<'
    GREATER = r'\>'


if __name__ == '__main__':
    codigo_prueba = """
    BEGIN
    dOubLeF IF eLse WHILE {{ Esto ES un Comentario de PRUEBA }}
    { Hola Mundo } {{ ComentArIo
       MultIlínNea }}
    { cadena sin cierre
    palabras sin apertura }
    j := 2.3d
    z := 5.
    m := -.1d5;
    n := -2.4;
    x := a -1.5 + -2.5 - 3.0d-5;
    -123$ui; +65535$ui; 70000$ui; a -5$ui;

    1.0 .6 1 3d3;
    0.0 1.2d+10 1.0d+400 1.0d-400; 
     -1.0d+400
    {{ CoMentariO sin Cerrar

    """

    ts = TablaSimbolos()
    lexer = AnalizadorLexico(ts)
    print("--- INICIO DEL ANÁLISIS LÉXICO ---\n")
    for token in lexer.tokenize(codigo_prueba):
        print(f"Token(type={token.type:<12}, value={repr(token.value)}, lineno={token.lineno})")
    print("\n--- FIN DEL ANÁLISIS LÉXICO ---")
    ts.imprimir_tabla()