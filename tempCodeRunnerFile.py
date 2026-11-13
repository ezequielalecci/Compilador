PROGRAMA = '''
prueba_completa
UINTEGER a, b;
DOUBLEF x, y;

UINTEGER FUNCTION doble(UINTEGER n)
UINTEGER a;
BEGIN
    a := (n + n)
    ret(a);
END;

AUTO FUNCTION media(DOUBLEF u, DOUBLEF v)
DOUBLEF a;
BEGIN
    a := (u + v) / 2$ui;
    ret(a);
END;

FUNCTION saludar(UINTEGER veces)
BEGIN
    pout({hola desde una funcion});
    pout(veces);
END;

CLASS contador BEGIN
    UINTEGER cuenta;
    PRIVATE UINTEGER paso;
    UINTEGER FUNCTION sumar(UINTEGER k)
    BEGIN
        cuenta := cuenta + k;
        ret(cuenta);
    END;
END;

contador c;

BEGIN
    a := 5$ui;
    b := doble(a) + 1$ui;
    pout(b);

    x := media(1.5, 2.5);
    pout(x);

    saludar(b);

    c.cuenta := 10$ui;
    a := c.sumar(5$ui);
    pout(a);
    pout(c.cuenta);

    while (a < 20$ui) repeat
    begin
        a := a + 1$ui;
    end;

    a := toui(2.0);
    pout(a);
END
'''