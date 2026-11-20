# Compilador Grupo 19

Para compilar una prueba, escribís `python main.py` y el nombre de la prueba:

```
python main.py ok_uinteger_literales
```

No hace falta escribir `test/` ni `.txt`. Tampoco hace falta escribir el nombre completo:
con un pedazo que sea único alcanza.

```
python main.py uinteger_negativo
```

Si el pedazo coincide con varias pruebas, el programa te avisa y te muestra cuáles son
para que elijas una.

También podés pasarle la ruta a cualquier archivo tuyo:

```
python main.py C:\cosas\mi_programa.txt
```


## Para ensamblar y ejecutar el resultado

Cuando la compilación sale sin errores, se genera `ensamblar.bat`.
Haciendo doble clic (o ejecutándolo desde la terminal) ensambla, enlaza y corre el programa.
Necesita tener **MASM32** instalado en `\masm32`.


### Qué muestra?

Siempre muestra estas tres cosas, **en este orden**:

1. **Errores y warnings**
2. **Tercetos** (el código intermedio)
3. **Tabla de símbolos**

Si no hubo ningún error, además genera `salida.asm` y `ensamblar.bat`
(quedan en la carpeta desde donde ejecutaste el comando).
Si hubo errores, avisa que **no** generó el Assembler.

---

## Mostrar solo lo que me interesa

Si no querés ver todo, podés apagar partes:

| Opción | Qué hace |
|---|---|
| `--no-errores` o `-E` | No muestra los errores |
| `--no-tercetos` o `-T` | No muestra los tercetos |
| `--no-ts` o `-S` | No muestra la tabla de símbolos |
| `--solo ...` | Muestra **solamente** lo que le digas |
| `--no-asm` | No genera `salida.asm` ni `ensamblar.bat` |

Ejemplos:

```
python main.py ok_funcion_con_retorno --no-ts
python main.py ok_funcion_con_retorno -T -S
python main.py err_variable_no_declarada --solo errores
python main.py ok_if_con_else --solo tercetos ts
python main.py ok_if_con_else --no-asm
```

Para `--solo` las palabras que se pueden usar son: `errores`, `tercetos` y `ts`.
Podés poner una sola o varias.

Se pueden combinar las opciones como quieras.

---

## Ver qué pruebas hay

```
python main.py --lista
```

Imprime los nombres de todas las pruebas de la carpeta `test/`.
Si ejecutás `python main.py` sin nada más, te muestra la ayuda y también esa lista.

---

## Correr todas las pruebas de una

```
python main.py --todas
```

Compila una por una (sin generar Assembler)
y te dice si cada una se portó como se esperaba. Se ve algo así:

```
[PASA ] ok_uinteger_literales          esperado: sin errores   obtenido: sin errores
[PASA ] err_uinteger_negativo          esperado: con errores   obtenido: con errores
[FALLA] ok_algo                        esperado: sin errores   obtenido: con errores

2/3 pruebas se comportaron como se esperaba.
```

¿Cómo sabe qué se espera? Por **cómo empieza el nombre** del archivo:

- `ok_...` → tiene que compilar **sin errores**.
- `err_...` → tiene que dar **al menos un error**.

Si querés correr solo algunas, agregás una palabra de filtro:

```
python main.py --todas funcion      # solo las que tengan "funcion" en el nombre
python main.py --todas err_         # solo las de error
python main.py --todas ok_clase     # solo las válidas de clases
```

Si alguna falla, el programa termina con código de error (útil si lo usás en un script).

---

## Agregar una prueba nueva

1. Creá un archivo `.txt` dentro de `test/`.
2. Ponele un nombre que empiece con `ok_` (si debe compilar bien) o `err_` (si debe dar error).
   Por ejemplo: `ok_while_simple.txt` o `err_funcion_sin_nombre.txt`.
3. Escribí el programa adentro.
4. Corrélo con `python main.py ok_while_simple`.

```
prueba

{{ Esperado: se imprime 5 }}

uinteger a;

BEGIN
    a := 5$ui;
    pout(a);
END
```

---
