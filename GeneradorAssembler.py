"""
GeneradorAssembler.py  -  TP4 (Grupo 19)

Genera Assembler Pentium 32 bits (MASM32) a partir de los tercetos del TP3.
  - Enteros (UINTEGER, 16 bits)  -> registros AX, BX, DX         (DW)
  - Punto flotante (DOUBLEF, 64) -> co-procesador 80x87          (DQ)
  - Mecanismo de salida: VARIABLES AUXILIARES: cada terceto aritmetico guarda su
    resultado en _t<unidad>_<n>; el terceto [n] se referencia con esa variable.

Controles en tiempo de ejecucion (mensaje + ExitProcess):
  d) overflow en producto de enteros       -> 'mul' + 'jc'
  e) overflow en producto de flotantes     -> 'fxam' detecta +-infinito
  f) resta de enteros sin signo negativa   -> 'sub' + 'jc'
  g) perdida de informacion DOUBLEF->UINT  -> TOUI: parte fraccionaria o fuera de [0, 65535]

Funciones (contrato con los tercetos del TP3):
    ( ARG  , valor , param_mangleado )   copia el argumento a la variable del parametro
    ( CALL , nombre_unidad , None )      tipo = UINTEGER / DOUBLEF / None (void)
    ( RET  , valor , None )              entero -> AX, flotante -> ST(0)
  'nombre_unidad' debe coincidir con UnidadCodigo.nombre de la funcion; los parametros y
  variables locales son estaticos (no hay recursion). Los ARG de una llamada se emiten
  despues de evaluar todos los argumentos y justo antes del CALL.
  Atributos de objetos ('.'): cualquier simbolo de la TS con uso 'variable' (por ejemplo
  uno registrado como 'obj.atributo') recibe almacenamiento propio.

Uso (al final del main del parser, si no hubo errores):
    from GeneradorAssembler import GeneradorAssembler
    GeneradorAssembler(ts, gen).generar('salida.asm')
"""

import re
from CodigoIntermedio import UINTEGER, DOUBLEF

ARIT = {'+', '-', '*', '/'}
COMPARACIONES = {'<', '<=', '>', '>=', '==', '!='}
# BF salta cuando la condicion es FALSA -> salto inverso.
# Tanto cmp (enteros sin signo) como fcompp+sahf (flotantes) dejan CF/ZF
# de modo que se usan los saltos "sin signo".
SALTO_INVERSO = {'<': 'jae', '<=': 'ja', '>': 'jbe', '>=': 'jb', '==': 'jne', '!=': 'je'}

ERRORES_RT = {
    '_err_mul_ui': 'Error en ejecucion: overflow en producto de enteros.',
    '_err_mul_f':  'Error en ejecucion: overflow en producto de punto flotante.',
    '_err_resta':  'Error en ejecucion: resultado negativo en resta de enteros sin signo.',
    '_err_conv':   'Error en ejecucion: perdida de informacion en conversion de flotante a entero.',
    '_err_div0':   'Error en ejecucion: division por cero.',
}


def _san(nombre):
    s = str(nombre)
    # Reemplazamos los puntos y dos puntos estructurales por '@' (válido en MASM, prohibido para el usuario)
    # Ya que MASM usa el . y : para directivas, estructuras especiales y etiquetas de salto
    s = s.replace('.', '@').replace(':', '@')
    return re.sub(r'[^0-9a-zA-Z@_]', '_', s)


class GeneradorAssembler:
    def __init__(self, tabla, gen):
        self.tabla = tabla
        # main primero (se ejecuta), despues las funciones
        self.unidades = [gen.unidad] + list(gen.terminadas)
        self.codigo = []
        self.cadenas = {}     # lexema TS '{texto}' -> etiqueta
        self.flotantes = {}   # lexema TS -> (etiqueta, valor)

    # ------------------------------------------------------------------
    # Operandos: devuelve (texto_asm, tipo, clase)  clase in {'imm','mem','str'}
    # ------------------------------------------------------------------
    def _aux(self, uid, n):
        return f'_t{uid}_{n}'

    def _op(self, ref, uid):
        if isinstance(ref, int):
            t = self.unidades[uid].tercetos[ref]
            return self._aux(uid, ref), t.tipo, 'mem'
        if ref.startswith('{'):
            if ref not in self.cadenas:
                self.cadenas[ref] = f'_str{len(self.cadenas)}'
            return self.cadenas[ref], 'CADENA', 'str'
        if ref.endswith('$ui'):
            return str(int(ref[:-3])), UINTEGER, 'imm'
        info = self.tabla.buscar(ref, 'ID')
        if info is not None:
            return 'v_' + _san(ref), info['tipo'], 'mem'
        if self.tabla.buscar(ref, 'FLOAT') is not None:
            if ref not in self.flotantes:
                v = float(ref.lower().replace('d', 'e'))
                self.flotantes[ref] = (f'_f{len(self.flotantes)}', v)
            return self.flotantes[ref][0], DOUBLEF, 'mem'
        raise ValueError(f"operando desconocido en la TS: {ref!r}")

    def e(self, linea):
        self.codigo.append('    ' + linea)

    # ------------------------------------------------------------------
    # Tercetos
    # ------------------------------------------------------------------
    def _aritmetica(self, uid, i, t):
        a, ta, _ = self._op(t.a1, uid)
        b, _, _ = self._op(t.a2, uid)
        d = self._aux(uid, i)
        if t.tipo == UINTEGER:
            if t.op == '+':
                self.e(f'mov ax, {a}'); self.e(f'add ax, {b}'); self.e(f'mov {d}, ax')
            elif t.op == '-':
                self.e(f'mov ax, {a}'); self.e(f'sub ax, {b}')
                self.e('jc _err_resta')                       # control f)
                self.e(f'mov {d}, ax')
            elif t.op == '*':
                self.e(f'mov ax, {a}'); self.e(f'mov bx, {b}'); self.e('mul bx')
                self.e('jc _err_mul_ui')                      # control d)  (DX != 0)
                self.e(f'mov {d}, ax')
            else:
                self.e(f'mov ax, {a}'); self.e(f'mov bx, {b}')
                self.e('cmp bx, 0'); self.e('je _err_div0')
                self.e('xor dx, dx'); self.e('div bx'); self.e(f'mov {d}, ax')
        else:
            self.e(f'fld {a}')
            if t.op == '+':
                self.e(f'fadd {b}')
            elif t.op == '-':
                self.e(f'fsub {b}')
            elif t.op == '*':
                self.e(f'fmul {b}')
                self.e('fxam')                                # control e)
                self.e('fstsw ax')
                self.e('and ah, 45h')                         # C3,C2,C0
                self.e('cmp ah, 05h')                         # C2=1,C0=1,C3=0 -> infinito
                self.e('je _err_mul_f')
            else:
                self.e(f'fdiv {b}')
            self.e(f'fstp {d}')

    def _neg(self, uid, i, t):
        a, _, _ = self._op(t.a1, uid)
        self.e(f'fld {a}'); self.e('fchs'); self.e(f'fstp {self._aux(uid, i)}')

    def _comparacion(self, uid, t):
        a, ta, _ = self._op(t.a1, uid)
        b, _, _ = self._op(t.a2, uid)
        if ta == UINTEGER:
            self.e(f'mov ax, {a}'); self.e(f'cmp ax, {b}')
        else:
            self.e(f'fld {b}'); self.e(f'fld {a}')            # ST0=a, ST1=b
            self.e('fcompp'); self.e('fstsw ax'); self.e('sahf')

    def _toui(self, uid, i, t):
        a, _, _ = self._op(t.a1, uid)
        d = self._aux(uid, i)
        self.e(f'fld {a}')
        # forzar redondeo por truncamiento (RC = 11)
        self.e('fnstcw _cw_old')
        self.e('mov ax, _cw_old')
        self.e('or ax, 0C00h')
        self.e('mov _cw_new, ax')
        self.e('fldcw _cw_new')
        self.e('fistp DWORD PTR _conv32')
        self.e('fldcw _cw_old')                 # restaurar antes de cualquier salto
        self.e('mov eax, _conv32')
        self.e('cmp eax, 65535')
        self.e('ja _err_conv')                  # negativo (como sin signo es enorme) o > 65535
        self.e(f'mov {d}, ax')

    def _conv(self, uid, i, t):
        """UINTEGER -> DOUBLEF (conversion implicita de los 'ret' de funciones AUTO)."""
        a, _, clase = self._op(t.a1, uid)
        if clase == 'imm':
            self.e(f'mov eax, {a}')
        else:
            self.e(f'movzx eax, WORD PTR {a}')
        self.e('mov _conv32, eax')
        self.e('fild DWORD PTR _conv32')
        self.e(f'fstp {self._aux(uid, i)}')

    def _asignacion(self, uid, t):
        dst, td, _ = self._op(t.a1, uid)
        src, _, _ = self._op(t.a2, uid)
        if td == UINTEGER:
            self.e(f'mov ax, {src}'); self.e(f'mov {dst}, ax')
        else:
            self.e(f'fld {src}'); self.e(f'fstp {dst}')

    def _pout(self, uid, t):
        x, tipo, clase = self._op(t.a1, uid)
        if tipo == 'CADENA':
            self.e(f'invoke MessageBox, NULL, addr {x}, addr _titulo, MB_OK')
            return
        if tipo == UINTEGER:
            if clase == 'imm':
                self.e(f'mov eax, {x}')
            else:
                self.e(f'movzx eax, WORD PTR {x}')
            self.e('invoke wsprintf, addr _buf, addr _fmt_ui, eax')
        else:
            self.e(f'push DWORD PTR [{x}+4]'); self.e(f'push DWORD PTR [{x}]')
            self.e('push offset _fmt_f'); self.e('push offset _buf')
            self.e('call crt_sprintf'); self.e('add esp, 16')
        self.e('invoke MessageBox, NULL, addr _buf, addr _titulo, MB_OK')

    def _retorno(self, uid, t):
        # Convencion: entero en AX, flotante en ST(0)
        x, tipo, clase = self._op(t.a1, uid)
        if tipo == UINTEGER:
            self.e(f'mov ax, {x}')
        else:
            self.e(f'fld {x}')
        self.e('ret')

    # ---- funciones --------------------------------------------------
    # Contrato con el TP3 (ver docstring): parametros por valor, copiados a las
    # variables estaticas del parametro de la funcion (ARG) justo antes del CALL.
    def _arg(self, uid, t):
        src, ts_, _ = self._op(t.a1, uid)
        dst, td, _ = self._op(t.a2, uid)
        if td == UINTEGER:
            self.e(f'mov ax, {src}'); self.e(f'mov {dst}, ax')
        else:
            self.e(f'fld {src}'); self.e(f'fstp {dst}')

    def _call(self, uid, i, t):
        self.e(f'call fn_{_san(t.a1)}')
        # el resultado se guarda de inmediato en la variable auxiliar del terceto
        if t.tipo == UINTEGER:
            self.e(f'mov {self._aux(uid, i)}, ax')
        elif t.tipo == DOUBLEF:
            self.e(f'fstp {self._aux(uid, i)}')

    def _unidad(self, uid, u):
        tercs = u.tercetos
        destinos = set()
        for t in tercs:
            if t.op == 'BI' and isinstance(t.a1, int):
                destinos.add(t.a1)
            elif t.op == 'BF' and isinstance(t.a2, int):
                destinos.add(t.a2)

        for i, t in enumerate(tercs):
            if i in destinos:
                self.codigo.append(f'L{uid}_{i}:')
            self.codigo.append(f'    ; [{i}] ( {t.op} , {t.a1} , {t.a2} )')
            if t.op in ARIT:
                self._aritmetica(uid, i, t)
            elif t.op == 'NEG':
                self._neg(uid, i, t)
            elif t.op in COMPARACIONES:
                self._comparacion(uid, t)
            elif t.op == 'TOUI':
                self._toui(uid, i, t)
            elif t.op == 'CONV':
                self._conv(uid, i, t)
            elif t.op == 'NOP':
                pass
            elif t.op == ':=':
                self._asignacion(uid, t)
            elif t.op == 'POUT':
                self._pout(uid, t)
            elif t.op == 'RET':
                self._retorno(uid, t)
            elif t.op == 'ARG':
                self._arg(uid, t)
            elif t.op == 'CALL':
                self._call(uid, i, t)
            elif t.op == 'BI':
                self.e(f'jmp L{uid}_{t.a1}')
            elif t.op == 'BF':
                cond = tercs[t.a1]          # la comparacion deja los flags listos
                self.e(f'{SALTO_INVERSO[cond.op]} L{uid}_{t.a2}')
            else:
                self.e(f'; terceto no soportado todavia: {t.op}')
        if len(tercs) in destinos:
            self.codigo.append(f'L{uid}_{len(tercs)}:')

    # ------------------------------------------------------------------
    # Programa completo
    # ------------------------------------------------------------------
    def generar(self, ruta='salida.asm'):
        self.codigo = []
        for uid, u in enumerate(self.unidades):
            if uid == 0:
                self._unidad(uid, u)
                self.e('invoke ExitProcess, 0')
                for etiqueta, msg in ERRORES_RT.items():
                    self.codigo.append(f'{etiqueta}:')
                    self.e(f'invoke MessageBox, NULL, addr {etiqueta[1:]}_msg, addr _titulo, MB_ICONERROR')
                    self.e('invoke ExitProcess, 1')
            else:
                self.codigo.append(f'fn_{_san(u.nombre)}:')
                self._unidad(uid, u)
                self.e('ret')

        L = []
        L += ['.386', '.model flat, stdcall', 'option casemap :none',
              'include \\masm32\\include\\windows.inc',
              'include \\masm32\\include\\kernel32.inc',
              'include \\masm32\\include\\user32.inc',
              'include \\masm32\\include\\msvcrt.inc',
              'includelib \\masm32\\lib\\kernel32.lib',
              'includelib \\masm32\\lib\\user32.lib',
              'includelib \\masm32\\lib\\msvcrt.lib', '', '.data']
        L += ['_titulo DB "Programa",0',
                '_fmt_ui DB "%u",0', '_fmt_f DB "%g",0',
                '_buf DB 400 DUP(0)', '_conv32 DD 0',
                '_cw_old DW 0', '_cw_new DW 0']
        for etiqueta, msg in ERRORES_RT.items():
            L.append(f'{etiqueta[1:]}_msg DB "{msg}",0')
        # variables del programa
        for (nombre, token), s in self.tabla._simbolos.items():
            if token == 'ID' and s.get('uso') in ('variable', 'parametro'):
                if s.get('tipo') == UINTEGER:
                    L.append(f'v_{_san(nombre)} DW 0')
                elif s.get('tipo') == DOUBLEF:
                    L.append(f'v_{_san(nombre)} DQ 0.0')
        # auxiliares
        for uid, u in enumerate(self.unidades):
            for i, t in enumerate(u.tercetos):
                if (t.op in ARIT or t.op in ('NEG', 'TOUI', 'CONV')
                        or (t.op == 'CALL' and t.tipo in (UINTEGER, DOUBLEF))):
                    L.append(f'{self._aux(uid, i)} ' + ('DW 0' if t.tipo == UINTEGER else 'DQ 0.0'))
        for lex, (etq, v) in self.flotantes.items():
            L.append(f'{etq} DQ {v:.17e}')
        for lex, etq in self.cadenas.items():
            texto = lex[1:-1].encode('cp1252', 'replace') + b'\x00'   # incluye el terminador
            for k in range(0, len(texto), 16):
                trozo = ','.join(str(b) for b in texto[k:k + 16])
                prefijo = f'{etq} ' if k == 0 else '    '
                L.append(f'{prefijo}DB {trozo}')
        L += ['', '.code', 'start:', '    finit']
        L += self.codigo
        L += ['end start', '']

        with open(ruta, 'w', encoding='cp1252', errors='replace') as f:
            f.write('\n'.join(L))
        return ruta