PROGRAMA = '''
prueba_completa
UINTEGER a, b, c;
DOUBLEF x, y, z;

BEGIN
    a := 30$ui;
    b := 70000$ui;
    c := -4$ui;
    pout(a);
    pout(b);
    
    x := 2.2250738585072014d-308;
    pout(x);
    pout
END
'''

PROGRAMA = '''
prueba_doublef
DOUBLEF a, b, c, d, e, f, g, h, i, j, k, l;

BEGIN
    pout({Numeros positivos y negativos});
    a := 1.0;
    b := -1.2;
    pout(a);
    pout(b);

    pout({Sin parte entera});
    c := .6;
    d := .2d34;
    pout(c);
    pout(d);

    pout({Exponentes negativos y positivos});
    e := 3.0d-5;
    f := 2.5d-1;
    g := 1.2d+10;
    pout(e);
    pout(f);
    pout(g);

    pout({Exponente sin signo});
    h := 1.5d10;
    pout(h);

    pout({Sin exponente});
    i := 15.2;
    pout(i);

    pout({Valores muy pequenos y grandes});
    k := 2.2250738585072014d-307;
    l := 1.7976931348623156d308;
    pout(k);
    pout(l);
    
    pout({Valores fuera de rango});
    k := 1.8d308;
    l := -1.8d308;
    pout(k);
    pout(l);
END
'''

PROGRAMA = '''
prueba

BEGIN
    pout({una sola linea});
    pout({
        esto
        no
        se
        puede
    })
END
'''

PROGRAMA = '''
prueba

uinteger x, res, const;
doublef y, afuera, resf;

uinteger function retorno_correcto(uinteger a, doublef b)
uinteger aux;
begin
    pout(b);
    aux := toui(b);
    pout(aux);
    
    ret(a+aux);
end;

function sin_retorno()
begin
    pout({esta funcion no tiene retorno});
end;

auto function retorna_afuera()
begin
    ret(afuera);
end;

BEGIN
    x := 1$ui;
    y := 2.7;
    const := 3$ui;
    res := retorno_correcto(x, y) / const;
    pout(res);
    sin_retorno();
    
    afuera := 5.6;
    resf := retorna_afuera();
    pout(resf);
END
'''

PROGRAMA = '''
prueba

class test
begin

    doublef fijo;
    
    uinteger function constructor(doublef val)
    begin
        fijo := val;
        ret(0$ui);
    end;
end;

test t;

BEGIN
    t.constructor(10.5);
    pout(t.fijo);
END
'''