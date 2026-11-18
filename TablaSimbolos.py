
class TablaSimbolos:
    PALABRAS_RESERVADAS = {
        'IF': 'IF',
        'ELSE': 'ELSE',
        'END_IF': 'END_IF',
        'BEGIN': 'BEGIN',
        'END': 'END',
        'POUT': 'POUT',
        'RET': 'RET',
        'CLASS': 'CLASS',
        'FUNCTION': 'FUNCTION',
        'DOUBLEF': 'DOUBLEF',
        'REPEAT': 'REPEAT',
        'WHILE': 'WHILE',
        'AUTO': 'AUTO',
        'COMPTIME': 'COMPTIME',
        'FRIEND': 'FRIEND',
        'PRIVATE': 'PRIVATE',
        'TOUI': 'TOUI',
        'UINTEGER': 'UINTEGER'
    }

    def __init__(self):
        # Símbolos declarados y constantes.
        # Clave: (nombre_interno, token)
        self._simbolos = {}

        # Identificadores reconocidos por el léxico.
        # No representan declaraciones semánticas.
        self._lexemas = set()

        self._cargar_palabras_reservadas()

    def _cargar_palabras_reservadas(self):
        for lexema, token in self.PALABRAS_RESERVADAS.items():
            self.insertar(lexema, token, valor=lexema)

    def insertar(self, lexema, tipo_token, valor=None):
        lexema = str(lexema)

        # Los ID se almacenan como lexemas, no como declaraciones.
        if tipo_token == 'ID':
            self._lexemas.add(lexema)
            return

        clave = (lexema, tipo_token)

        if clave not in self._simbolos:
            self._simbolos[clave] = {
                'lexema': lexema,
                'token': tipo_token,
                'valor': valor
            }

    def registrar(self, nombre_interno, token, **atributos):
        """
        Registra una declaración semántica.
        nombre_interno incluye el ámbito mediante name mangling.
        """
        clave = (str(nombre_interno), token)

        if clave not in self._simbolos:
            self._simbolos[clave] = {
                'lexema': str(nombre_interno),
                'token': token,
                'valor': None
            }

        self._simbolos[clave].update(atributos)

    def buscar(self, nombre_interno, token='ID'):
        return self._simbolos.get((str(nombre_interno), token))

    def actualizar_valor(self, nombre_interno, nuevo_valor):
        clave = (str(nombre_interno), 'ID')

        if clave in self._simbolos:
            self._simbolos[clave]['valor'] = nuevo_valor
            return True

        return False

    def obtener_valor(self, nombre_interno):
        clave = (str(nombre_interno), 'ID')

        if clave in self._simbolos:
            return self._simbolos[clave]['valor']

        return None

    def imprimir_tabla(self, mostrar_reservadas=True, ascii_puro=False):
        if ascii_puro:
            H, V = '-', '|'
            TL, TM, TR = '+', '+', '+'
            ML, MM, MR = '+', '+', '+'
            BL, BM, BR = '+', '+', '+'
        else:
            H, V = '─', '│'
            TL, TM, TR = '┌', '┬', '┐'
            ML, MM, MR = '├', '┼', '┤'
            BL, BM, BR = '└', '┴', '┘'

        encabezados = ['NOMBRE INTERNO', 'TOKEN', 'TIPO', 'USO', 'ÁMBITO', 'VALOR']
        maximos     = [34, 12, 10, 10, 24, 22]

        def celda(x):
            if x is None or x == '':
                return '-'
            return str(x)

        filas = []
        for s in self._simbolos.values():
            es_reservada = self.PALABRAS_RESERVADAS.get(s['lexema']) == s['token']
            if es_reservada and not mostrar_reservadas:
                continue
            filas.append([
                celda(s['lexema']),
                celda(s['token']),
                celda(s.get('tipo')),
                celda(s.get('uso')),
                celda(s.get('ambito')),
                celda(s.get('valor')),
            ])

        # Ancho de cada columna: el del contenido más largo, con tope por columna
        anchos = []
        for i, enc in enumerate(encabezados):
            ancho = max([len(enc)] + [len(f[i]) for f in filas])
            anchos.append(min(ancho, maximos[i]))

        def recortar(texto, ancho):
            return texto if len(texto) <= ancho else texto[:ancho - 3] + '...'

        def linea(izq, medio, der):
            return izq + medio.join(H * (a + 2) for a in anchos) + der

        def fila(valores):
            celdas = [f' {recortar(v, a).ljust(a)} ' for v, a in zip(valores, anchos)]
            return V + V.join(celdas) + V

        total = sum(anchos) + 3 * len(anchos) + 1
        titulo = 'TABLA DE SÍMBOLOS'

        print()
        print(linea(TL, H, TR))
        print(V + titulo.center(total - 2) + V)
        print(linea(ML, TM, MR))
        print(fila(encabezados))
        print(linea(ML, MM, MR))
        for f in filas:
            print(fila(f))
        print(linea(BL, BM, BR))
        print(f"  {len(filas)} símbolo(s)\n")
