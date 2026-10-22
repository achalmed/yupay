"""Rendición de cuentas de viáticos (2026-10-18, pedido de Edison: «que nos ayude a hacer el informe de
rendición de cuenta de manera más rápida, que nos solucione todo tipo de cosas que se puedan presentar,
que todo sea automático»). La parte PURA: el cálculo de la liquidación, los controles, la movilidad
sugerida, el reparto de los tramos y el importe en letras. Sin base de datos ni archivos; la usan
`api/rendiciones.py`, el documento LaTeX (`servicios/rendicion_tex.py`) y la exportación a Excel
(`servicios/rendicion_excel.py`). Pruebas en `tests/test_rendicion.py`.

El cálculo replica, fórmula por fórmula, el libro de liquidación con que el despacho rindió la primera
semana de representación (hoja «Rendición», un día por columna; `docs/arquitectura.md` §32):

    A  gastos con comprobante (desayuno, almuerzo, cena, otros de alimentación, hospedaje) → subtotal
    B  gastos con declaración jurada (movilidad y otros sin comprobante)                 → subtotal
    C  asignado = tope diario; reconocido = MIN(A, tope) + B; exceso = MAX(0, A − tope);
       saldo = asignado − reconocido
    D  controles: B ≤ tope DJ; reconocido ≤ tope (+0,001); exceso = 0  → «CONFORME» / «REVISAR»

y la regla de la movilidad declarada: el menor entre el tope DJ y lo que falte para completar el viático
del día, para que la devolución sea la mínima. Todo se suma en CÉNTIMOS (enteros): S/ 0,10 + S/ 0,20
nunca da 0,30000000000000004.

Los pasajes terrestres y los otros recursos (Formato 03-VN, secciones B y C) no son viático: se rinden
documentados al 100 % contra su propio importe recibido.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta

# --- Vocabularios -------------------------------------------------------------------------------------

#: concepto → (sección del Formato 03-VN, rótulo, rótulo del Anexo 4)
CONCEPTOS: dict[str, tuple[str, str, str]] = {
    "desayuno": ("A", "Desayuno", "ALIMENTACIÓN"),
    "almuerzo": ("A", "Almuerzo", "ALIMENTACIÓN"),
    "cena": ("A", "Cena", "ALIMENTACIÓN"),
    "otros_alimentacion": ("A", "Otros de alimentación", "ALIMENTACIÓN"),
    "hospedaje": ("A", "Hospedaje", "HOSPEDAJE"),
    "pasaje_terrestre": ("B", "Pasaje terrestre", "PASAJE TERRESTRE"),
    "otro_recurso": ("C", "Otro recurso", "OTROS RECURSOS"),
}
CONCEPTOS_A = [c for c, (s, *_r) in CONCEPTOS.items() if s == "A"]
#: lo que va UNA vez por día (2026-10-18); el hospedaje y «otros de alimentación» pueden ser más de uno
UNO_POR_DIA = ("desayuno", "almuerzo", "cena")

#: tipo de comprobante → rótulo con que lo imprime el Anexo 4
TIPOS_COMPROBANTE: dict[str, str] = {
    "boleta_electronica": "Boleta de venta electrónica",
    "boleta": "Boleta de venta",
    "factura_electronica": "Factura electrónica",
    "factura": "Factura",
    "ticket": "Ticket",
    "recibo": "Recibo",
    "otro": "Comprobante",
}
#: lo que sustenta la sección A: comprobantes de pago de la SUNAT —«facturas, boletas de venta y ticket»
#: (DI 37-2025-DF-DGA-CR, Anexo N.° 05, a), 2026-10-18)—; el recibo u otro papel no es comprobante.
TIPOS_SUSTENTO_A = {"boleta_electronica", "boleta", "factura_electronica", "factura", "ticket"}

ESTADOS = ("borrador", "lista", "presentada", "observada", "cerrada")
ETIQUETA_ESTADO = {"borrador": "Borrador", "lista": "Lista", "presentada": "Presentada",
                   "observada": "Observada", "cerrada": "Cerrada"}

#: Los parámetros de FÁBRICA, con su procedencia. Viven en el ajuste `rendicion_parametros` (los cambia
#: Administración) y cada rendición puede ajustar los suyos. Procedencia (`docs/arquitectura.md` §32), en
#: la biblioteca desde el 2026-10-18: D.S. N.° 007-2013-EF (calibre 10517), Directiva DI 37-2025-DF-DGA-CR
#: del Congreso, «Otorgamiento de pasajes, viáticos y otros recursos en el territorio nacional y la
#: rendición de cuenta» (calibre 10518), y Acuerdo N.° 226-2012-2013/MESA-CR (calibre 10519). La Directiva
#: N.° 08-2022-DGA/CR (calibre 10092) trata el apoyo logístico del CONGRESISTA, que no se rinde.
FABRICA: dict[str, dict] = {
    # `norma`: la cita corta que se muestra al lado del valor; `simple`: lo que significa, en una línea
    # (2026-10-18, Edison: «parámetros más fáciles de entender»). `fuente`: la procedencia completa.
    "tope_diario": {"valor": 320.0, "etiqueta": "Viático por día", "norma": "D.S. 007-2013-EF",
                    "simple": "Lo máximo que se reconoce por cada día de comisión.",
                    "fuente": "D.S. N.° 007-2013-EF, art. 1 (calibre 10517): S/ 320 por día; el Acuerdo N.° 226-2012-2013/MESA-CR "
                              "(calibre 10519) fija S/ 380 solo para el Oficial Mayor. Una comisión de más de 4 h y hasta 24 h cuenta "
                              "como un día; si dura menos, se paga en proporción"},
    "pct_dj": {"valor": 30.0, "etiqueta": "Declaración jurada", "norma": "DI 37-2025-DF-DGA-CR",
               "simple": "Lo que se sustenta sin comprobante (la movilidad): hasta este porcentaje de lo recibido.",
               "fuente": "DI 37-2025-DF-DGA-CR (calibre 10518), 7.9.1.1.1-2, y D.S. N.° 007-2013-EF (calibre 10517), art. 3: "
                         "comprobantes por al menos el 70 % y declaración jurada por no más del 30 %, solo para la movilidad"},
    "tope_dj": {"valor": None, "etiqueta": "Declaración jurada por día", "norma": "práctica de la entidad",
                "simple": "Viático por día × porcentaje de declaración jurada: lo máximo de movilidad en un día.",
                "fuente": "Práctica de la entidad (libro de la SR-01): viático por día × % de declaración jurada; la directiva limita el 30 % del total"},
    "plazo_dias_habiles": {"valor": 10, "etiqueta": "Plazo para rendir", "norma": "DI 37-2025-DF-DGA-CR",
                           "simple": "Días hábiles contados desde el último día de la comisión.",
                           "fuente": "DI 37-2025-DF-DGA-CR (calibre 10518), 6.6.2.2 y 7.9.6.4.2 b): diez días hábiles desde el término "
                                     "de la comisión para funcionarios y servidores (15 para congresistas, 6.6.2.1); si vence en día inhábil, "
                                     "el hábil siguiente (D.S. N.° 007-2013-EF, art. 3)"},
    "recibido_viaticos": {"valor": None, "etiqueta": "Importe recibido", "norma": "memorando o comprobante de pago",
                          "simple": "Lo que se depositó de viáticos para esta comisión; con él se calcula el saldo a devolver.",
                          "fuente": "No consta: se supone viático por día × días de la comisión"},
    "recibido_pasajes": {"valor": 0.0, "etiqueta": "Recibido para pasajes terrestres", "norma": "comprobante de pago",
                         "simple": "Solo si además le dieron dinero para pasajes terrestres.", "fuente": "Del comprobante de pago"},
    "recibido_otros": {"valor": 0.0, "etiqueta": "Recibido para otros recursos", "norma": "comprobante de pago",
                       "simple": "Solo si además le dieron dinero para otros recursos.", "fuente": "Del comprobante de pago"},
}
CLAVES_PARAMETROS = tuple(FABRICA)


# --- Dinero -------------------------------------------------------------------------------------------


def centimos(valor) -> int:
    """S/ como número o texto («S/ 2,345.60», «40», 12.5) → céntimos. Lo ilegible es 0."""
    if valor is None or valor == "":
        return 0
    if isinstance(valor, bool):
        return 0
    if isinstance(valor, int):
        return valor * 100
    if isinstance(valor, float):
        return int(round(valor * 100))
    s = re.sub(r"[^\d,.\-]", "", str(valor))
    if not s or s in "-.,":
        return 0
    # «2,345.60» y «2.345,60»: el último separador es el decimal si lo siguen 1 o 2 cifras.
    m = re.match(r"^(-?)([\d.,]*?)(?:[.,](\d{1,2}))?$", s)
    if not m:
        return 0
    signo, entero, dec = m.group(1), re.sub(r"[.,]", "", m.group(2) or "0"), (m.group(3) or "0")
    total = int(entero or "0") * 100 + int(dec.ljust(2, "0"))
    return -total if signo else total


def soles(c: int) -> float:
    return round(c / 100, 2)


def texto_soles(c: int, prefijo: str = "S/ ") -> str:
    """12345 → «S/ 123.45»; con miles «S/ 2,345.60» (la forma de los formatos del Congreso)."""
    signo = "-" if c < 0 else ""
    c = abs(c)
    return f"{signo}{prefijo}{c // 100:,}.{c % 100:02d}"


# --- Fechas -------------------------------------------------------------------------------------------

MESES = ("", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre")


def dias_de(inicio: str, fin: str) -> list[str]:
    """Los días ISO de [inicio, fin]; vacío si faltan o están al revés (como mucho 60)."""
    try:
        a, b = date.fromisoformat(str(inicio)[:10]), date.fromisoformat(str(fin)[:10])
    except ValueError:
        return []
    if b < a:
        return []
    return [(a + timedelta(days=i)).isoformat() for i in range(min((b - a).days + 1, 60))]


def fecha_larga(iso: str) -> str:
    try:
        d = date.fromisoformat(str(iso)[:10])
    except ValueError:
        return ""
    return f"{d.day} de {MESES[d.month]} de {d.year}"


def fecha_corta(iso: str) -> str:
    """AAAA-MM-DD → DD/MM/AAAA (la forma de las tablas de los formatos)."""
    try:
        d = date.fromisoformat(str(iso)[:10])
    except ValueError:
        return str(iso or "")
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


def hora_12(hhmm: str) -> str:
    """«15:00» → «3:00 p. m.» (como el formato de referencia); lo que no es hora, tal cual."""
    m = re.match(r"^(\d{1,2}):(\d{2})", str(hhmm or ""))
    if not m:
        return str(hhmm or "")
    h, mi = int(m.group(1)), m.group(2)
    sufijo = "a. m." if h < 12 else "p. m."
    return f"{(h % 12) or 12}:{mi} {sufijo}"


# --- Importe en letras --------------------------------------------------------------------------------

_UNIDADES = ("cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez",
             "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho",
             "diecinueve", "veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco",
             "veintiséis", "veintisiete", "veintiocho", "veintinueve")
_DECENAS = ("", "", "", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa")
_CENTENAS = ("", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos",
             "setecientos", "ochocientos", "novecientos")


def _menor_mil(n: int) -> str:
    if n == 100:
        return "cien"
    c, r = divmod(n, 100)
    partes = [_CENTENAS[c]] if c else []
    if r:
        if r < 30:
            partes.append(_UNIDADES[r])
        else:
            d, u = divmod(r, 10)
            partes.append(_DECENAS[d] + (f" y {_UNIDADES[u]}" if u else ""))
    return " ".join(partes)


def _apocopar(texto: str) -> str:
    """«uno» ante un sustantivo («mil», «millones»): «veintiuno mil» → «veintiún mil»."""
    if texto.endswith("veintiuno"):
        return texto[:-9] + "veintiún"
    if texto.endswith("uno"):
        return texto[:-3] + "un"
    return texto


def numero_en_letras(n: int) -> str:
    """Entero no negativo en palabras, en minúsculas (RAE: «veinticuatro», «doscientos un mil»)."""
    if n < 0:
        return "menos " + numero_en_letras(-n)
    if n < 1000:
        return _UNIDADES[n] if n < 30 else _menor_mil(n)
    millones, resto = divmod(n, 1_000_000)
    partes = []
    if millones:
        partes.append("un millón" if millones == 1 else f"{_apocopar(numero_en_letras(millones))} millones")
    miles, unidades = divmod(resto, 1000)
    if miles:
        partes.append("mil" if miles == 1 else f"{_apocopar(_menor_mil(miles))} mil")
    if unidades:
        partes.append(_menor_mil(unidades))
    return " ".join(partes)


def importe_en_letras(c: int) -> str:
    """43700 → «Cuatrocientos treinta y siete con 00/100 soles» (la frase de la declaración jurada)."""
    c = abs(int(c))
    texto = numero_en_letras(c // 100)
    return f"{texto[:1].upper()}{texto[1:]} con {c % 100:02d}/100 soles"


def dias_en_letras(n: int) -> str:
    """5 → «CINCO (05)» (los días de duración del Formato 03-VN)."""
    return f"{numero_en_letras(n).upper()} ({n:02d})"


# --- Parámetros vigentes ------------------------------------------------------------------------------


def _num(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def parametros_vigentes(ajuste: dict | None, propios: dict | None, dias: int,
                        comision: dict | None = None, memorando: dict | None = None) -> dict:
    """Los parámetros que RIGEN una rendición y de dónde sale cada uno: los de la rendición si los
    ajustó, si no los de la entidad (ajuste `rendicion_parametros`), si no los de fábrica. Devuelve
    {clave: {valor, etiqueta, norma, simple, fuente, origen}} con `tope_dj` y `recibido_viaticos` ya resueltos.

    El IMPORTE RECIBIDO varía en cada comisión (2026-10-18, Edison: «no lo supongas igual»): manda el de
    la rendición; si no, el registrado para toda la comisión (`comision` = {valor, por}); si no, el que
    dice el memorando (`memorando` = {valor, numero}); si no, el de la entidad; y si nada consta, se SUPONE
    viático × días (origen `supuesto`) y queda como pendiente."""
    ajuste, propios = ajuste or {}, propios or {}
    salida: dict[str, dict] = {}
    for clave, f in FABRICA.items():
        valor, origen, fuente = f["valor"], "fabrica", f["fuente"]
        a = ajuste.get(clave)
        if isinstance(a, dict) and _num(a.get("valor")) is not None:
            valor, origen, fuente = _num(a["valor"]), "despacho", str(a.get("fuente") or "Ajuste de la entidad")
        elif _num(a) is not None:
            valor, origen, fuente = _num(a), "despacho", "Ajuste de la entidad (Administración)"
        if _num(propios.get(clave)) is not None:
            valor, origen, fuente = _num(propios[clave]), "rendicion", "Anotado en esta rendición"
        salida[clave] = {"valor": valor, "etiqueta": f["etiqueta"], "norma": f.get("norma", ""), "simple": f.get("simple", ""),
                         "fuente": fuente, "origen": origen}
    tope = centimos(salida["tope_diario"]["valor"])
    if salida["tope_dj"]["valor"] is None:
        salida["tope_dj"]["valor"] = soles(int(round(tope * float(salida["pct_dj"]["valor"] or 0) / 100)))
    rec = salida["recibido_viaticos"]
    if rec["origen"] != "rendicion":
        if comision and _num(comision.get("valor")) is not None:
            quien = str(comision.get("por") or "").strip()
            rec.update(valor=_num(comision["valor"]), origen="comision",
                       fuente=f"Anotado para toda la comisión{f' por {quien}' if quien else ''}")
        elif memorando and _num(memorando.get("valor")) is not None:
            rec.update(valor=_num(memorando["valor"]), origen="memorando",
                       fuente=f"Del memorando {memorando.get('numero') or ''}".strip())
    if rec["valor"] is None:
        rec.update(valor=soles(tope * max(dias, 0)), origen="supuesto")
    if salida["plazo_dias_habiles"]["valor"] is not None:
        salida["plazo_dias_habiles"]["valor"] = int(salida["plazo_dias_habiles"]["valor"])
    return salida


def importe_de_texto(texto: str) -> int | None:
    """El importe de viáticos que dice un texto (el cuerpo de un memorando), en céntimos: la primera cifra
    «S/ 1,600.00» de una oración que habla de viáticos. None si no lo dice. Pura."""
    for oracion in re.split(r"(?<=[.;\n])\s+", str(texto or "")):
        if "viatic" not in _plano(oracion):
            continue
        m = re.search(r"S/\.?\s*(\d[\d.,]*\d|\d)", oracion)
        if m:
            c = centimos(m.group(1))
            if c > 0:
                return c
    return None


# --- Liquidación --------------------------------------------------------------------------------------


@dataclass
class Dia:
    fecha: str
    por_concepto: dict[str, int] = field(default_factory=dict)  # céntimos por concepto de la sección A
    subtotal_a: int = 0
    movilidad: int = 0          # tramos del día
    otros_dj: int = 0           # otros gastos sin comprobante del día
    dj: int = 0                 # sección B: movilidad + otros
    asignado: int = 0
    reconocido: int = 0
    exceso: int = 0
    saldo: int = 0
    sugerida: int = 0           # movilidad sugerida: el menor entre el tope DJ y lo que falta
    objetivo: int | None = None  # la DJ del día fijada por la persona (los tramos deben sumarla)
    dj_ok: bool = True
    total_ok: bool = True
    sin_exceso: bool = True

    def como_dict(self) -> dict:
        return {
            "fecha": self.fecha, "por_concepto": {k: soles(v) for k, v in self.por_concepto.items()},
            "subtotal_a": soles(self.subtotal_a), "movilidad": soles(self.movilidad), "otros_dj": soles(self.otros_dj),
            "dj": soles(self.dj), "asignado": soles(self.asignado), "reconocido": soles(self.reconocido),
            "exceso": soles(self.exceso), "saldo": soles(self.saldo), "sugerida": soles(self.sugerida),
            "objetivo": None if self.objetivo is None else soles(self.objetivo),
            "dj_ok": self.dj_ok, "total_ok": self.total_ok, "sin_exceso": self.sin_exceso,
        }


def sugerida(subtotal_a: int, tope: int, tope_dj: int, otros_dj: int = 0) -> int:
    """La movilidad que conviene declarar (céntimos): el menor entre el tope DJ y lo que falta para
    completar el viático del día, descontando lo ya declarado sin comprobante. Nunca negativa."""
    falta = tope - min(subtotal_a, tope)
    return max(0, min(tope_dj, falta) - otros_dj)


def texto_corto(c: int) -> str:
    """12000 → «S/ 120»; 8250 → «S/ 82.50» (los montos de las líneas breves)."""
    return f"S/ {c // 100:,}" if c % 100 == 0 else texto_soles(c)


def nombre_corto(nombres: str, completo: str) -> str:
    """Cómo se nombra a una persona en una línea breve: sus nombres de pila (o, sin ellos, los dos primeros
    de un nombre de cuatro palabras, o el primero)."""
    n = str(nombres or "").strip()
    if n:
        return n
    p = str(completo or "").split()
    return " ".join(p[:2]) if len(p) >= 4 else (p[0] if p else "")


def movilidad_compartida(personas: list[dict], dias: list[str]) -> dict[str, dict]:
    """La movilidad del día que alcanza a TODOS los de una comisión (2026-10-18, Edison: «la movilidad debe
    ser igual para ambos, así que el monto del día no siempre llega a 96: unos consumen más con comprobante
    y otros menos»). Para cada comisionado, el menor entre su tope de declaración jurada del día y lo que le
    falta para completar su viático (descontados sus otros gastos sin comprobante); la del día es el MENOR
    de esos montos. Así nadie pasa su viático y la devolución es la mínima posible para todos.

    `personas`: [{nombre, tope, tope_dj, a: {fecha: céntimos con comprobante}, otros: {fecha: céntimos},
    dias: [fechas] | None}], todo en céntimos. Devuelve {fecha: {monto, limita, motivo: tope|viatico,
    texto, por_persona: [{nombre, gastado, otros, puede}]}}; el `texto` es la línea que explica el monto
    («S/ 90: Ana ya gastó S/ 230 con comprobante ese día»). Pura."""
    salida: dict[str, dict] = {}
    for d in dias:
        filas = []
        for p in personas:
            if p.get("dias") and d not in p["dias"]:
                continue
            a, o = int((p.get("a") or {}).get(d, 0)), int((p.get("otros") or {}).get(d, 0))
            tope, tope_dj = int(p.get("tope") or 0), int(p.get("tope_dj") or 0)
            filas.append({"nombre": str(p.get("nombre") or ""), "gastado": a, "otros": o, "tope": tope,
                          "tope_dj": tope_dj, "puede": sugerida(a, tope, tope_dj, o)})
        if not filas:
            continue
        lim = min(filas, key=lambda f: f["puede"])
        falta = lim["tope"] - min(lim["gastado"], lim["tope"])
        motivo = "tope" if falta >= lim["tope_dj"] else "viatico"
        if motivo == "tope" and lim["otros"]:
            texto = (f"{texto_corto(lim['puede'])}: el tope de declaración jurada del día, menos {texto_corto(lim['otros'])} "
                     f"de otros gastos sin comprobante de {lim['nombre'] or 'el comisionado'}.")
        elif motivo == "tope":
            texto = f"{texto_corto(lim['puede'])}: el tope de declaración jurada del día."
        else:
            extra = f" y {texto_corto(lim['otros'])} sin comprobante" if lim["otros"] else ""
            texto = f"{texto_corto(lim['puede'])}: {lim['nombre'] or 'el comisionado'} ya gastó {texto_corto(lim['gastado'])} con comprobante{extra} ese día."
        salida[d] = {"monto": lim["puede"], "limita": lim["nombre"] if motivo == "viatico" or lim["otros"] else "", "motivo": motivo, "texto": texto,
                     "por_persona": [{k: f[k] for k in ("nombre", "gastado", "otros", "puede")} for f in filas]}
    return salida


def elegir_tramos_por_dia(conjuntos: dict[int, list[dict]]) -> tuple[list[dict], list[dict]]:
    """La migración a la movilidad compartida (2026-10-18): cada rendición de una comisión tenía SUS tramos.
    Día por día queda el juego de la rendición que declaró MENOS ese día (a igual monto, el escrito a mano
    antes que el que «Ajustar» repartió parejo, y luego la de menor id):
    lo que alcanza a todos. `conjuntos`: {rendicion_id: [tramos {fecha, hora, desde, hasta, monto…}]}.
    Devuelve (elegidos, descartes), con descartes = [{rendicion_id, fecha, total, tramos}] de los juegos
    DISTINTOS al elegido (los idénticos no son descarte). Pura."""
    def firma(ts: list[dict]) -> list[tuple]:
        return sorted((t.get("hora") or "", t.get("desde") or "", t.get("hasta") or "", centimos(t.get("monto"))) for t in ts)

    por_dia: dict[str, dict[int, list[dict]]] = {}
    for rid, ts in conjuntos.items():
        for t in ts:
            por_dia.setdefault(str(t.get("fecha") or ""), {}).setdefault(rid, []).append(t)
    elegidos, descartes = [], []
    for fecha in sorted(por_dia):
        juegos = por_dia[fecha]
        # A igual total, el juego escrito a mano (montos distintos) antes que uno repartido parejo por
        # «Ajustar» (el ensayo del 2026-10-18 tenía los dos), y después la rendición más antigua.
        def parejo(ts: list[dict]) -> bool:
            montos = [centimos(t.get("monto")) for t in ts]
            return sorted(montos) == sorted(repartir(sum(montos), len(montos)))

        rid = min(juegos, key=lambda k: (sum(centimos(t.get("monto")) for t in juegos[k]), parejo(juegos[k]), k))
        elegidos.extend(juegos[rid])
        for otro, ts in juegos.items():
            if otro != rid and firma(ts) != firma(juegos[rid]):
                descartes.append({"rendicion_id": otro, "fecha": fecha, "total": soles(sum(centimos(t.get("monto")) for t in ts)),
                                  "elegido": rid, "tramos": ts})
    return elegidos, descartes


def recortar_a_limites(metas: dict[str, int], limites: list[dict]) -> dict[str, dict]:
    """El 30 % de lo recibido de CADA comisionado (2026-10-18, Edison: «nunca debe sobrepasar el 30 % de lo
    recibido de cada uno»). `metas`: {fecha: céntimos} que se pondrían; `limites`: [{nombre, dias: [fechas] |
    None, disponible: céntimos}] —lo que a cada uno le queda para movilidad en esos días: 30 % de lo recibido,
    menos sus otros gastos sin comprobante y la movilidad de los días que no se tocan—. Si a alguien no le
    alcanza, se baja de a S/ 1 el día más alto de los suyos (el más reciente a igualdad) hasta que alcance.
    Cambia `metas` en su lugar y devuelve {fecha: {nombre, disponible}} de los días recortados. Pura."""
    recortes: dict[str, dict] = {}
    cambio = True
    while cambio:
        cambio = False
        for lim in limites:
            suyos = [f for f in metas if not lim.get("dias") or f in lim["dias"]]
            exceso = sum(metas[f] for f in suyos) - max(0, int(lim.get("disponible") or 0))
            while exceso > 0:
                vivos = [f for f in suyos if metas[f] > 0]
                if not vivos:
                    break
                f = max(vivos, key=lambda x: (metas[x], x))
                corte = min(exceso, metas[f], 100)
                metas[f] -= corte
                exceso -= corte
                recortes[f] = {"nombre": str(lim.get("nombre") or ""), "disponible": max(0, int(lim.get("disponible") or 0))}
                cambio = True
    return recortes


def plan_ajuste(dias: list[dict], tramos: list[dict], limites: list[dict] | None = None) -> list[dict]:
    """Lo que hará «Ajustar a lo sugerido», día por día, antes de hacerlo (2026-10-18, Edison lo tocó y no
    entendió qué hacía): la meta del día repartida en soles enteros entre sus tramos; un día que ya suma su
    meta queda como está. Solo cambia los MONTOS de los tramos: nunca los topes ni la DJ fijada.

    La meta NUNCA pasa los topes (2026-10-18, Edison: «¿altera o sobrepasa los topes?»): es la movilidad que
    alcanza a todos (`compartida`: el tope de declaración jurada del día y el viático del día de CADA
    comisionado); la DJ fijada a mano rige si es menor, y si es mayor se queda en lo que alcanza; y en total
    no pasa el 30 % de lo recibido de cada uno (`limites`, `recortar_a_limites`).

    `dias`: los de la liquidación (con `compartida` y `objetivo`); `tramos`: [{id, fecha, monto}] ordenados.
    Devuelve [{fecha, antes, despues, cambia, montos: [(id, monto)], motivo: ''|'fijada'|'fijada_tope'|'pct',
    recorte?}] de los días con tramos. Pura."""
    metas: dict[str, int] = {}
    motivos: dict[str, str] = {}
    del_dia: dict[str, list[dict]] = {}
    for d in dias:
        ts = [t for t in tramos if t.get("fecha") == d["fecha"]]
        if not ts:
            continue
        del_dia[d["fecha"]] = ts
        alcanza = centimos(d.get("compartida", d.get("sugerida")))
        objetivo = d.get("objetivo")
        if objetivo is None:
            metas[d["fecha"]], motivos[d["fecha"]] = alcanza, ""
        elif centimos(objetivo) <= alcanza:
            metas[d["fecha"]], motivos[d["fecha"]] = centimos(objetivo), "fijada"
        else:
            # La DJ fijada pasa lo que alcanza a todos: se queda en lo que alcanza.
            metas[d["fecha"]], motivos[d["fecha"]] = alcanza, "fijada_tope"
    recortes = recortar_a_limites(metas, limites or [])
    salida = []
    for fecha, ts in del_dia.items():
        meta_c = metas[fecha]
        antes = sum(centimos(t.get("monto")) for t in ts)
        # Un día que ya suma la meta no se toca: se respeta cómo la persona repartió sus tramos.
        cambia = antes != meta_c
        montos = repartir(meta_c, len(ts)) if cambia else [centimos(t.get("monto")) for t in ts]
        fila = {"fecha": fecha, "antes": soles(antes), "despues": soles(meta_c), "cambia": cambia,
                "montos": [(t.get("id"), soles(m)) for t, m in zip(ts, montos)] if cambia else [],
                "motivo": "pct" if fecha in recortes else motivos[fecha]}
        if fecha in recortes:
            fila["recorte"] = {"nombre": recortes[fecha]["nombre"], "disponible": soles(recortes[fecha]["disponible"])}
        salida.append(fila)
    return salida


def liquidar(dias: list[str], comprobantes: list[dict], declarados: list[dict], parametros: dict,
             objetivos: dict | None = None) -> dict:
    """La liquidación completa. `comprobantes`: [{fecha, concepto, importe}], `declarados`:
    [{clase: movilidad|otro, fecha, monto}], `parametros`: los de `parametros_vigentes` (o
    {clave: valor}), `objetivos`: {fecha: monto} de la DJ del día fijada a mano. Lo que cae fuera de
    los días de la comisión no entra en el cálculo (lo avisan los controles)."""
    val = {k: (v["valor"] if isinstance(v, dict) else v) for k, v in parametros.items()}
    tope, tope_dj = centimos(val.get("tope_diario")), centimos(val.get("tope_dj"))
    if not tope_dj:
        tope_dj = int(round(tope * float(val.get("pct_dj") or 0) / 100))
    pct_max = float(val.get("pct_dj") or 0) / 100
    objetivos = objetivos or {}
    por_dia = {d: Dia(fecha=d, por_concepto={c: 0 for c in CONCEPTOS_A}, asignado=tope) for d in dias}
    seccion = {"B": [], "C": []}
    for c in comprobantes:
        concepto = str(c.get("concepto") or "")
        s = CONCEPTOS.get(concepto, ("?",))[0]
        if s in ("B", "C"):
            seccion[s].append(centimos(c.get("importe")))
            continue
        d = por_dia.get(str(c.get("fecha") or "")[:10])
        if d is not None and s == "A":
            d.por_concepto[concepto] += centimos(c.get("importe"))
    for x in declarados:
        d = por_dia.get(str(x.get("fecha") or "")[:10])
        if d is None:
            continue
        if (x.get("clase") or "movilidad") == "movilidad":
            d.movilidad += centimos(x.get("monto"))
        else:
            d.otros_dj += centimos(x.get("monto"))
    for d in por_dia.values():
        d.subtotal_a = sum(d.por_concepto.values())
        d.dj = d.movilidad + d.otros_dj
        d.reconocido = min(d.subtotal_a, tope) + d.dj
        d.exceso = max(0, d.subtotal_a - tope)
        d.saldo = d.asignado - d.reconocido
        d.sugerida = sugerida(d.subtotal_a, tope, tope_dj, d.otros_dj)
        obj = objetivos.get(d.fecha)
        d.objetivo = None if obj in (None, "") else centimos(obj)
        d.dj_ok = d.dj <= tope_dj
        d.total_ok = d.reconocido <= tope  # el libro compara con +0,001: en céntimos es exacto
        d.sin_exceso = d.exceso == 0
    filas = list(por_dia.values())
    asignado = sum(d.asignado for d in filas)
    con_comprobante = sum(d.subtotal_a for d in filas)
    dj = sum(d.dj for d in filas)
    reconocido = sum(d.reconocido for d in filas)
    exceso = sum(d.exceso for d in filas)
    recibido = centimos(val.get("recibido_viaticos")) if val.get("recibido_viaticos") not in (None, "") else asignado
    total_pasajes, total_otros = sum(seccion["B"]), sum(seccion["C"])
    recibido_pasajes, recibido_otros = centimos(val.get("recibido_pasajes")), centimos(val.get("recibido_otros"))
    # El 30 % es «del monto otorgado» (DI 37-2025-DF-DGA-CR, 7.9.1.1.1-2): lo recibido; sin dato, lo asignado.
    base_pct = recibido or asignado
    pct = (dj / base_pct) if base_pct else 0.0
    controles_dia = {
        "dj": all(d.dj_ok for d in filas), "total": all(d.total_ok for d in filas),
        "exceso": all(d.sin_exceso for d in filas),
    }
    return {
        "dias": [d.como_dict() for d in filas],
        "por_concepto": {c: soles(sum(d.por_concepto[c] for d in filas)) for c in CONCEPTOS_A},
        "tope_diario": soles(tope), "tope_dj": soles(tope_dj), "pct_dj_max": round(pct_max * 100, 2),
        "asignado": soles(asignado), "recibido": soles(recibido), "con_comprobante": soles(con_comprobante),
        "dj": soles(dj), "movilidad": soles(sum(d.movilidad for d in filas)),
        "otros_dj": soles(sum(d.otros_dj for d in filas)),
        # «Total rendido» de la hoja Resumen = A + B (lo documentado), y el reconocido con el tope.
        "rendido": soles(con_comprobante + dj), "reconocido": soles(reconocido), "exceso": soles(exceso),
        "saldo": soles(recibido - reconocido),
        "saldo_por_dias": soles(sum(d.saldo for d in filas)),
        "pct_dj": round(pct * 100, 2), "pct_dj_ok": pct <= pct_max + 0.000001,
        "conforme": {k: ("CONFORME" if v else "REVISAR") for k, v in controles_dia.items()},
        "pasajes": {"rendido": soles(total_pasajes), "recibido": soles(recibido_pasajes), "saldo": soles(recibido_pasajes - total_pasajes)},
        "otros": {"rendido": soles(total_otros), "recibido": soles(recibido_otros), "saldo": soles(recibido_otros - total_otros)},
        "dj_en_letras": importe_en_letras(dj),
    }


# --- Movilidad: proponer y repartir -------------------------------------------------------------------


def repartir(total: int, n: int, paso: int = 100) -> list[int]:
    """`total` céntimos en `n` montos de múltiplos de `paso` (soles enteros por omisión), lo más
    parejos posible; lo que no cabe en el paso va al último. Suma exacta."""
    if n <= 0:
        return []
    total = max(0, int(total))
    base = (total // n) // paso * paso
    montos = [base] * n
    resto = total - base * n
    i = 0
    while resto >= paso:
        montos[i % n] += paso
        resto -= paso
        i += 1
    montos[-1] += resto
    return montos


def _lugar(a: dict) -> str:
    for k in ("lugar", "localidad", "distrito", "provincia"):
        v = str(a.get(k) or "").strip()
        if v:
            return v
    return ""


def tramos_desde_actividades(actividades: list[dict], dias: list[str], partida: str = "Hospedaje") -> list[dict]:
    """Los tramos de movilidad que se deducen de las actividades de la semana: cada día, del punto
    de partida a la primera actividad, de una actividad a la siguiente y de la última de vuelta.
    `actividades`: [{codigo, fecha, hora_inicio, lugar|localidad|distrito}]. Monto 0: lo pone el
    reparto o la persona."""
    salida = []
    for d in dias:
        del_dia = sorted(
            (a for a in actividades if str(a.get("fecha") or "")[:10] == d and _lugar(a)),
            key=lambda a: (str(a.get("hora_inicio") or "99:99"), str(a.get("codigo") or "")),
        )
        if not del_dia:
            continue
        anterior = partida
        for a in del_dia:
            lugar = _lugar(a)
            if lugar != anterior:
                salida.append({"fecha": d, "hora": str(a.get("hora_inicio") or "")[:5], "desde": anterior,
                               "hasta": lugar, "monto": 0.0, "actividad": str(a.get("codigo") or "")})
            anterior = lugar
        if anterior != partida:
            # La vuelta, a la hora en que terminó la última actividad (o, sin fin, a la de su inicio).
            fin = str(del_dia[-1].get("hora_fin") or del_dia[-1].get("hora_inicio") or "")[:5]
            # La vuelta lleva el código de la última actividad: así se sabe que la propuso el sistema.
            salida.append({"fecha": d, "hora": fin, "desde": anterior, "hasta": partida, "monto": 0.0,
                           "actividad": str(del_dia[-1].get("codigo") or "")})
    return salida


# --- Controles ----------------------------------------------------------------------------------------


def _plano(t: str) -> str:
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(ch for ch in t if unicodedata.category(ch) != "Mn")


def clave_comprobante(c: dict) -> str | None:
    """La identidad de un comprobante para detectar repetidos: RUC (si lo hay), serie y número sin
    ceros a la izquierda. Sin número no se puede comparar (None)."""
    numero = re.sub(r"\D", "", str(c.get("numero") or ""))
    if not numero:
        return None
    serie = re.sub(r"[^A-Z0-9]", "", str(c.get("serie") or "").upper())
    ruc = re.sub(r"\D", "", str(c.get("ruc") or ""))
    return f"{ruc}|{serie}|{int(numero)}"


def documento_de(c: dict) -> str:
    """«Boleta de venta electrónica N.° EB01-813» (la columna DOCUMENTO del Anexo 4)."""
    tipo = TIPOS_COMPROBANTE.get(str(c.get("tipo") or ""), "Comprobante")
    serie, numero = str(c.get("serie") or "").strip(), str(c.get("numero") or "").strip()
    num = f"{serie}-{numero}" if serie and numero else (serie or numero)
    return f"{tipo} N.° {num}" if num else tipo


_PALABRAS_A = ("desayuno", "almuerzo", "cena", "comida", "alimenta", "menu", "hotel", "hostal", "hospedaje", "alojamiento")


def controles(rendicion: dict, liquidacion: dict, comprobantes: list[dict], declarados: list[dict],
              parametros: dict, hoy: str, limite: str | None = None,
              repetidos_fuera: dict[str, str] | None = None, anexos: list[dict] | None = None) -> list[dict]:
    """Los controles visibles de una rendición, del más grave al más leve. Cada uno:
    {codigo, nivel: error|aviso|info, texto (breve), dia?, ref?: 'comprobante:<id>'|'declarado:<id>'}.
    Un `error` impide marcarla «lista». `limite` es la fecha límite para rendir (la calcula quien
    llama con los días hábiles); `repetidos_fuera`: {clave_comprobante: «en la rendición de …»}."""
    val = {k: (v["valor"] if isinstance(v, dict) else v) for k, v in parametros.items()}
    salida: list[dict] = []
    inicio, fin = str(rendicion.get("fecha_inicio") or ""), str(rendicion.get("fecha_fin") or "")
    dias = set(dias_de(inicio, fin))

    def poner(codigo: str, nivel: str, texto: str, **extra) -> None:
        salida.append({"codigo": codigo, "nivel": nivel, "texto": texto, **extra})

    if not dias:
        poner("sin_fechas", "error", "Faltan las fechas de la comisión.")
    if not rendicion.get("dni"):
        poner("sin_dni", "aviso", "Falta su DNI: complételo en Mi perfil (sale en la declaración jurada).")
    if not rendicion.get("cargo"):
        poner("sin_cargo", "aviso", "Falta su cargo: complételo en Mi perfil.")
    if not rendicion.get("memorando"):
        poner("sin_memorando", "aviso", "Vincule el memorando que solicitó los viáticos.")
    elif rendicion["memorando"].get("numerado") is False:
        poner("memorando_sin_numero", "aviso", "El memorando vinculado aún no tiene número.")

    pendientes = [x.strip(" -•\t") for x in str(rendicion.get("pendientes") or "").splitlines() if x.strip(" -•\t")]
    if pendientes:
        # Lo que la persona anotó que falta (2026-10-18): visible arriba hasta que lo borre.
        poner("pendientes", "aviso", f"Pendiente: {pendientes[0]}" + (f" (y {len(pendientes) - 1} más)" if len(pendientes) > 1 else ""))

    # Los comprobantes se entregaron EN FÍSICO (2026-10-18, Edison): la foto deja de faltar.
    en_fisico = str(rendicion.get("en_fisico") or "").strip().lower() in ("si", "sí", "1", "true")
    if en_fisico and comprobantes:
        poner("en_fisico", "info", "Comprobantes entregados en físico: la foto no hace falta.")
    vistos: dict[str, int] = {}
    comidas: dict[tuple[str, str], str] = {}
    for c in comprobantes:
        ref = f"comprobante:{c.get('id')}"
        f = str(c.get("fecha") or "")[:10]
        concepto = str(c.get("concepto") or "")
        nombre = documento_de(c)
        if concepto not in CONCEPTOS:
            poner("concepto", "error", f"{nombre}: concepto no válido.", ref=ref)
        elif CONCEPTOS[concepto][0] == "A":
            if f and dias and f not in dias:
                poner("fuera_de_fecha", "error", f"{nombre} es del {fecha_corta(f)}, fuera de la comisión.", ref=ref)
            if concepto in UNO_POR_DIA and f:
                # Un desayuno, un almuerzo y una cena por día (2026-10-18, Edison: «en un día no puede haber dos
                # desayunos»); el hospedaje y los otros pueden ser más de uno.
                if (f, concepto) in comidas:
                    otra = {"desayuno": "otro desayuno", "almuerzo": "otro almuerzo", "cena": "otra cena"}[concepto]
                    poner("concepto_repetido", "aviso", f"{nombre}: ya hay {otra} el {fecha_corta(f)[:5]} ({comidas[(f, concepto)]}); "
                          "va uno por día.", ref=ref)
                else:
                    comidas[(f, concepto)] = nombre
            if str(c.get("tipo") or "") not in TIPOS_SUSTENTO_A:
                poner("tipo_seccion", "aviso", f"{nombre}: la alimentación y el hospedaje se sustentan con factura, boleta o ticket.", ref=ref)
        elif concepto == "pasaje_terrestre" and not centimos(val.get("recibido_pasajes")):
            poner("concepto_seccion", "aviso", f"{nombre}: hay pasajes, pero no se registró el importe recibido de pasajes.", ref=ref)
        elif concepto == "otro_recurso" and not centimos(val.get("recibido_otros")):
            poner("concepto_seccion", "aviso", f"{nombre}: hay otros recursos, pero no se registró su importe recibido.", ref=ref)
        if not f:
            poner("sin_fecha", "error", f"{nombre}: falta la fecha.", ref=ref)
        if centimos(c.get("importe")) <= 0:
            poner("sin_importe", "error", f"{nombre}: falta el importe.", ref=ref)
        k = clave_comprobante(c)
        if k:
            if k in vistos:
                poner("repetido", "error", f"{nombre} está dos veces.", ref=ref)
            elif repetidos_fuera and k in repetidos_fuera:
                poner("repetido", "error", f"{nombre} ya figura {repetidos_fuera[k]}.", ref=ref)
            vistos[k] = 1
        if not c.get("archivo") and not en_fisico:
            poner("sin_foto", "aviso", f"{nombre}: falta la foto o el PDF.", ref=ref)
        if str(c.get("tipo") or "").startswith("factura") and centimos(c.get("importe")) > 70000:
            # DI 37-2025-DF-DGA-CR, 7.9.1.1.6: factura de más de S/ 700 → retener el 3 % (régimen de retenciones del IGV).
            poner("retencion", "aviso", f"{nombre}: pasa de S/ 700; corresponde retener el 3 % del IGV.", ref=ref)

    for x in declarados:
        f = str(x.get("fecha") or "")[:10]
        es_tramo = (x.get("clase") or "movilidad") == "movilidad"
        # Los tramos son de la COMISIÓN (`tramo:<id>`); los otros gastos, de la rendición (`declarado:<id>`).
        ref = f"tramo:{x.get('id')}" if es_tramo else f"declarado:{x.get('id')}"
        que = "Tramo" if es_tramo else "Gasto sin comprobante"
        if f and dias and f not in dias:
            poner("fuera_de_fecha", "error", f"{que} del {fecha_corta(f)}, fuera de la comisión.", ref=ref)
        if centimos(x.get("monto")) <= 0:
            poner("sin_importe", "aviso", f"{que} del {fecha_corta(f)} sin monto.", ref=ref)
        if que != "Tramo" and any(p in _plano(x.get("concepto")) for p in _PALABRAS_A):
            poner("concepto_seccion", "aviso", f"«{x.get('concepto')}»: la alimentación y el hospedaje van con comprobante.", ref=ref)
        elif que != "Tramo":
            # La declaración jurada vale SOLO para la movilidad (DI 37-2025-DF-DGA-CR, 7.9.1.1.2; calibre 10518).
            poner("dj_solo_movilidad", "aviso", f"«{x.get('concepto') or 'Gasto sin comprobante'}»: la declaración jurada vale solo para la movilidad; "
                  "lo demás va con comprobante.", ref=ref)

    tope_dj = centimos(liquidacion.get("tope_dj"))
    for d in liquidacion.get("dias", []):
        f = d["fecha"]
        if not d["dj_ok"]:
            # Aviso, no error: el tope DIARIO es práctica de la entidad; la directiva limita el 30 % del TOTAL
            # (DI 37-2025-DF-DGA-CR, 7.9.1.1.2), que controla `pct_dj` (2026-10-18).
            poner("dj_tope", "aviso", f"{fecha_corta(f)}: la declaración jurada ({texto_soles(centimos(d['dj']))}) pasa el tope diario de {texto_soles(tope_dj)}.", dia=f)
        if not d["total_ok"]:
            poner("dia_tope", "error", f"{fecha_corta(f)}: lo reconocido pasa el viático del día.", dia=f)
        if d["exceso"] > 0:
            poner("exceso", "aviso", f"{fecha_corta(f)}: {texto_soles(centimos(d['exceso']))} sobre el viático; lo asume el comisionado.", dia=f)
        if d.get("compartida") is not None and d["dj_ok"] and d["total_ok"] and centimos(d["movilidad"]) > centimos(d["compartida"]):
            # La movilidad es la misma para todos (2026-10-18): si pasa lo que alcanza a otro de la comisión,
            # a esa persona le pasa el viático del día.
            poner("movilidad_compartida", "aviso", f"{fecha_corta(f)}: la movilidad ({texto_corto(centimos(d['movilidad']))}) pasa lo que alcanza a todos. "
                  f"{d.get('explicacion') or ''}".strip(), dia=f)
        if d["objetivo"] is not None and centimos(d["movilidad"]) != centimos(d["objetivo"]):
            poner("tramos_dj", "aviso", f"{fecha_corta(f)}: los tramos suman {texto_soles(centimos(d['movilidad']))} y la DJ del día es {texto_soles(centimos(d['objetivo']))}.", dia=f)

    if not liquidacion.get("pct_dj_ok", True):
        poner("pct_dj", "error", f"La declaración jurada es el {liquidacion['pct_dj']:.2f} % del viático; el límite es {liquidacion['pct_dj_max']:.0f} %.")
    asignado, recibido = centimos(liquidacion.get("asignado")), centimos(liquidacion.get("recibido"))
    if recibido and asignado and recibido != asignado:
        poner("recibido", "aviso", f"Lo recibido ({texto_soles(recibido)}) no es viático × días ({texto_soles(asignado)}).")
    origen_recibido = (parametros.get("recibido_viaticos") or {}).get("origen") if isinstance(parametros.get("recibido_viaticos"), dict) else None
    if origen_recibido == "supuesto" and asignado:
        # No se inventa: lo recibido varía en cada comisión (2026-10-18, Edison). Sin dato, se SUPONE
        # viático × días para calcular y queda PENDIENTE hasta que alguien lo anote.
        poner("recibido_supuesto", "aviso", f"Importe recibido: no consta. Anótelo en Datos (memorando o comprobante de pago); "
              f"mientras, se calcula con {texto_soles(asignado)}.")

    estado = str(rendicion.get("estado") or "borrador")
    if limite and corre_plazo(estado):
        if hoy > limite:
            # Quien tiene una rendición pendiente no recibe nuevos viáticos (DI 37-2025-DF-DGA-CR, 6.6.4).
            poner("plazo", "aviso", f"Plazo para rendir vencido el {fecha_corta(limite)}. Mientras esté pendiente, no se otorgan nuevos viáticos.", urgente=True)
        else:
            faltan = (date.fromisoformat(limite) - date.fromisoformat(hoy)).days
            nivel = "aviso" if faltan <= 3 else "info"
            poner("plazo", nivel, f"Rendir hasta el {fecha_corta(limite)} ({'hoy' if faltan == 0 else f'faltan {faltan} días'}).")

    saldo = centimos(liquidacion.get("saldo"))
    clases_anexo = {str(a.get("clase") or "") for a in (anexos or [])}
    if saldo > 0:
        # DI 37-2025-DF-DGA-CR, 7.9.4.2: el sobrante se devuelve en efectivo en la Caja de Tesorería y la copia
        # del recibo forma parte de la rendición.
        if "devolucion" in clases_anexo:
            poner("saldo", "info", f"Saldo a devolver: {texto_soles(saldo)}. Recibo de devolución adjunto.")
        else:
            poner("saldo", "info", f"Saldo a devolver: {texto_soles(saldo)}. Devuélvalo en la Caja de Tesorería y adjunte el recibo.")
    if (comprobantes or declarados) and "boleto" not in clases_anexo:
        # DI 37-2025-DF-DGA-CR, 7.9.1.1.5: el boleto aéreo no se rinde, pero se adjunta (fechas de ida y vuelta).
        poner("boleto", "info", "Si viajó en avión, adjunte el boleto en Documento (no se rinde, pero se presenta).")
    for clave, rotulo in (("pasajes", "pasajes"), ("otros", "otros recursos")):
        s = centimos((liquidacion.get(clave) or {}).get("saldo"))
        if s > 0:
            poner(f"saldo_{clave}", "info", f"Saldo de {rotulo} a devolver: {texto_soles(s)}.")
        elif s < 0:
            poner(f"saldo_{clave}", "aviso", f"Los {rotulo} rendidos pasan lo recibido en {texto_soles(-s)}.")
    if not comprobantes and not declarados:
        poner("vacia", "info", "Aún no hay comprobantes ni movilidad.")
    orden = {"error": 0, "aviso": 1, "info": 2}
    salida.sort(key=lambda x: (orden[x["nivel"]], not x.get("urgente", False)))
    return salida


# --- Avance por sección ------------------------------------------------------------------------------

#: Los controles que se corrigen en cada sección (lo mismo que `pasoDeControl` de la web).
_DE_DATOS = {"sin_dni", "sin_cargo", "sin_memorando", "memorando_sin_numero", "sin_fechas", "recibido", "recibido_supuesto"}
_DE_MOVILIDAD = {"dj_tope", "tramos_dj", "dia_tope", "movilidad_compartida"}
SECCIONES = (("datos", "Datos"), ("comprobantes", "Comprobantes"), ("movilidad", "Movilidad"), ("documento", "Documento"))


def seccion_de_control(c: dict) -> str:
    ref = str(c.get("ref") or "")
    if ref.startswith("comprobante:"):
        return "comprobantes"
    if ref.startswith(("declarado:", "tramo:")) or c.get("codigo") in _DE_MOVILIDAD:
        return "movilidad"
    if c.get("codigo") in _DE_DATOS:
        return "datos"
    return "general"


def avance(datos: dict, comprobantes: list[dict], declarados: list[dict], controles_: list[dict],
           documento: dict) -> dict:
    """El avance de una rendición por sección (2026-10-18, pedido de Edison: «pendiente, registrado,
    validado»). Cada sección: `pendiente` (falta lo esencial), `registrado` (hay datos con algo por
    revisar) o `validado` (sin controles por corregir ni revisar). Pura.

    `documento`: {pdf: bool, al_dia: bool}. Devuelve {secciones: [{clave, etiqueta, estado, texto}],
    validadas, total}."""
    por = {k: [c for c in controles_ if seccion_de_control(c) == k and c.get("nivel") in ("error", "aviso")]
           for k, _ in SECCIONES}
    errores = sum(1 for c in controles_ if c.get("nivel") == "error")
    salida = []

    def poner(clave: str, estado: str, texto: str) -> None:
        salida.append({"clave": clave, "etiqueta": dict(SECCIONES)[clave], "estado": estado, "texto": texto})

    if not (datos.get("fecha_inicio") and datos.get("fecha_fin")):
        poner("datos", "pendiente", "Faltan las fechas")
    elif any(c["codigo"] == "sin_memorando" for c in por["datos"]):
        poner("datos", "pendiente", "Falta el memorando")
    elif any(c["codigo"] == "recibido_supuesto" for c in por["datos"]):
        poner("datos", "registrado", "Falta el importe recibido")
    elif por["datos"]:
        poner("datos", "registrado", f"{len(por['datos'])} por revisar")
    else:
        poner("datos", "validado", "Completos")

    sin_datos = [c for c in comprobantes if not c.get("numero") and not centimos(c.get("importe"))]
    if not comprobantes:
        poner("comprobantes", "pendiente", "Sin comprobantes")
    elif sin_datos:
        poner("comprobantes", "pendiente", f"{len(sin_datos)} foto(s) por completar")
    elif por["comprobantes"]:
        poner("comprobantes", "registrado", f"{len(comprobantes)} · {len(por['comprobantes'])} por revisar")
    else:
        poner("comprobantes", "validado", f"{len(comprobantes)} registrados")

    tramos = [x for x in declarados if (x.get("clase") or "movilidad") == "movilidad"]
    if not declarados:
        poner("movilidad", "pendiente", "Sin tramos")
    elif por["movilidad"]:
        poner("movilidad", "registrado", f"{len(tramos)} tramos · {len(por['movilidad'])} por revisar")
    elif tramos and all(x.get("actividad") for x in tramos):
        # Todos los propuso el sistema desde las actividades: nadie los revisó aún.
        poner("movilidad", "registrado", f"{len(tramos)} tramos propuestos: revíselos")
    else:
        poner("movilidad", "validado", f"{len(tramos)} tramos")

    if not documento.get("pdf"):
        poner("documento", "pendiente", "Sin generar")
    elif not documento.get("al_dia"):
        poner("documento", "registrado", "Desactualizado: vuelva a generarlo")
    elif errores:
        poner("documento", "registrado", f"{errores} control(es) por corregir")
    else:
        poner("documento", "validado", "Al día")
    return {"secciones": salida, "validadas": sum(1 for s in salida if s["estado"] == "validado"), "total": len(salida)}


def partir_numero(serie: str, numero: str) -> tuple[str, str]:
    """«EB01-1586», «F001 - 00004711», «FR95 / 12841» o «001 026812» escritos en un solo campo → (serie,
    número). Si la serie ya vino aparte o no hay separador, se devuelven tal cual. Pura."""
    serie, numero = str(serie or "").strip(), str(numero or "").strip()
    if serie:
        return serie.upper(), numero
    m = re.match(r"^\s*([A-Za-z0-9]{1,6})\s*[-–/ ]\s*(\d{1,12})\s*$", numero)
    if m:
        return m.group(1).upper(), m.group(2)
    return serie, numero


#: Los estados en que corre el plazo para rendir (2026-10-18, Edison: «una rendición presentada no lleva
#: “Vencida”»): presentada, observada o cerrada ya se rindió; la observada se subsana en 72 horas, aparte.
ESTADOS_CON_PLAZO = ("borrador", "lista")


def corre_plazo(estado: str) -> bool:
    return estado in ESTADOS_CON_PLAZO


def puede_pasar(estado: str, nuevo: str, es_admin: bool, errores: int) -> str | None:
    """¿Se permite el cambio de estado? None si sí; el motivo si no. Pura."""
    if nuevo not in ESTADOS:
        return "Estado desconocido."
    if estado == nuevo:
        return None
    if estado == "cerrada" and not es_admin:
        return "La rendición está cerrada."
    if estado == "presentada" and not es_admin:
        return "Ya se presentó: para corregirla, Administración debe observarla."
    if nuevo in ("lista", "presentada") and errores:
        return f"Hay {errores} control(es) por corregir antes."
    if nuevo in ("observada", "cerrada") and not es_admin:
        return "Solo Administración observa o cierra una rendición."
    if nuevo == "presentada" and estado not in ("lista", "observada"):
        return "Primero márquela como lista."
    return None
