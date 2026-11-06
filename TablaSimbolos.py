class TablaSimbolos:
    # Catálogo estático de palabras reservadas del lenguaje
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
        # Clave: (lexema, tipo_token)
        # Valor: dict con 'lexema', 'token' y 'valor'
        self._simbolos = {}

        # Precarga automática de las palabras reservadas del lenguaje
        self._cargar_palabras_reservadas()

    def _cargar_palabras_reservadas(self):
        """Carga todas las palabras reservadas al inicializar la tabla."""
        for lexema, token in self.PALABRAS_RESERVADAS.items():
            self.insertar(lexema, token, valor=lexema)

    def insertar(self, lexema, tipo_token, valor=None):
        """Inserta un símbolo en la tabla. 
        Si no se indica un valor (como en ID o DOUBLEF), queda en None."""
        clave = (str(lexema), tipo_token)
        if clave not in self._simbolos:
            self._simbolos[clave] = {
                'lexema': str(lexema),
                'token': tipo_token,
                'valor': valor
            }

    def actualizar_valor(self, lexema, nuevo_valor):
        """Permite actualizar el valor de un símbolo/variable desde el sintáctico/semántico."""
        clave = (str(lexema), 'ID')
        if clave in self._simbolos:
            self._simbolos[clave]['valor'] = nuevo_valor
            return True
        return False

    def obtener_valor(self, lexema):
        clave = (str(lexema), 'ID')
        if clave in self._simbolos:
            return self._simbolos[clave]['valor']
        return None

    def imprimir_tabla(self):
        """Muestra la tabla de símbolos formateada en consola."""
        ancho = 64
        print("\n" + "=" * ancho)
        print(f"{'TABLA DE SÍMBOLOS':^{ancho}}")
        print("=" * ancho)
        print(f"{'LEXEMA':<30} | {'TOKEN':<22} | {'VALOR':<20}")
        print("-" * ancho)
        for s in self._simbolos.values():
            val_str = str(s['valor']) if s['valor'] is not None else "-"
            if len(val_str) > 20:
                val_str = val_str[:17] + "..."
            print(f"{s['lexema']:<30} | {s['token']:<22} | {val_str:<20}")
        print("=" * ancho + "\n")