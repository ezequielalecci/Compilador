
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

    def imprimir_tabla(self):
        ancho = 110

        print("\n" + "=" * ancho)
        print(f"{'TABLA DE SÍMBOLOS':^{ancho}}")
        print("=" * ancho)

        print(
            f"{'NOMBRE INTERNO':<30} | "
            f"{'TOKEN':<12} | "
            f"{'TIPO':<12} | "
            f"{'USO':<15} | "
            f"{'ÁMBITO':<25}"
        )

        print("-" * ancho)

        for simbolo in self._simbolos.values():
            print(
                f"{simbolo['lexema']:<30} | "
                f"{simbolo['token']:<12} | "
                f"{str(simbolo.get('tipo') or '-'):<12} | "
                f"{str(simbolo.get('uso') or '-'):<15} | "
                f"{str(simbolo.get('ambito') or '-'):<25}"
            )

        print("=" * ancho + "\n")
