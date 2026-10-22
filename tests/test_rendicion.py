"""tests/test_rendicion.py — la rendición de cuentas de viáticos (servicios/rendicion.py,
rendicion_tex.py, rendicion_excel.py; el formato de pegado `comprobantes-gasto`).

El cálculo replica fórmula por fórmula el libro de liquidación de referencia (hoja «Rendición»):
reconocido = MIN(A, tope) + B; exceso = MAX(0, A − tope); saldo = asignado − reconocido; controles
B ≤ tope DJ, reconocido ≤ tope, exceso = 0; movilidad sugerida = el menor entre el tope DJ y lo que falta.
Pruebas puras (sin base de datos). Todas las cifras, nombres y proveedores son FICTICIOS.
Uso: cd backend && .venv/bin/python -m pytest -q tests/test_rendicion.py
"""
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:y@127.0.0.1/z")
os.environ.setdefault("JWT_SECRET", "prueba")

import pytest  # noqa: E402

from yupay import rendicion as r  # noqa: E402

DIAS = ["2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28"]
PARAM = {"tope_diario": 320, "pct_dj": 30, "tope_dj": None, "recibido_viaticos": None,
         "recibido_pasajes": 0, "recibido_otros": 0, "plazo_dias_habiles": 10}


def _c(i, fecha, concepto, importe, **extra):
    base = {"id": i, "fecha": fecha, "concepto": concepto, "importe": importe, "tipo": "boleta_electronica",
            "serie": "EB01", "numero": str(100 + i), "ruc": "20000000001", "proveedor": "Proveedor SAC", "archivo": "x.jpg"}
    return {**base, **extra}


COMPROBANTES = [
    _c(1, DIAS[0], "desayuno", 10), _c(2, DIAS[0], "almuerzo", 25), _c(3, DIAS[0], "cena", 20), _c(4, DIAS[0], "hospedaje", 120),
    _c(5, DIAS[1], "almuerzo", 30), _c(6, DIAS[1], "hospedaje", 300),
    _c(7, DIAS[2], "otros_alimentacion", 250),
    _c(8, DIAS[4], "almuerzo", 100),
]
DECLARADOS = [
    {"id": 1, "clase": "movilidad", "fecha": DIAS[0], "monto": 50}, {"id": 2, "clase": "movilidad", "fecha": DIAS[0], "monto": 46},
    {"id": 3, "clase": "movilidad", "fecha": DIAS[2], "monto": 96},
    {"id": 4, "clase": "movilidad", "fecha": DIAS[4], "monto": 90}, {"id": 5, "clase": "otro", "fecha": DIAS[4], "monto": 10, "concepto": "Fotocopias"},
]


def _param():
    return r.parametros_vigentes({}, PARAM, len(DIAS))


def test_liquidacion_replica_el_libro():
    liq = r.liquidar(DIAS, COMPROBANTES, DECLARADOS, _param())
    d = {x["fecha"]: x for x in liq["dias"]}
    # Día 1: A = 175, B = 96 → reconocido 271, saldo 49, sugerida MIN(96, 145) = 96.
    assert d[DIAS[0]]["subtotal_a"] == 175 and d[DIAS[0]]["dj"] == 96
    assert d[DIAS[0]]["reconocido"] == 271 and d[DIAS[0]]["saldo"] == 49 and d[DIAS[0]]["sugerida"] == 96
    # Día 2: A = 330 > 320 → exceso 10, reconocido = MIN(330, 320) = 320, saldo 0, sugerida 0.
    assert d[DIAS[1]]["exceso"] == 10 and d[DIAS[1]]["reconocido"] == 320 and d[DIAS[1]]["saldo"] == 0
    assert d[DIAS[1]]["sugerida"] == 0 and not d[DIAS[1]]["sin_exceso"]
    # Día 3: A = 250 y B = 96 → reconocido 346 pasa el tope (REVISAR); sugerida MIN(96, 70) = 70.
    assert d[DIAS[2]]["reconocido"] == 346 and not d[DIAS[2]]["total_ok"] and d[DIAS[2]]["dj_ok"]
    assert d[DIAS[2]]["sugerida"] == 70 and d[DIAS[2]]["saldo"] == -26
    # Día 4: nada → saldo = todo el viático.
    assert d[DIAS[3]]["saldo"] == 320 and d[DIAS[3]]["sugerida"] == 96
    # Día 5: B = 90 + 10 = 100 > 96 → la DJ pasa el tope; la sugerida descuenta los otros: 96 − 10 = 86.
    assert d[DIAS[4]]["dj"] == 100 and not d[DIAS[4]]["dj_ok"] and d[DIAS[4]]["sugerida"] == 86
    # Totales (hoja Resumen).
    assert liq["asignado"] == 1600 and liq["recibido"] == 1600
    assert liq["con_comprobante"] == 855 and liq["dj"] == 292 and liq["rendido"] == 1147
    assert liq["reconocido"] == 1137 and liq["exceso"] == 10 and liq["saldo"] == 463
    assert liq["pct_dj"] == 18.25 and liq["pct_dj_ok"]
    assert liq["conforme"] == {"dj": "REVISAR", "total": "REVISAR", "exceso": "REVISAR"}
    assert liq["por_concepto"]["hospedaje"] == 420
    assert liq["dj_en_letras"] == "Doscientos noventa y dos con 00/100 soles"


def test_sin_problemas_todo_conforme_y_centimos_exactos():
    comp = [_c(1, DIAS[0], "almuerzo", "0.10"), _c(2, DIAS[0], "cena", "0.20")]
    liq = r.liquidar(DIAS[:1], comp, [], _param())
    assert liq["con_comprobante"] == 0.3  # nunca 0.30000000000000004
    assert liq["conforme"] == {"dj": "CONFORME", "total": "CONFORME", "exceso": "CONFORME"}


def test_lo_recibido_manda_en_el_saldo_y_pasajes_aparte():
    p = r.parametros_vigentes({}, {**PARAM, "recibido_viaticos": 1500, "recibido_pasajes": 80}, len(DIAS))
    comp = COMPROBANTES + [_c(20, DIAS[0], "pasaje_terrestre", 60)]
    liq = r.liquidar(DIAS, comp, DECLARADOS, p)
    assert liq["saldo"] == 1500 - 1137
    assert liq["pasajes"] == {"rendido": 60, "recibido": 80, "saldo": 20}
    assert liq["con_comprobante"] == 855  # el pasaje no es viático


def test_fuera_de_los_dias_no_entra_en_el_calculo():
    liq = r.liquidar(DIAS, [_c(1, "2026-08-23", "cena", 50)], [], _param())
    assert liq["con_comprobante"] == 0


def test_parametros_precedencia_y_fuente():
    despacho = {"tope_diario": {"valor": 380, "fuente": "Ajuste"}, "pct_dj": 25}
    p = r.parametros_vigentes(despacho, {}, 2)
    assert p["tope_diario"]["valor"] == 380 and p["tope_diario"]["origen"] == "despacho"
    assert p["tope_dj"]["valor"] == 95.0 and p["recibido_viaticos"]["valor"] == 760
    p = r.parametros_vigentes(despacho, {"tope_diario": 320}, 2)
    assert p["tope_diario"]["valor"] == 320 and p["tope_diario"]["origen"] == "rendicion"
    assert r.parametros_vigentes({}, {}, 1)["tope_dj"]["valor"] == 96.0
    # Procedencia citada (leída el 2026-10-18): la directiva del Congreso y el decreto supremo del MEF.
    assert "DI 37-2025-DF-DGA-CR" in r.parametros_vigentes({}, {}, 1)["plazo_dias_habiles"]["fuente"]
    assert "007-2013-EF" in r.parametros_vigentes({}, {}, 1)["tope_diario"]["fuente"]


@pytest.mark.parametrize("n, letras", [
    (0, "Cero"), (1, "Uno"), (21, "Veintiuno"), (100, "Cien"), (101, "Ciento uno"), (437, "Cuatrocientos treinta y siete"),
    (1000, "Mil"), (1357, "Mil trescientos cincuenta y siete"), (21000, "Veintiún mil"), (101000, "Ciento un mil"),
    (1_000_000, "Un millón"), (2_500_000, "Dos millones quinientos mil"),
])
def test_importe_en_letras(n, letras):
    assert r.importe_en_letras(n * 100) == f"{letras} con 00/100 soles"


def test_importe_con_centimos_y_dias():
    assert r.importe_en_letras(234560) == "Dos mil trescientos cuarenta y cinco con 60/100 soles"
    assert r.dias_en_letras(5) == "CINCO (05)"


@pytest.mark.parametrize("texto, esperado", [
    ("S/ 2,345.60", 234560), ("2.345,60", 234560), ("40", 4000), (12.5, 1250), ("S/. 6.00", 600), ("", 0), (None, 0), ("12,5", 1250),
])
def test_centimos(texto, esperado):
    assert r.centimos(texto) == esperado


def test_sugerida_y_reparto():
    assert r.sugerida(17500, 32000, 9600) == 9600
    assert r.sugerida(25000, 32000, 9600) == 7000
    assert r.sugerida(40000, 32000, 9600) == 0
    assert r.sugerida(10000, 32000, 9600, otros_dj=1000) == 8600
    montos = r.repartir(9600, 7)
    assert sum(montos) == 9600 and all(m % 100 == 0 for m in montos) and max(montos) - min(montos) <= 100
    assert sum(r.repartir(1050, 4)) == 1050 and r.repartir(500, 0) == []


def test_tramos_desde_actividades():
    acts = [
        {"codigo": "A-02", "fecha": DIAS[0], "hora_inicio": "11:00", "hora_fin": "12:00", "lugar": "Colegio de ejemplo"},
        {"codigo": "A-01", "fecha": DIAS[0], "hora_inicio": "09:00", "lugar": "Plaza de Armas"},
        {"codigo": "A-03", "fecha": DIAS[1], "hora_inicio": "10:00", "distrito": "Distrito de ejemplo"},
        {"codigo": "A-04", "fecha": "2026-09-01", "hora_inicio": "10:00", "lugar": "Fuera"},
    ]
    t = r.tramos_desde_actividades(acts, DIAS)
    assert [(x["desde"], x["hasta"], x["hora"]) for x in t if x["fecha"] == DIAS[0]] == [
        ("Hospedaje", "Plaza de Armas", "09:00"), ("Plaza de Armas", "Colegio de ejemplo", "11:00"), ("Colegio de ejemplo", "Hospedaje", "12:00")]
    assert [x["hasta"] for x in t if x["fecha"] == DIAS[1]] == ["Distrito de ejemplo", "Hospedaje"]
    assert all(x["fecha"] in DIAS for x in t) and t[0]["actividad"] == "A-01"


def _controles(comp, decl, estado="borrador", hoy="2026-09-01", limite="2026-09-11", objetivos=None, fuera=None, **datos):
    p = _param()
    liq = r.liquidar(DIAS, comp, decl, p, objetivos)
    rend = {"fecha_inicio": DIAS[0], "fecha_fin": DIAS[-1], "estado": estado, "dni": "00000000", "cargo": "Asistente",
            "memorando": {"id": 1}, **datos}
    return r.controles(rend, liq, comp, decl, p, hoy, limite, fuera)


def _codigos(cs):
    return {c["codigo"] for c in cs}


def test_controles_de_la_rendicion_de_ejemplo():
    cs = _controles(COMPROBANTES, DECLARADOS)
    codigos = _codigos(cs)
    assert {"dj_tope", "dia_tope", "exceso", "saldo", "plazo"} <= codigos
    assert cs[0]["nivel"] == "error"  # lo grave primero
    assert not {"repetido", "sin_foto", "fuera_de_fecha", "sin_dni", "sin_memorando"} & codigos


def test_controles_de_comprobantes():
    comp = [
        _c(1, "2026-08-23", "cena", 30),                                 # fuera de la comisión
        _c(2, DIAS[0], "almuerzo", 20, numero="0007"), _c(3, DIAS[0], "cena", 20, numero="7"),   # repetido (mismo número)
        _c(4, DIAS[1], "hospedaje", 80, archivo="", tipo="recibo"),      # sin foto; recibo en la sección A (el ticket sí vale)
        _c(5, DIAS[1], "pasaje_terrestre", 40),                          # pasaje sin importe recibido de pasajes
        _c(6, DIAS[2], "cena", 0),                                       # sin importe
    ]
    cs = _controles(comp, [])
    por = {(c["codigo"], c.get("ref")) for c in cs}
    assert ("fuera_de_fecha", "comprobante:1") in por
    assert ("repetido", "comprobante:3") in por
    assert ("sin_foto", "comprobante:4") in por and ("tipo_seccion", "comprobante:4") in por
    assert ("concepto_seccion", "comprobante:5") in por
    assert ("sin_importe", "comprobante:6") in por
    otra = _controles([_c(9, DIAS[0], "cena", 20)], [], fuera={r.clave_comprobante(_c(9, DIAS[0], "cena", 20)): "en la rendición de Nombre Apellido (R-002)"})
    assert any(c["codigo"] == "repetido" and "R-002" in c["texto"] for c in otra)


def test_controles_de_declaracion_y_plazo():
    decl = [{"id": 1, "clase": "movilidad", "fecha": DIAS[0], "monto": 40}, {"id": 2, "clase": "otro", "fecha": DIAS[0], "monto": 5, "concepto": "Almuerzo sin boleta"}]
    cs = _controles([], decl, objetivos={DIAS[0]: 96})
    assert {"tramos_dj", "concepto_seccion"} <= _codigos(cs)
    vencido = _controles([], [], hoy="2026-09-20")
    assert any(c["codigo"] == "plazo" and "vencido" in c["texto"] for c in vencido)
    cerca = _controles([], [], hoy="2026-09-09")
    assert any(c["codigo"] == "plazo" and c["nivel"] == "aviso" for c in cerca)
    assert not any(c["codigo"] == "plazo" for c in _controles([], [], estado="presentada", hoy="2026-09-20"))
    sin = _controles([], [], dni="", cargo="", memorando=None)
    assert {"sin_dni", "sin_cargo", "sin_memorando", "vacia"} <= _codigos(sin)
    borrador = _controles([], [], memorando={"id": 1, "numero": "Memorando (borrador)", "numerado": False})
    assert "memorando_sin_numero" in _codigos(borrador)


def test_pct_dj_sobre_el_limite():
    p = r.parametros_vigentes({}, {**PARAM, "pct_dj": 10}, 1)
    decl = [{"id": 1, "clase": "movilidad", "fecha": DIAS[0], "monto": 50}]
    liq = r.liquidar(DIAS[:1], [], decl, p)
    assert not liq["pct_dj_ok"]
    cs = r.controles({"fecha_inicio": DIAS[0], "fecha_fin": DIAS[0], "dni": "1", "cargo": "x", "memorando": {}}, liq, [], decl, p, DIAS[0])
    assert "pct_dj" in _codigos(cs)


def test_estados():
    assert r.puede_pasar("borrador", "lista", False, 0) is None
    assert "control" in r.puede_pasar("borrador", "lista", False, 2)
    assert r.puede_pasar("lista", "presentada", False, 0) is None
    assert r.puede_pasar("borrador", "presentada", False, 0)
    assert r.puede_pasar("presentada", "observada", False, 0)
    assert r.puede_pasar("presentada", "observada", True, 0) is None
    assert r.puede_pasar("cerrada", "borrador", False, 0)
    assert r.puede_pasar("presentada", "borrador", False, 0)        # el comisionado no la reabre
    assert r.puede_pasar("presentada", "borrador", True, 0) is None


def test_documento_de_y_clave():
    assert r.documento_de({"tipo": "boleta_electronica", "serie": "EB01", "numero": "813"}) == "Boleta de venta electrónica N.° EB01-813"
    assert r.documento_de({"tipo": "factura"}) == "Factura"
    assert r.clave_comprobante({"serie": "f001", "numero": "00022", "ruc": "20000000001"}) == "20000000001|F001|22"
    assert r.clave_comprobante({"serie": "F001"}) is None


def _vista():
    p = _param()
    liq = r.liquidar(DIAS, COMPROBANTES, DECLARADOS, p)
    return {"comisionado": {"nombre": "Nombre Apellido", "dni": "00000000", "cargo": "Asistente"},
            "datos": {"fecha_inicio": DIAS[0], "fecha_fin": DIAS[-1], "lugar": "Provincia de ejemplo", "motivo": "Semana de representación & 100 % prueba",
                      "fecha_rendicion": "2026-08-31"},
            "memorando": {"numero": "Memorando N° 0001-2026-2027", "fecha": "2026-08-18"}, "unidad": "",
            "liquidacion": liq, "comprobantes": COMPROBANTES, "declarados": [dict(x, hora="15:00", desde="Hospedaje", hasta="Plaza") for x in DECLARADOS],
            "parametros": p, "nombre_archivo": "RV-SR-01_nombre-apellido"}


def test_documento_latex():
    from yupay import tex as rendicion_tex

    meta, cont = rendicion_tex.componer(_vista())
    assert "\\setmeta{comisionado}{Nombre Apellido}" in meta
    assert "\\setmeta{dias}{CINCO (05)}" in meta
    assert "\\setmeta{periodo}{del día 24 de agosto al día 28 de agosto de 2026}" in meta
    assert "\\setmeta{documentoviajefecha}{18-08-2026}" in meta
    assert "\\& 100 \\% prueba" in meta            # escapado
    assert "% \\setmeta{siaf}{}" in meta             # sin dato: renglón a mano
    assert "\\tramo{24/08/2026}{3:00 p. m.}{Hospedaje}{Plaza}{S/ 50.00}" in cont
    assert "\\otrogasto{28/08/2026}{Fotocopias}{S/ 10.00}" in cont
    assert "\\cierredeclaracion{S/ 292.00}{Doscientos noventa y dos con 00/100 soles}" in cont
    assert "\\gasto{9}{Declaración jurada}{31/08/2026}{MOVILIDAD Y OTROS}{S/ 292.00}" in cont
    assert "\\totalseccion{Sobre el viático (lo asume)}{-S/ 10.00}" in cont
    assert "\\totalseccionfuerte{Saldo}{S/ 463.00}" in cont
    assert "GENERADO por" in meta and "GENERADO por" in cont
    assert "\\setmeta{nombrearchivo}{RV-SR-01_nombre-apellido}" in meta
    # Un memorando sin número no se imprime como «borrador»: renglón para llenar a mano.
    v = _vista()
    v["memorando"] = {"numero": "Memorando (borrador)", "fecha": "2026-08-18", "numerado": False}
    meta2, _ = rendicion_tex.componer(v)
    assert "% \\setmeta{documentoviaje}{}" in meta2


def test_excel_con_formulas():
    pytest.importorskip("openpyxl")
    from yupay import excel as rendicion_excel

    wb = rendicion_excel.libro(_vista())
    ws = wb["Rendición"]
    assert ws["B11"].value == "=SUM(B6:B10)"
    assert ws["B20"].value == "=MIN(B11,Parámetros!$B$3)+B16"
    assert ws["B21"].value == "=MAX(0,B11-Parámetros!$B$3)"
    assert ws["B22"].value == "=B19-B20"
    assert ws["G26"].value == '=IF(COUNTIF(B26:F26,"OK")=5,"CONFORME","REVISAR")'
    assert ws["B6"].value == 10 and ws["C10"].value == 300
    assert wb["Parámetros"]["B3"].value == 320 and wb["Parámetros"]["B6"].value == "=B3*B5"
    assert wb["Resumen"]["B11"].value == "=B10-B9"
    assert wb.sheetnames == ["Rendición", "Resumen", "Parámetros"]   # el orden del libro de referencia


def test_efectivos_salen_de_la_semana():
    from yupay.api import efectivos

    semana = {"inicio": "2026-08-24", "fin": "2026-08-28", "region": "Región de ejemplo", "provincias": ["Uno", "Dos"]}
    d, origen = efectivos({}, semana)
    assert d["fecha_inicio"] == "2026-08-24" and origen["fecha_inicio"] == "semana"
    assert d["lugar"] == "Región de ejemplo" and d["motivo"] == "Semana de representación del mes de agosto de 2026"
    assert d["fecha_rendicion"] == "2026-08-28"
    d, origen = efectivos({"lugar": "Otro lugar"}, semana)
    assert d["lugar"] == "Otro lugar" and origen["lugar"] == "propio"


def test_ticket_vale_y_dj_diaria_es_aviso():
    """DI 37-2025-DF-DGA-CR: el ticket es comprobante (Anexo 05) y el 30 % se mide sobre el TOTAL
    otorgado (7.9.1.1.2): pasar el tope DIARIO del despacho es aviso, no error."""
    cs = _controles([_c(1, DIAS[0], "almuerzo", 20, tipo="ticket")], [{"id": 1, "clase": "movilidad", "fecha": DIAS[0], "monto": 120}])
    assert "tipo_seccion" not in _codigos(cs)
    dj = next(c for c in cs if c["codigo"] == "dj_tope")
    assert dj["nivel"] == "aviso"


def test_pendientes_retencion_y_recibido_supuesto():
    cs = _controles([_c(1, DIAS[0], "hospedaje", 750, tipo="factura_electronica")], [],
                    pendientes="Falta el Excel\n- Confirmar el comprobante de pago")
    por = {c["codigo"]: c for c in cs}
    assert por["pendientes"]["nivel"] == "aviso" and "Falta el Excel" in por["pendientes"]["texto"] and "1 más" in por["pendientes"]["texto"]
    assert por["retencion"]["ref"] == "comprobante:1"
    assert por["recibido_supuesto"]["nivel"] == "aviso" and "no consta" in por["recibido_supuesto"]["texto"]
    p = r.parametros_vigentes({}, {**PARAM, "recibido_viaticos": 1600}, len(DIAS))
    liq = r.liquidar(DIAS, [], [], p)
    cs2 = r.controles({"fecha_inicio": DIAS[0], "fecha_fin": DIAS[-1], "dni": "1", "cargo": "x", "memorando": {}}, liq, [], [], p, DIAS[0])
    assert "recibido_supuesto" not in _codigos(cs2)


def test_devolucion_con_recibo_adjunto():
    p = _param()
    liq = r.liquidar(DIAS, [], [], p)
    base = {"fecha_inicio": DIAS[0], "fecha_fin": DIAS[-1], "dni": "1", "cargo": "x", "memorando": {}}
    sin = next(c for c in r.controles(base, liq, [], [], p, DIAS[0]) if c["codigo"] == "saldo")
    con = next(c for c in r.controles(base, liq, [], [], p, DIAS[0], anexos=[{"clase": "devolucion"}]) if c["codigo"] == "saldo")
    assert "Caja de Tesorería" in sin["texto"] and "adjunto" in con["texto"]


@pytest.mark.parametrize("serie, numero, esperado", [
    ("", "EB01-1586", ("EB01", "1586")), ("", "F001 - 00004711", ("F001", "00004711")), ("", "FR95 / 12841", ("FR95", "12841")),
    ("", "001 026812", ("001", "026812")), ("", "12345", ("", "12345")), ("eb01", "1586", ("EB01", "1586")),
])
def test_partir_numero(serie, numero, esperado):
    assert r.partir_numero(serie, numero) == esperado


def test_avance_por_seccion():
    p = r.parametros_vigentes({}, {**PARAM, "recibido_viaticos": 1600}, len(DIAS))
    vacia = r.avance({"fecha_inicio": DIAS[0], "fecha_fin": DIAS[-1]}, [], [], [{"codigo": "sin_memorando", "nivel": "aviso"}], {"pdf": False})
    estados = {s["clave"]: s["estado"] for s in vacia["secciones"]}
    assert estados == {"datos": "pendiente", "comprobantes": "pendiente", "movilidad": "pendiente", "documento": "pendiente"}
    comp = [_c(1, DIAS[0], "almuerzo", 20)]
    decl = [{"id": 1, "clase": "movilidad", "fecha": DIAS[0], "monto": 10}]
    liq = r.liquidar(DIAS, comp, decl, p)
    cs = r.controles({"fecha_inicio": DIAS[0], "fecha_fin": DIAS[-1], "dni": "1", "cargo": "x", "memorando": {"numerado": True}}, liq, comp, decl, p, DIAS[0])
    lista = r.avance({"fecha_inicio": DIAS[0], "fecha_fin": DIAS[-1]}, comp, decl, cs, {"pdf": True, "al_dia": True})
    estados = {s["clave"]: s["estado"] for s in lista["secciones"]}
    assert estados == {"datos": "validado", "comprobantes": "validado", "movilidad": "validado", "documento": "validado"}
    assert lista["validadas"] == 4
    viejo = r.avance({"fecha_inicio": DIAS[0], "fecha_fin": DIAS[-1]}, comp, decl, cs, {"pdf": True, "al_dia": False})
    assert {s["clave"]: s["estado"] for s in viejo["secciones"]}["documento"] == "registrado"
    fotos = r.avance({"fecha_inicio": DIAS[0], "fecha_fin": DIAS[-1]}, [{"id": 2, "numero": "", "importe": 0}], [], [], {"pdf": False})
    assert fotos["secciones"][1]["estado"] == "pendiente" and "foto" in fotos["secciones"][1]["texto"]


def test_documento_lleva_las_casillas_de_fecha():
    from yupay import tex as rendicion_tex

    p = _param()
    v = {"datos": {"fecha_inicio": DIAS[0], "fecha_fin": DIAS[-1], "comprobante_pago_fecha": "2026-08-20"},
         "comisionado": {"nombre": "Nombre Apellido", "dni": "00000000", "cargo": "Asistente"},
         "liquidacion": r.liquidar(DIAS, [], [], p), "comprobantes": [], "declarados": [], "parametros": p}
    meta, _ = rendicion_tex.componer(v)
    assert "\\setmeta{comprobantepagodia}{20}" in meta and "\\setmeta{comprobantepagomes}{08}" in meta
    assert "\\setmeta{comprobantepagoanio}{2026}" in meta and "solicitudefectivodia" not in meta


def test_carpetas_y_nombres_de_la_rendicion():
    """Organización de archivos (2026-10-18): toda comisión tiene una carpeta; los sustentos se nombran
    por fecha y número con la huella del contenido; el PDF sigue la convención de nombres.py."""
    from yupay import api as api

    from yupay import comision as rc

    # La ficha de la semana, como la da «semanas.v1» (fase 10.2b).
    semana = {"id": 2, "carpeta": "2026-09_SR-02_ejemplo"}

    # Fuera de la carpeta de la Semana, por año y comisión (2026-10-18): RENDICIONES_DIR/AAAA/<comisión>/R-NNN_<usuario>.
    assert rc.clave_y_carpeta(semana, {}, 7) == ("sr:2", "2026/2026-09_SR-02_ejemplo")
    assert rc.clave_y_carpeta(None, {"fecha_inicio": "2026-10-05", "lugar": "Lima Metropolitana"}, 7) == (
        "cs:2026-10-05_lima-metropolitana", "2026/2026-10-05_lima-metropolitana")
    assert rc.clave_y_carpeta(None, {"motivo": "Reunión técnica"}, 7) == ("r:7", "sin-fecha/R-007")
    assert api.carpeta_rendicion("2026/2026-09_SR-02_ejemplo", 7, "usuario.uno") == "2026/2026-09_SR-02_ejemplo/R-007_usuario-uno"
    assert api.nombre_sustento("2026-09-24", "FF01", "008795", "abc123", ".jpg") == "20260924_FF01-008795_abc123.jpg"
    assert api.nombre_sustento("", "", "", "abc123", ".pdf") == "foto_abc123.pdf"
    v = {"codigo": "R-007", "semana": None, "datos": {"fecha_inicio": "2026-10-05"}, "comisionado": {"nombre": "Nombre Apéllido"}}
    assert api._nombre_archivo(v) == "RV-CS-20261005_Nombre-Apellido"
    assert api._nombre_archivo({**v, "semana": {"codigo": "SR-02"}}) == "RV-SR-02_Nombre-Apellido"


def test_faltan_de_la_semana():
    from yupay import api as api

    responsables = [{"nombre": "Titular de Ejemplo", "rol": "diputado de la República"},
                    {"nombre": "Persona Uno", "rol": "auxiliar"}, {"nombre": "Pérsona Dos", "rol": "técnico"}]
    faltan = api.faltan_de(responsables, {"persona uno"}, {"persona dos": 9})
    assert faltan == [{"nombre": "Pérsona Dos", "rol": "técnico", "usuario_id": 9}]


# --- Movilidad compartida (2026-10-18) -----------------------------------------------------------------


def _persona(nombre, a, otros=None, tope=32000, tope_dj=9600):
    return {"nombre": nombre, "tope": tope, "tope_dj": tope_dj, "a": {DIAS[i]: v for i, v in enumerate(a)},
            "otros": otros or {}, "dias": DIAS}


def test_movilidad_compartida_toma_el_menor_de_todos():
    """Cifras ficticias: cada uno limita un día distinto; la del día es la que alcanza a los dos."""
    ana = _persona("Ana", [25000, 10000, 0, 0, 27000])        # le faltan 70, 220, 320, 320, 50
    luis = _persona("Luis", [20000, 10000, 24000, 0, 26000])  # le faltan 120, 220, 80, 320, 60
    m = r.movilidad_compartida([ana, luis], DIAS)
    assert [m[d]["monto"] for d in DIAS] == [7000, 9600, 8000, 9600, 5000]
    assert m[DIAS[0]]["texto"] == "S/ 70: Ana ya gastó S/ 250 con comprobante ese día."
    assert m[DIAS[2]]["limita"] == "Luis" and m[DIAS[1]]["motivo"] == "tope" and m[DIAS[1]]["limita"] == ""
    assert m[DIAS[1]]["texto"] == "S/ 96: el tope de declaración jurada del día."
    # Sola, cada persona tendría su propia sugerida; juntas, ninguna pasa su viático.
    for p in (ana, luis):
        for d in DIAS:
            assert p["a"][d] + m[d]["monto"] <= 32000 or p["a"][d] >= 32000
    # Otros gastos sin comprobante de uno descuentan lo del día y se nombran.
    con_otros = r.movilidad_compartida([_persona("Ana", [0] * 5, {DIAS[0]: 1000})], DIAS[:1])
    assert con_otros[DIAS[0]]["monto"] == 8600 and "S/ 10 de otros gastos sin comprobante de Ana" in con_otros[DIAS[0]]["texto"]


def test_elegir_tramos_por_dia_y_plan_de_ajuste():
    t = lambda f, de, a, m: {"fecha": f, "hora": "", "desde": de, "hasta": a, "monto": m}  # noqa: E731
    conjuntos = {3: [t(DIAS[0], "A", "B", 50), t(DIAS[0], "B", "A", 46), t(DIAS[1], "A", "C", 96)],
                 4: [t(DIAS[0], "A", "B", 45), t(DIAS[0], "B", "A", 45), t(DIAS[1], "A", "C", 96)]}
    elegidos, descartes = r.elegir_tramos_por_dia(conjuntos)
    assert sum(x["monto"] for x in elegidos if x["fecha"] == DIAS[0]) == 90       # el menor del día
    assert len(elegidos) == 3 and [d["rendicion_id"] for d in descartes] == [3]   # el día 2 era idéntico
    # A igual total, el escrito a mano gana al repartido parejo aunque sea de una rendición más nueva.
    parejo = {3: [t(DIAS[0], "A", "B", 48), t(DIAS[0], "B", "A", 48)], 4: [t(DIAS[0], "A", "B", 50), t(DIAS[0], "B", "A", 46)]}
    assert [x["monto"] for x in r.elegir_tramos_por_dia(parejo)[0]] == [50, 46]
    dias = [{"fecha": DIAS[0], "compartida": 96, "objetivo": None}, {"fecha": DIAS[1], "compartida": 96, "objetivo": 80}]
    plan = r.plan_ajuste(dias, [{"id": 1, "fecha": DIAS[0], "monto": 45}, {"id": 2, "fecha": DIAS[0], "monto": 45},
                                {"id": 3, "fecha": DIAS[1], "monto": 96}])
    assert plan[0]["antes"] == 90 and plan[0]["despues"] == 96 and plan[0]["cambia"] and plan[0]["montos"] == [(1, 48.0), (2, 48.0)]
    assert plan[1]["despues"] == 80 and plan[1]["montos"] == [(3, 80.0)]
    # Un día que ya suma lo sugerido no se toca (se respeta cómo se repartió a mano).
    igual = r.plan_ajuste([{"fecha": DIAS[0], "compartida": 96, "objetivo": None}],
                          [{"id": 1, "fecha": DIAS[0], "monto": 90}, {"id": 2, "fecha": DIAS[0], "monto": 6}])
    assert igual[0]["cambia"] is False and igual[0]["montos"] == []


def test_recibido_de_donde_sale():
    """El importe recibido varía en cada comisión: rendición → comisión → memorando → supuesto (pendiente)."""
    assert r.parametros_vigentes({}, {}, 5)["recibido_viaticos"]["origen"] == "supuesto"
    p = r.parametros_vigentes({}, {}, 5, memorando={"valor": 1280, "numero": "MEM-0009"})
    assert p["recibido_viaticos"]["valor"] == 1280 and "MEM-0009" in p["recibido_viaticos"]["fuente"]
    p = r.parametros_vigentes({}, {}, 5, comision={"valor": 1500, "por": "Ana"}, memorando={"valor": 1280})
    assert p["recibido_viaticos"]["origen"] == "comision" and "Ana" in p["recibido_viaticos"]["fuente"]
    p = r.parametros_vigentes({}, {"recibido_viaticos": 1600}, 5, comision={"valor": 1500})
    assert p["recibido_viaticos"]["origen"] == "rendicion" and p["recibido_viaticos"]["valor"] == 1600
    assert p["tope_diario"]["norma"] == "D.S. 007-2013-EF" and p["pct_dj"]["simple"]
    assert "10517" in p["tope_diario"]["fuente"] and "10518" in p["plazo_dias_habiles"]["fuente"]
    assert r.importe_de_texto("Solicito viáticos por S/ 1,280.00 para la comisión.") == 128000
    assert r.importe_de_texto("Pasajes por S/ 300.00. Sin más.") is None


def test_dj_solo_para_la_movilidad_y_nombre_corto():
    cs = _controles([], [{"id": 9, "clase": "otro", "fecha": DIAS[0], "monto": 5, "concepto": "Fotocopias"}])
    assert any(c["codigo"] == "dj_solo_movilidad" and c["ref"] == "declarado:9" for c in cs)
    cs = _controles([], [{"id": 4, "clase": "movilidad", "fecha": "2026-01-01", "monto": 5}])
    assert any(c["ref"] == "tramo:4" for c in cs)
    assert r.nombre_corto("", "Ana María Pérez Soto") == "Ana María" and r.nombre_corto("", "Luis Rojas") == "Luis"
    assert r.nombre_corto("Ana", "Ana Pérez") == "Ana"


def test_comprobantes_en_fisico_no_piden_foto():
    comp = [_c(1, DIAS[0], "almuerzo", 20, archivo="")]
    assert "sin_foto" in _codigos(_controles(comp, []))
    cs = _controles(comp, [], en_fisico="si")
    assert "sin_foto" not in _codigos(cs) and "en_fisico" in _codigos(cs)
