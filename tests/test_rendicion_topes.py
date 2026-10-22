"""tests/test_rendicion_topes.py — «Ajustar a lo sugerido» NUNCA pasa los topes (2026-10-18).

Edison: «¿“Sugerido” es aplicable? ¿Altera o sobrepasa los topes?». Se comprueba, con comisiones de dos y
tres personas armadas al azar (semilla fija), que tras aplicar el plan de `rendicion.plan_ajuste`:
- ningún día pasa el tope diario de declaración jurada de NINGÚN comisionado (`dj_ok`);
- ningún día pasa el viático del día de NINGÚN comisionado (`total_ok`, salvo el exceso que ya traía con
  comprobante, que lo asume él y no lo causa la movilidad);
- ninguno pasa el 30 % de lo recibido (`pct_dj_ok`), aunque haya recibido menos que viático × días;
- y que el plan solo cambia los MONTOS de los tramos: los parámetros (topes) y la DJ fijada quedan iguales.
También: el plazo no corre en una rendición presentada, observada o cerrada, y el aviso de dos desayunos.
Pruebas puras (sin base de datos); cifras y nombres FICTICIOS.
Uso: cd backend && .venv/bin/python -m pytest -q tests/test_rendicion_topes.py
"""
import copy
import os
import random

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:y@127.0.0.1/z")
os.environ.setdefault("JWT_SECRET", "prueba")

from yupay.api import explicar_plan, ficha_comparar, limites_dj  # noqa: E402
from yupay import rendicion as r  # noqa: E402

DIAS = ["2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28"]
CONCEPTOS = ["desayuno", "almuerzo", "cena", "otros_alimentacion", "hospedaje"]


class _Tramo:
    def __init__(self, id_, fecha, monto):
        self.id, self.fecha, self.monto = id_, fecha, monto


def _persona_y_liq(nombre, comprobantes, otros, tramos, parametros):
    p = r.parametros_vigentes({}, parametros, len(DIAS))
    decl = [{"clase": "movilidad", "fecha": t.fecha, "monto": t.monto} for t in tramos] + otros
    liq = r.liquidar(DIAS, comprobantes, decl, p)
    base = r.centimos(liq["recibido"]) or r.centimos(liq["asignado"])
    persona = {"nombre": nombre, "tope": r.centimos(liq["tope_diario"]), "tope_dj": r.centimos(liq["tope_dj"]),
               "a": {d["fecha"]: r.centimos(d["subtotal_a"]) for d in liq["dias"]},
               "otros": {d["fecha"]: r.centimos(d["otros_dj"]) for d in liq["dias"]}, "dias": DIAS,
               "tope_total": int(base * float(liq["pct_dj_max"]) / 100), "otros_total": r.centimos(liq["otros_dj"])}
    return persona, liq, p


def _comision_al_azar(azar: random.Random, n: int):
    gente = []
    for i in range(n):
        comp = []
        for d in DIAS:
            for c in CONCEPTOS:
                if azar.random() < 0.6:
                    comp.append({"fecha": d, "concepto": c, "importe": round(azar.uniform(5, 140 if c == "hospedaje" else 60), 2)})
        otros = [{"clase": "otro", "fecha": azar.choice(DIAS), "monto": azar.choice([0, 5, 12])} for _ in range(azar.randint(0, 2))]
        recibido = azar.choice([None, 1600, 1200, 900, 500, 300])
        tope_diario = azar.choice([320, 320, 380])
        gente.append({"nombre": f"Persona {i + 1}", "comprobantes": comp, "otros": otros,
                      "parametros": {"tope_diario": tope_diario, "pct_dj": 30, "tope_dj": None, "recibido_viaticos": recibido,
                                     "recibido_pasajes": 0, "recibido_otros": 0, "plazo_dias_habiles": 10}})
    tramos, tid = [], 1
    for d in DIAS:
        for _ in range(azar.randint(0, 4)):
            tramos.append(_Tramo(tid, d, float(azar.choice([0, 7, 15, 27, 40, 60]))))
            tid += 1
    objetivos = {d: azar.choice([50, 96, 130, 200]) for d in DIAS if azar.random() < 0.3}
    return gente, tramos, objetivos


def _ajustar(gente, tramos, objetivos, fechas=None):
    """Lo que hace `api/rendiciones.py::_ajustar` con la primera persona: su liquidación con la movilidad
    compartida, el plan con los límites del 30 % y los montos aplicados a los tramos."""
    filas = [_persona_y_liq(g["nombre"], g["comprobantes"], g["otros"], tramos, g["parametros"]) for g in gente]
    personas = [f[0] for f in filas]
    liq = r.liquidar(DIAS, gente[0]["comprobantes"],
                     [{"clase": "movilidad", "fecha": t.fecha, "monto": t.monto} for t in tramos] + gente[0]["otros"],
                     filas[0][2], objetivos)
    compartida = r.movilidad_compartida(personas, DIAS)
    for d in liq["dias"]:
        d["compartida"] = r.soles(compartida[d["fecha"]]["monto"])
    dias = [d for d in liq["dias"] if not fechas or d["fecha"] in fechas]
    limites = limites_dj(personas, {d["fecha"] for d in dias}, tramos, DIAS)
    plan = r.plan_ajuste(dias, [{"id": t.id, "fecha": t.fecha, "monto": t.monto} for t in tramos], limites)
    por_id = {t.id: t for t in tramos}
    for p in plan:
        for tid, monto in p["montos"]:
            por_id[tid].monto = monto
    return plan


def test_ajustar_nunca_pasa_ningun_tope_de_ningun_comisionado():
    azar = random.Random(20261018)
    revisados = 0
    for _ in range(400):
        gente, tramos, objetivos = _comision_al_azar(azar, azar.choice([2, 2, 3]))
        topes_antes = copy.deepcopy([g["parametros"] for g in gente])
        objetivos_antes = dict(objetivos)
        fechas = {azar.choice(DIAS)} if azar.random() < 0.25 else None
        plan = _ajustar(gente, tramos, objetivos, fechas)
        for g in gente:
            _p, liq, _par = _persona_y_liq(g["nombre"], g["comprobantes"], g["otros"], tramos, g["parametros"])
            for d in liq["dias"]:
                if fechas and d["fecha"] not in fechas:
                    continue
                if any(t.fecha == d["fecha"] for t in tramos):
                    assert d["dj_ok"], (g["nombre"], d)
                    # El viático del día: lo que se reconoce no pasa el tope (el exceso con comprobante lo asume él).
                    assert d["total_ok"], (g["nombre"], d)
            if not fechas:
                assert liq["pct_dj_ok"], (g["nombre"], liq["pct_dj"], liq["recibido"])
        # Solo cambian los montos de los tramos: ni los topes ni la DJ fijada.
        assert [g["parametros"] for g in gente] == topes_antes
        assert objetivos == objetivos_antes
        assert all(set(p) >= {"fecha", "antes", "despues", "cambia", "montos", "motivo"} for p in plan)
        revisados += 1
    assert revisados == 400


def test_la_dj_fijada_rige_si_es_menor_y_no_pasa_lo_que_alcanza():
    dias = [{"fecha": DIAS[0], "compartida": 90.0, "objetivo": 60.0}, {"fecha": DIAS[1], "compartida": 90.0, "objetivo": 120.0},
            {"fecha": DIAS[2], "compartida": 96.0, "objetivo": None}]
    tramos = [{"id": i + 1, "fecha": d, "monto": 10} for i, d in enumerate(DIAS[:3])]
    plan = {p["fecha"]: p for p in r.plan_ajuste(dias, tramos)}
    assert plan[DIAS[0]]["despues"] == 60.0 and plan[DIAS[0]]["motivo"] == "fijada"
    assert plan[DIAS[1]]["despues"] == 90.0 and plan[DIAS[1]]["motivo"] == "fijada_tope"
    assert plan[DIAS[2]]["despues"] == 96.0 and plan[DIAS[2]]["motivo"] == ""
    assert "pasa lo que alcanza" in explicar_plan(plan[DIAS[1]], "", 120.0)


def test_el_30_por_ciento_de_lo_recibido_recorta_el_dia_mas_alto():
    # Recibió S/ 600: el 30 % son S/ 180, aunque cada día alcanzaría S/ 96 (5 días = S/ 480).
    dias = [{"fecha": d, "compartida": 96.0, "objetivo": None} for d in DIAS]
    tramos = [{"id": i + 1, "fecha": d, "monto": 0} for i, d in enumerate(DIAS)]
    limites = [{"nombre": "Ana", "dias": DIAS, "disponible": 18000}, {"nombre": "Luis", "dias": DIAS, "disponible": 40000}]
    plan = r.plan_ajuste(dias, tramos, limites)
    assert sum(r.centimos(p["despues"]) for p in plan) == 18000
    assert all(r.centimos(p["despues"]) <= 9600 for p in plan)
    recortados = [p for p in plan if p["motivo"] == "pct"]
    assert recortados and recortados[0]["recorte"]["nombre"] == "Ana"
    assert "30 %" in explicar_plan(recortados[0], "", None)
    # Parejo: entre el día más alto y el más bajo no hay más de S/ 1.
    montos = [r.centimos(p["despues"]) for p in plan]
    assert max(montos) - min(montos) <= 100


def test_limites_descuentan_otros_gastos_y_dias_que_no_se_tocan():
    personas = [{"nombre": "Ana", "dias": DIAS, "tope_total": 48000, "otros_total": 1000}]
    tramos = [_Tramo(1, DIAS[0], 50), _Tramo(2, DIAS[1], 40)]
    lim = limites_dj(personas, {DIAS[1]}, tramos, DIAS)
    assert lim == [{"nombre": "Ana", "dias": sorted(DIAS), "disponible": 48000 - 1000 - 5000}]


def test_el_plazo_no_corre_en_presentada_observada_ni_cerrada():
    assert r.corre_plazo("borrador") and r.corre_plazo("lista")
    assert not any(r.corre_plazo(e) for e in ("presentada", "observada", "cerrada"))
    p = r.parametros_vigentes({}, {}, 1)
    liq = r.liquidar(DIAS[:1], [], [], p)
    base = {"fecha_inicio": DIAS[0], "fecha_fin": DIAS[0], "dni": "1", "cargo": "x", "memorando": {"numerado": True}}
    for estado in ("presentada", "observada", "cerrada"):
        cs = r.controles({**base, "estado": estado}, liq, [], [], p, "2026-12-01", "2026-09-11")
        assert not any(c["codigo"] == "plazo" for c in cs), estado
    cs = r.controles({**base, "estado": "borrador"}, liq, [], [], p, "2026-12-01", "2026-09-11")
    assert any(c["codigo"] == "plazo" and "vencido" in c["texto"] for c in cs)


def test_dos_desayunos_el_mismo_dia_se_avisan_y_dos_hospedajes_no():
    def c(i, concepto, numero):
        return {"id": i, "fecha": DIAS[0], "concepto": concepto, "importe": 10, "tipo": "boleta_electronica",
                "serie": "EB01", "numero": numero, "ruc": "20000000001", "archivo": "x.jpg"}
    comp = [c(1, "desayuno", "1"), c(2, "desayuno", "2"), c(3, "hospedaje", "3"), c(4, "hospedaje", "4")]
    p = r.parametros_vigentes({}, {}, 1)
    liq = r.liquidar(DIAS[:1], comp, [], p)
    cs = r.controles({"fecha_inicio": DIAS[0], "fecha_fin": DIAS[0], "dni": "1", "cargo": "x", "memorando": {}}, liq, comp, [], p, DIAS[0])
    repetidos = [x for x in cs if x["codigo"] == "concepto_repetido"]
    assert [x["ref"] for x in repetidos] == ["comprobante:2"]
    assert repetidos[0]["nivel"] == "aviso" and "desayuno" in repetidos[0]["texto"]


def test_ficha_para_comparar_cuenta_comprobantes_por_dia_y_concepto():
    p = r.parametros_vigentes({}, {}, len(DIAS))
    comp = [{"id": 1, "fecha": DIAS[0], "concepto": "almuerzo", "importe": 20}, {"id": 2, "fecha": DIAS[0], "concepto": "almuerzo", "importe": 5}]
    liq = r.liquidar(DIAS, comp, [], p)
    v = {"id": 3, "codigo": "R-003", "estado": "borrador", "etiqueta_estado": "Borrador", "errores": 0, "comprobantes": comp,
         "comisionado": {"corto": "Ana", "nombre": "Ana Pérez"}, "liquidacion": liq}
    f = ficha_comparar(v, True)
    assert f["dias"][0]["cuantos"] == {"almuerzo": 2} and f["dias"][0]["por_concepto"]["almuerzo"] == 25.0
    assert f["totales"]["comprobantes"] == 2 and f["propia"] is True


