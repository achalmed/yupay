"""La COMISIÓN de una rendición y su MOVILIDAD COMPARTIDA (2026-10-18; `docs/arquitectura.md` §32).

Edison: «en el Anexo 3 los dos trabajadores tienen los MISMOS tramos de movilidad, porque viajan juntos
con el diputado al mismo lugar y en las mismas fechas. Solo cambia el Anexo 4». Por eso los tramos son
de la comisión (`rendicion_comisiones` → `rendicion_tramos`) y no de cada rendición: si uno registra
«Huanta → Huamanga, S/ 27», aparece en la rendición del otro; cualquiera lo corrige y se ve en ambas.

Un solo lugar de verdad (§27) y constancia de quién cambió qué: toda escritura en la movilidad pasa por
un `Lote` (una acción = un lote) que guarda cada tramo antes y después en `rendicion_cambios`; así se
muestra el historial y se DESHACE el último lote (`deshacer`), salvo lo que alguien cambió después.

Aquí vive también la migración de lo que ya existía (`migrar`, idempotente, la llama servicios/rendicion_db.py al
arrancar): cada rendición se vincula a su comisión y sus tramos pasan a la comisión, día por día los de
la rendición que declaró menos (`rendicion.elegir_tramos_por_dia`); lo distinto queda en la constancia.

La cuenta y la semana se piden por el contrato (`cuenta`, `cuentas`, `semana_de`; fase 10.2b, 2026-10-20).
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tiqsi.modulo import Perezosa, opcional
from tiqsi.nombres import sanear

from yupay.modelos import CambioMovilidad, ComisionServicio, GastoDeclarado, Rendicion, TramoMovilidad
from yupay import rendicion as calc

CAMPOS_TRAMO = ("fecha", "hora", "desde", "hasta", "monto", "actividad", "orden")


# --- Lo de otros, por el contrato (fase 10.2b, 2026-10-20) ---------------------------------------------------

identidad = Perezosa("identidad.v1")


async def cuenta(usuario_id: int | None) -> dict | None:
    """La cuenta vigente {id, usuario, nombre_completo, nombres, cargo, dni, rol, activo} («identidad.v1»)."""
    return await identidad.cuenta(usuario_id) if usuario_id else None


async def cuentas() -> list[dict]:
    """Todas las cuentas, con los mismos campos que `cuenta`."""
    return await identidad.cuentas()


async def semana_de(semana_id: int | None) -> dict | None:
    """La ficha vigente de la semana {id, codigo, tema, inicio, fin, provincias, region, carpeta} («semanas.v1»;
    sin la Semana de representación, ninguna)."""
    semanas = opcional("semanas.v1")
    return await semanas.ficha(semana_id) if semana_id and semanas is not None else None


# --- La comisión ---------------------------------------------------------------------------------------


def clave_y_carpeta(semana: dict | None, datos: dict, rid: int) -> tuple[str, str]:
    """(clave, carpeta relativa a RENDICIONES_DIR) de la comisión de una rendición. Pura.

    - Semana de representación: `sr:<id>` y `AAAA/<carpeta de la semana>` (el mismo nombre que su
      expediente en `representacion/`, para reconocerla de un vistazo).
    - Otra comisión de servicio: `cs:<inicio>_<lugar>` y `AAAA/AAAA-MM-DD_<lugar>`: quienes viajaron
      juntos (mismo inicio y lugar) la comparten.
    - Sin fechas: una propia, `r:<id>`, en `sin-fecha/R-NNN`."""
    if semana is not None:
        carpeta = semana["carpeta"] or ""
        anio = carpeta[:4] if re.match(r"^\d{4}", carpeta) else str(datos.get("fecha_inicio") or "")[:4] or "sin-fecha"
        return f"sr:{semana['id']}", f"{anio}/{carpeta}"
    inicio = str(datos.get("fecha_inicio") or "")[:10]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", inicio):
        return f"r:{rid}", f"sin-fecha/R-{rid:03d}"
    slug = sanear(str(datos.get("lugar") or datos.get("motivo") or "comision"), 40).lower() or "comision"
    return f"cs:{inicio}_{slug}", f"{inicio[:4]}/{inicio}_{slug}"


async def comision_de(sesion: AsyncSession, r: Rendicion) -> ComisionServicio:
    """La comisión de la rendición; si aún no tiene, la busca por su clave o la crea (dos peticiones a la
    vez no crean dos: `ON CONFLICT DO NOTHING` sobre la clave única)."""
    if r.comision_id:
        c = await sesion.get(ComisionServicio, r.comision_id)
        if c is not None:
            return c
    semana = await semana_de(r.semana_id)
    clave, carpeta = clave_y_carpeta(semana, dict(r.datos or {}), r.id)
    await sesion.execute(insert(ComisionServicio).values(clave=clave, semana_id=semana["id"] if semana else None,
                                                         carpeta=carpeta, datos={}).on_conflict_do_nothing(index_elements=["clave"]))
    c = (await sesion.execute(select(ComisionServicio).where(ComisionServicio.clave == clave))).scalar_one()
    r.comision_id = c.id
    return c


async def rendiciones_de(sesion: AsyncSession, comision_id: int) -> list[Rendicion]:
    return list((await sesion.execute(select(Rendicion).where(Rendicion.comision_id == comision_id).order_by(Rendicion.id))).scalars())


async def bloqueada_por(sesion: AsyncSession, comision_id: int) -> str:
    """Si alguna rendición de la comisión ya se presentó (o se cerró), la movilidad compartida queda FIJA:
    cambiarla alteraría lo presentado. Devuelve el nombre de quien la presentó ('' si no está fija)."""
    uid = (await sesion.execute(
        select(Rendicion.usuario_id)
        .where(Rendicion.comision_id == comision_id, Rendicion.estado.in_(("presentada", "cerrada")))
        # Quien presentó PRIMERO (la dejó fija); antes salía cualquiera de los que presentaron (2026-10-20).
        .order_by(Rendicion.presentada_en.asc().nulls_last(), Rendicion.id).limit(1)
    )).scalar()
    if uid is None:
        return ""
    c = await cuenta(uid)
    # Presentada por una cuenta que ya no está: la movilidad sigue fija (lo presentado no se altera).
    return (c["nombre_completo"] if c else "") or "un comisionado"


async def tramos_de(sesion: AsyncSession, comision_id: int) -> list[TramoMovilidad]:
    return list((await sesion.execute(
        select(TramoMovilidad).where(TramoMovilidad.comision_id == comision_id)
        .order_by(TramoMovilidad.fecha, TramoMovilidad.hora, TramoMovilidad.orden, TramoMovilidad.id)
    )).scalars())


def ficha(t: TramoMovilidad) -> dict:
    """El tramo como dato (lo que se guarda antes y después en la constancia)."""
    return {"fecha": t.fecha, "hora": t.hora, "desde": t.desde, "hasta": t.hasta, "monto": float(t.monto or 0),
            "actividad": t.actividad, "orden": t.orden}


async def siguiente_orden(sesion: AsyncSession, comision_id: int) -> int:
    return ((await sesion.execute(select(func.max(TramoMovilidad.orden)).where(TramoMovilidad.comision_id == comision_id))).scalar() or 0) + 1


# --- El lote: una acción, con su constancia -----------------------------------------------------------


class Lote:
    """Una acción sobre la movilidad de una comisión. Cada `crear`, `cambiar`, `quitar` o `dato` escribe y
    deja su fila en `rendicion_cambios` con el mismo `lote`; `texto` es lo que se lee en el historial
    («Ajustar a lo sugerido», «Quitar los tramos del lun 24/08»)."""

    def __init__(self, sesion: AsyncSession, comision: ComisionServicio, usuario_id: int | None, texto: str,
                 rendicion_id: int | None = None, deshace: str = ""):
        self.sesion, self.comision, self.usuario_id = sesion, comision, usuario_id
        self.texto, self.rendicion_id, self.deshace = texto[:300], rendicion_id, deshace
        self.id = uuid.uuid4().hex[:16]
        self.filas = 0

    def _constancia(self, accion: str, tramo_id: int | None, antes: dict | None, despues: dict | None) -> None:
        self.sesion.add(CambioMovilidad(comision_id=self.comision.id, lote=self.id, texto=self.texto, accion=accion,
                                        tramo_id=tramo_id, antes=antes, despues=despues, usuario_id=self.usuario_id,
                                        rendicion_id=self.rendicion_id, deshace=self.deshace))
        self.filas += 1

    async def crear(self, valores: dict) -> TramoMovilidad:
        t = TramoMovilidad(comision_id=self.comision.id, actualizado_por=self.usuario_id,
                           **{k: v for k, v in valores.items() if k in CAMPOS_TRAMO})
        if not t.orden:
            t.orden = await siguiente_orden(self.sesion, self.comision.id)
        self.sesion.add(t)
        await self.sesion.flush()
        self._constancia("crear", t.id, None, ficha(t))
        return t

    def cambiar(self, t: TramoMovilidad, valores: dict) -> bool:
        antes = ficha(t)
        for k, v in valores.items():
            if k in CAMPOS_TRAMO:
                setattr(t, k, v)
        despues = ficha(t)
        if despues == antes:
            return False
        t.actualizado_por = self.usuario_id
        t.actualizado_en = datetime.now(timezone.utc)
        self._constancia("cambiar", t.id, antes, despues)
        return True

    async def quitar(self, t: TramoMovilidad) -> None:
        self._constancia("quitar", t.id, ficha(t), None)
        await self.sesion.delete(t)

    def dato(self, clave: str, valor) -> bool:
        """Un dato de la comisión (`dj_objetivo`, `recibido_viaticos`); None lo quita."""
        datos = dict(self.comision.datos or {})
        antes = datos.get(clave)
        if valor in (None, "", {}):
            datos.pop(clave, None)
            valor = None
        else:
            datos[clave] = valor
        if antes == valor:
            return False
        self.comision.datos = datos
        self._constancia("dato", None, {clave: antes}, {clave: valor})
        return True


# --- Deshacer e historial ------------------------------------------------------------------------------


async def ultimo_lote(sesion: AsyncSession, comision_id: int) -> dict | None:
    """El último lote que se puede deshacer (no deshecho y que no sea, a su vez, un deshacer)."""
    fila = (await sesion.execute(
        select(CambioMovilidad).where(CambioMovilidad.comision_id == comision_id, CambioMovilidad.deshecho.is_(False),
                                      CambioMovilidad.deshace == "")
        .order_by(CambioMovilidad.id.desc()).limit(1)
    )).scalar()
    if fila is None:
        return None
    quien = await cuenta(fila.usuario_id)
    n = (await sesion.execute(select(func.count()).where(CambioMovilidad.lote == fila.lote))).scalar() or 0
    return {"lote": fila.lote, "texto": fila.texto, "usuario": calc.nombre_corto(quien["nombres"], quien["nombre_completo"]) if quien else "",
            "en": fila.en.isoformat() if fila.en else None, "cambios": n}


async def deshacer(sesion: AsyncSession, comision: ComisionServicio, usuario_id: int | None, rendicion_id: int | None) -> dict:
    """Vuelve atrás el último lote de la comisión. Lo que alguien cambió DESPUÉS (el tramo ya no está como
    lo dejó el lote) no se toca y se cuenta. Lo deshecho queda en la constancia como otro lote."""
    ultimo = await ultimo_lote(sesion, comision.id)
    if ultimo is None:
        return {"deshecho": None, "revertidos": 0, "saltados": 0}
    filas = list((await sesion.execute(select(CambioMovilidad).where(CambioMovilidad.lote == ultimo["lote"])
                                       .order_by(CambioMovilidad.id.desc()))).scalars())
    lote = Lote(sesion, comision, usuario_id, f"Deshacer: {ultimo['texto']}", rendicion_id, deshace=ultimo["lote"])
    revertidos = saltados = 0
    for f in filas:
        f.deshecho = True
        t = await sesion.get(TramoMovilidad, f.tramo_id) if f.tramo_id else None
        if f.accion == "crear":
            if t is not None and ficha(t) == f.despues:
                await lote.quitar(t)
                revertidos += 1
            else:
                saltados += 1
        elif f.accion == "cambiar":
            if t is not None and ficha(t) == f.despues:
                lote.cambiar(t, dict(f.antes or {}))
                revertidos += 1
            else:
                saltados += 1
        elif f.accion == "quitar":
            if t is None and f.antes:
                await lote.crear(dict(f.antes))
                revertidos += 1
            else:
                saltados += 1
        elif f.accion == "dato" and f.antes is not None:
            (clave, valor), = f.antes.items()
            actual = (comision.datos or {}).get(clave)
            if actual == (f.despues or {}).get(clave):
                lote.dato(clave, valor)
                revertidos += 1
            else:
                saltados += 1
    return {"deshecho": ultimo["texto"], "revertidos": revertidos, "saltados": saltados}


async def historial(sesion: AsyncSession, comision_id: int, limite: int = 40) -> list[dict]:
    """Los últimos lotes de la comisión, del más nuevo al más viejo: quién, cuándo, qué y cuántos tramos."""
    filas = list((await sesion.execute(
        select(CambioMovilidad)
        .where(CambioMovilidad.comision_id == comision_id).order_by(CambioMovilidad.id.desc()).limit(limite * 20)
    )).scalars())
    personas = {x["id"]: (x["nombres"], x["nombre_completo"]) for x in await cuentas()} if filas else {}
    lotes: dict[str, dict] = {}
    for c in filas:
        nombres, completo = personas.get(c.usuario_id or 0, ("", ""))
        x = lotes.get(c.lote)
        if x is None:
            if len(lotes) >= limite:
                break
            x = lotes[c.lote] = {"lote": c.lote, "texto": c.texto, "usuario": calc.nombre_corto(nombres or "", completo or ""),
                                 "en": c.en.isoformat() if c.en else None, "deshecho": c.deshecho, "es_deshacer": c.deshace not in ("", "migracion"),
                                 "detalle": []}
        if len(x["detalle"]) < 12:
            x["detalle"].append(_detalle(c))
    return list(lotes.values())


def _detalle(c: CambioMovilidad) -> str:
    """Una línea por cambio: «lun 24/08 Huanta → Huamanga: S/ 27 → S/ 30»."""
    def t(x: dict | None) -> str:
        if not x:
            return ""
        return f"{calc.fecha_corta(x.get('fecha', ''))[:5]} {x.get('desde') or '¿?'} → {x.get('hasta') or '¿?'}"
    def m(x: dict | None) -> str:
        return calc.texto_corto(calc.centimos((x or {}).get("monto")))
    if c.accion == "crear":
        return f"Agregó {t(c.despues)} ({m(c.despues)})"
    if c.accion == "quitar":
        return f"Quitó {t(c.antes)} ({m(c.antes)})"
    if c.accion == "dato" and "descartado" in (c.antes or {}):
        d = c.antes["descartado"] or {}
        quedo = f"; quedó el de R-{d['elegido']:03d}" if d.get("elegido") else ""
        return (f"Descartado: R-{d.get('rendicion_id', 0):03d} declaraba {calc.texto_corto(calc.centimos(d.get('total')))} "
                f"el {calc.fecha_corta(d.get('fecha', ''))[:5]} con otros tramos{quedo}")
    if c.accion == "dato":
        (clave, antes), = (c.antes or {None: None}).items()
        despues = (c.despues or {}).get(clave)
        nombre = {"recibido_viaticos": "Importe recibido", "dj_objetivo": "DJ del día fijada"}.get(clave or "", clave or "dato")
        return f"{nombre}: {antes if antes is not None else '—'} → {despues if despues is not None else '—'}"
    partes = []
    a, d = c.antes or {}, c.despues or {}
    for k, rotulo in (("fecha", "día"), ("hora", "hora"), ("desde", "del"), ("hasta", "al")):
        if a.get(k) != d.get(k):
            partes.append(f"{rotulo} {a.get(k) or '—'} → {d.get(k) or '—'}")
    if calc.centimos(a.get("monto")) != calc.centimos(d.get("monto")):
        partes.append(f"{m(a)} → {m(d)}")
    return f"Cambió {t(a)}: " + "; ".join(partes) if partes else f"Cambió {t(a)}"


# --- Migración de lo existente (idempotente; servicios/rendicion_db.py al arrancar) --------------------


async def migrar(sesion: AsyncSession) -> dict:
    """1) Cada rendición sin comisión se vincula a la suya. 2) Los tramos que cada rendición guardaba por
    su cuenta (`rendicion_declarados`, clase movilidad) pasan a su comisión: día por día, los de la
    rendición que declaró menos; lo distinto queda en la constancia (nada se pierde). 3) La DJ del día
    fijada en cada rendición pasa a la comisión (el menor por día). Sin nada que migrar, no toca nada."""
    hechos = {"vinculadas": 0, "tramos": 0, "descartes": 0}
    for r in list((await sesion.execute(select(Rendicion).where(Rendicion.comision_id.is_(None)).order_by(Rendicion.id))).scalars()):
        await comision_de(sesion, r)
        hechos["vinculadas"] += 1
    await sesion.flush()
    viejos = list((await sesion.execute(
        select(GastoDeclarado, Rendicion.comision_id).join(Rendicion, Rendicion.id == GastoDeclarado.rendicion_id)
        .where(GastoDeclarado.clase == "movilidad").order_by(GastoDeclarado.rendicion_id, GastoDeclarado.fecha,
                                                              GastoDeclarado.hora, GastoDeclarado.orden, GastoDeclarado.id)
    )).all())
    por_comision: dict[int, dict[int, list[dict]]] = {}
    filas_viejas: list[GastoDeclarado] = []
    for x, cid in viejos:
        por_comision.setdefault(cid, {}).setdefault(x.rendicion_id, []).append(
            {"fecha": x.fecha, "hora": x.hora, "desde": x.desde, "hasta": x.hasta, "monto": float(x.monto or 0),
             "actividad": x.actividad, "orden": x.orden})
        filas_viejas.append(x)
    for cid, conjuntos in por_comision.items():
        c = await sesion.get(ComisionServicio, cid)
        ya = await tramos_de(sesion, cid)
        codigos = ", ".join(f"R-{rid:03d}" for rid in sorted(conjuntos))
        # `deshace="migracion"`: la migración no es un lote que se deshaga desde la web.
        lote = Lote(sesion, c, None, f"Movilidad compartida: tramos tomados de {codigos}", deshace="migracion")
        if ya:
            # La comisión ya tiene su movilidad: lo que quedaba suelto en las rendiciones va a la constancia.
            elegidos, descartes = [], [{"rendicion_id": rid, "fecha": "", "total": 0, "elegido": None, "tramos": ts}
                                       for rid, ts in conjuntos.items()]
        else:
            elegidos, descartes = calc.elegir_tramos_por_dia(conjuntos)
        for i, t in enumerate(elegidos, 1):
            await lote.crear({**t, "orden": i})
            hechos["tramos"] += 1
        for d in descartes:
            # Lo descartado (otro juego de tramos de ese día) queda entero en la constancia.
            lote._constancia("dato", None, {"descartado": d}, {"descartado": None})
            hechos["descartes"] += 1
    for x in filas_viejas:
        await sesion.delete(x)
    # La DJ del día fijada a mano pasa a la comisión (el menor por día si había varias).
    for r in list((await sesion.execute(select(Rendicion).where(Rendicion.comision_id.is_not(None)))).scalars()):
        obj = (r.datos or {}).get("dj_objetivo")
        if not obj:
            continue
        c = await sesion.get(ComisionServicio, r.comision_id)
        actual = dict((c.datos or {}).get("dj_objetivo") or {})
        for f, m in obj.items():
            actual[f] = min(actual[f], m) if f in actual else m
        c.datos = {**(c.datos or {}), "dj_objetivo": actual}
        r.datos = {k: v for k, v in (r.datos or {}).items() if k != "dj_objetivo"}
    await sesion.commit()
    return hechos
