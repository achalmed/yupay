"""RENDICIÓN DE CUENTAS de viáticos como módulo de la entidad (2026-10-18; `docs/arquitectura.md` §32).

Edison: «hay dos archivos de rendición de cuenta que hicimos de la Semana de representación; implementa
eso como módulo de la entidad […] que nos ayude a hacer el informe de rendición de cuenta de manera más
rápida, que nos solucione todo tipo de cosas que se puedan presentar, que todo sea automático».

Una rendición por comisionado y comisión de servicio, vinculada por clave (§27) a la semana (`sr:N`), al
memorando que solicitó los viáticos (`doc:N`) y a la cuenta del comisionado: lo que se muestra de ellos
es siempre lo vigente. El cálculo, los controles y el importe en letras son puros
(`servicios/rendicion.py`); el documento (Anexos 3 y 4) lo compone el marco (`rendicion_tex.py`, tipo
`rendicion-viaticos`) y la liquidación sale también en Excel con sus fórmulas (`rendicion_excel.py`).

Módulo aislado (proyecto Yupay; fase 10.2b, 2026-10-20): no importa nada de Qillqa. Su base, su configuración y
sus ajustes y su marco LaTeX son suyos (`servicios/rendicion_db.py`, `rendicion_config.py`, `AjusteRendicion`,
`app/rendicion_marco`); la cuenta, la semana, el memorando, el pegado y los días hábiles los pide por el contrato de
Tiqsi (`identidad.v1`, `semanas.v1`, `documentos.v1`, `pegado.v1`, `calendario.v1`); lo que no esté se apaga sin romper.

Todo el equipo usa el módulo salvo el invitado; cada quien ve las suyas (las de las que es comisionado y
las que hizo como ENCARGADO para un compañero) y el administrador, todas.

La MOVILIDAD es de la comisión, no de cada rendición (2026-10-18; `servicios/rendicion_comision.py`):
los tramos se registran una vez y salen en el Anexo 3 de todos los que viajaron juntos; la movilidad
sugerida del día es la que alcanza a TODOS (`rendicion.movilidad_compartida`).
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tiqsi.modulo import opcional
from tiqsi.nombres import sanear
from tiqsi.puertos import Usuario, usuario_actual
from tiqsi.web import enviar_archivo

from yupay.modelos import (AjusteRendicion, AnexoRendicion, ComisionServicio, ComprobanteGasto, GastoDeclarado,
                                   Rendicion, TramoMovilidad)
from yupay import rendicion as calc
from yupay import comision as rc
from yupay import excel as rendicion_excel, tex as rendicion_tex
from yupay.comision import cuenta, cuentas, semana_de
from yupay.config import raiz as raiz_rendiciones
from yupay.db import obtener_sesion_rendicion

router = APIRouter(prefix="/api/rendiciones", tags=["rendición de cuentas"])

AJUSTE = "parametros"            # sus ajustes (AjusteRendicion); antes, «rendicion_parametros» de la plataforma
EXTENSIONES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".pdf"}
MAX_ARCHIVO = 15 * 1024 * 1024


# --- Acceso -------------------------------------------------------------------------------------------


def _equipo(u: Usuario) -> None:
    if u.rol == "invitado":
        raise HTTPException(403, "La cuenta de invitado no usa la rendición de cuentas.")


def _admin(u: Usuario) -> bool:
    return u.rol == "administrador"


def _puede(r: Rendicion, u: Usuario) -> bool:
    """La ve y la edita su comisionado, quien la creó para él (el ENCARGADO que hace las rendiciones de
    la comisión, 2026-10-18) y Administración."""
    return _admin(u) or r.usuario_id == u.id or r.creado_por == u.id


async def _rendicion(sesion: AsyncSession, rid: int, u: Usuario, bloquear: bool = False) -> Rendicion:
    _equipo(u)
    q = select(Rendicion).where(Rendicion.id == rid)
    if bloquear:
        q = q.with_for_update()
    r = (await sesion.execute(q)).scalar_one_or_none()
    if r is None or not _puede(r, u):
        raise HTTPException(404, "Rendición no encontrada.")
    return r


def _editable(r: Rendicion, u: Usuario) -> None:
    if r.estado in ("presentada", "cerrada") and not _admin(u):
        raise HTTPException(409, "La rendición ya se presentó: pida a Administración que la observe para corregirla.")


async def _movilidad_editable(sesion: AsyncSession, r: Rendicion, u: Usuario) -> ComisionServicio:
    """La comisión de la rendición, si su movilidad se puede cambiar: es COMPARTIDA, así que queda fija en
    cuanto alguien de la comisión presentó la suya (cambiarla alteraría lo presentado)."""
    _editable(r, u)
    c = await rc.comision_de(sesion, r)
    quien = await rc.bloqueada_por(sesion, c.id)
    if quien and not _admin(u):
        raise HTTPException(409, f"La movilidad es compartida y {quien} ya presentó su rendición: quedó fija. "
                                 "Para corregirla, Administración debe observar esa rendición.")
    return c


# --- Lo vinculado, vigente ----------------------------------------------------------------------------


def _plano(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _plano(t)).strip("-")[:40] or "comisionado"


async def parametros_despacho(sesion: AsyncSession) -> dict:
    fila = await sesion.get(AjusteRendicion, AJUSTE)
    return dict(fila.valor or {}) if fila else {}


#: Lo que la rendición muestra del memorando (lo demás que da «documentos.v1», texto y referencia, es para leerlo).
CAMPOS_MEMORANDO = ("id", "numero", "fecha", "asunto", "estado", "numerado")


def _ficha_memorando(m: dict | None) -> dict | None:
    return {k: m[k] for k in CAMPOS_MEMORANDO} if m else None


async def _memorando(documento_id: int | None) -> dict | None:
    """El documento vigente por «documentos.v1» (Gestión documental); sin ella, ninguno."""
    docs = opcional("documentos.v1")
    return await docs.documento(documento_id) if documento_id and docs is not None else None


def _motivo_de(semana: dict | None) -> str:
    if not semana or not semana.get("inicio"):
        return ""
    d = date.fromisoformat(semana["inicio"][:10])
    return f"Semana de representación del mes de {calc.MESES[d.month]} de {d.year}"


def efectivos(datos: dict, semana: dict | None) -> tuple[dict, dict]:
    """Los datos de cabecera que RIGEN: los propios de la rendición o, si faltan, los de la semana
    (fechas, lugar y motivo), y de dónde sale cada uno. Pura."""
    d = dict(datos or {})
    origen: dict[str, str] = {}
    sugeridos = {
        "fecha_inicio": (semana or {}).get("inicio") or "",
        "fecha_fin": (semana or {}).get("fin") or "",
        "lugar": (semana or {}).get("region") or ", ".join((semana or {}).get("provincias") or []),
        "motivo": _motivo_de(semana),
    }
    for clave, valor in sugeridos.items():
        if str(d.get(clave) or "").strip():
            origen[clave] = "propio"
        elif valor:
            d[clave], origen[clave] = valor, "semana"
    if not d.get("fecha_rendicion") and d.get("fecha_fin"):
        d["fecha_rendicion"], origen["fecha_rendicion"] = d["fecha_fin"], "fin"
    return d, origen


def limite_para_rendir(fin: str, dias_habiles: int | None) -> str | None:
    if not fin or not dias_habiles:
        return None
    calendario = opcional("calendario.v1")   # los feriados del Perú; sin el calendario, no hay fecha límite
    if calendario is None:
        return None
    try:
        return calendario.dias_habiles(date.fromisoformat(fin[:10]), int(dias_habiles)).isoformat()
    except ValueError:
        return None


def _comprobante(c: ComprobanteGasto) -> dict:
    return {"id": c.id, "orden": c.orden, "fecha": c.fecha, "tipo": c.tipo, "serie": c.serie, "numero": c.numero,
            "ruc": c.ruc, "proveedor": c.proveedor, "concepto": c.concepto, "importe": float(c.importe or 0),
            "archivo": c.archivo, "nota": c.nota, "origen": c.origen, "documento": calc.documento_de(
                {"tipo": c.tipo, "serie": c.serie, "numero": c.numero})}


def _declarado(x: GastoDeclarado) -> dict:
    return {"id": x.id, "clase": x.clase, "orden": x.orden, "fecha": x.fecha, "hora": x.hora, "desde": x.desde,
            "hasta": x.hasta, "concepto": x.concepto, "monto": float(x.monto or 0), "actividad": x.actividad}


def _tramo(t: TramoMovilidad, nombres: dict[int, str] | None = None) -> dict:
    """Un tramo de la COMISIÓN con la forma de un gasto declarado (clase movilidad) y quién lo tocó."""
    return {"id": t.id, "clase": "movilidad", "orden": t.orden, "fecha": t.fecha, "hora": t.hora, "desde": t.desde,
            "hasta": t.hasta, "concepto": "", "monto": float(t.monto or 0), "actividad": t.actividad,
            "actualizado_por": (nombres or {}).get(t.actualizado_por or 0, ""),
            "actualizado_en": t.actualizado_en.isoformat() if t.actualizado_en else None}


async def _nombres_cortos() -> dict[int, str]:
    return {x["id"]: calc.nombre_corto(x["nombres"], x["nombre_completo"]) for x in await cuentas()}


def _recibido_de_memorando(m: dict | None) -> dict | None:
    """Lo recibido, si el memorando lo dice («… viáticos por S/ 1,600.00 …»): {valor, numero}."""
    if m is None:
        return None
    c = calc.importe_de_texto(m.get("texto") or "")
    if c is None:
        return None
    return {"valor": calc.soles(c), "numero": m["numero"]}


def _anexo(a: AnexoRendicion) -> dict:
    return {"id": a.id, "clase": a.clase, "descripcion": a.descripcion, "archivo": a.archivo,
            "creado_en": a.creado_en.isoformat() if a.creado_en else None}


async def _anexos(sesion: AsyncSession, rid: int) -> list[AnexoRendicion]:
    return list((await sesion.execute(select(AnexoRendicion).where(AnexoRendicion.rendicion_id == rid)
                                      .order_by(AnexoRendicion.id))).scalars())


def _publicos(datos: dict) -> dict:
    """Los datos sin las claves internas (`_carpeta`, `_huella`): las escribe el sistema, no la persona."""
    return {k: v for k, v in (datos or {}).items() if not str(k).startswith("_")}


async def _hijos(sesion: AsyncSession, rid: int) -> tuple[list[ComprobanteGasto], list[GastoDeclarado]]:
    """Los comprobantes y los OTROS gastos sin comprobante de la rendición (la movilidad es de la comisión)."""
    comp = list((await sesion.execute(select(ComprobanteGasto).where(ComprobanteGasto.rendicion_id == rid)
                                      .order_by(ComprobanteGasto.fecha, ComprobanteGasto.orden, ComprobanteGasto.id))).scalars())
    decl = list((await sesion.execute(select(GastoDeclarado).where(GastoDeclarado.rendicion_id == rid, GastoDeclarado.clase != "movilidad")
                                      .order_by(GastoDeclarado.fecha, GastoDeclarado.hora, GastoDeclarado.orden, GastoDeclarado.id))).scalars())
    return comp, decl


async def _repetidos_fuera(sesion: AsyncSession, r: Rendicion) -> dict[str, str]:
    """{clave del comprobante: «en la rendición de Nombre (R-003)»} de las OTRAS rendiciones."""
    filas = (await sesion.execute(
        select(ComprobanteGasto, Rendicion.id, Rendicion.usuario_id)
        .join(Rendicion, Rendicion.id == ComprobanteGasto.rendicion_id)
        .where(ComprobanteGasto.rendicion_id != r.id, ComprobanteGasto.numero != "")
    )).all()
    nombres = {x["id"]: x["nombre_completo"] for x in await cuentas()} if filas else {}
    salida = {}
    for c, rid, uid in filas:
        nombre = nombres.get(uid, "")
        k = calc.clave_comprobante({"serie": c.serie, "numero": c.numero, "ruc": c.ruc})
        if k:
            salida[k] = f"en la rendición de {nombre} (R-{rid:03d})"
    return salida


async def _base(sesion: AsyncSession, r: Rendicion, ajuste: dict, comision: ComisionServicio) -> dict:
    """Lo propio de UNA rendición para el cálculo: datos vigentes, días, parámetros, comprobantes y otros
    gastos sin comprobante (sin la movilidad, que es de la comisión)."""
    semana = await semana_de(r.semana_id)
    memo_doc = await _memorando(r.documento_id)
    datos, origen = efectivos(_publicos(r.datos), semana)
    dias = calc.dias_de(datos.get("fecha_inicio") or "", datos.get("fecha_fin") or "")
    rec = (comision.datos or {}).get("recibido_viaticos")
    rec_com = None
    if isinstance(rec, dict) and rec.get("valor") is not None:
        quien = await cuenta(rec.get("por"))
        rec_com = {"valor": rec["valor"], "por": calc.nombre_corto(quien["nombres"], quien["nombre_completo"]) if quien else ""}
    parametros = calc.parametros_vigentes(ajuste, r.parametros or {}, len(dias), comision=rec_com,
                                          memorando=_recibido_de_memorando(memo_doc))
    comp, otros = await _hijos(sesion, r.id)
    return {"semana": semana, "memo_doc": memo_doc, "datos": datos, "origen": origen, "dias": dias, "parametros": parametros,
            "comprobantes": [_comprobante(c) for c in comp], "otros": [_declarado(x) for x in otros]}


async def _personas(sesion: AsyncSession, r: Rendicion, comision: ComisionServicio, ajuste: dict, liq: dict,
                    dias: list[str], nombres: dict[int, str]) -> list[dict]:
    """Cada comisionado de la comisión con lo que limita su movilidad: su tope diario y de declaración jurada,
    lo gastado con comprobante y sin él por día, y en TOTAL lo que le permite el 30 % de lo recibido
    (`tope_total`, céntimos) y sus otros gastos sin comprobante (`otros_total`). La rendición propia, con su
    liquidación ya hecha; las demás, con sus comprobantes y otros gastos (2026-10-18)."""
    def persona(nombre: str, liq_: dict, dias_: list[str]) -> dict:
        base = calc.centimos(liq_["recibido"]) or calc.centimos(liq_["asignado"])
        return {"nombre": nombre, "tope": calc.centimos(liq_["tope_diario"]), "tope_dj": calc.centimos(liq_["tope_dj"]),
                "a": {d["fecha"]: calc.centimos(d["subtotal_a"]) for d in liq_["dias"]},
                "otros": {d["fecha"]: calc.centimos(d["otros_dj"]) for d in liq_["dias"]}, "dias": dias_,
                "tope_total": int(base * float(liq_["pct_dj_max"] or 0) / 100), "otros_total": calc.centimos(liq_["otros_dj"])}

    personas = [persona(nombres.get(r.usuario_id, ""), liq, dias)]
    for o in await rc.rendiciones_de(sesion, comision.id):
        if o.id == r.id:
            continue
        b = await _base(sesion, o, ajuste, comision)
        lo = calc.liquidar(b["dias"], b["comprobantes"], b["otros"], b["parametros"])
        personas.append(persona(nombres.get(o.usuario_id, ""), lo, b["dias"]))
    return personas


async def vista(sesion: AsyncSession, r: Rendicion, completa: bool = True, quien: Usuario | None = None,
                extra: dict | None = None) -> dict:
    """La rendición con todo lo vinculado VIGENTE, su liquidación (con la movilidad de su comisión y la
    que alcanza a todos) y sus controles. Si se pasa `extra`, deja en él `personas` (lo que limita la
    movilidad de cada comisionado, para «Ajustar a lo sugerido»)."""
    u = await cuenta(r.usuario_id)
    comision = await rc.comision_de(sesion, r)
    ajuste = await parametros_despacho(sesion)
    b = await _base(sesion, r, ajuste, comision)
    semana, datos, origen, dias, parametros = b["semana"], b["datos"], b["origen"], b["dias"], b["parametros"]
    memo = _ficha_memorando(b["memo_doc"])
    nombres = await _nombres_cortos()
    tramos = [_tramo(t, nombres) for t in await rc.tramos_de(sesion, comision.id)]
    comprobantes = b["comprobantes"]
    declarados = tramos + b["otros"]
    objetivos = (comision.datos or {}).get("dj_objetivo") or {}
    liq = calc.liquidar(dias, comprobantes, declarados, parametros, objetivos)
    personas = await _personas(sesion, r, comision, ajuste, liq, dias, nombres)
    compartida = calc.movilidad_compartida(personas, dias)
    if extra is not None:
        extra["personas"] = personas
    for d in liq["dias"]:
        x = compartida.get(d["fecha"])
        d["compartida"] = calc.soles(x["monto"]) if x else d["sugerida"]
        d["explicacion"] = x["texto"] if x else ""
        d["limita"] = x["limita"] if x else ""
    comisionado = {"id": u["id"] if u else None, "nombre": (u["nombre_completo"] if u else "") or "",
                   "corto": calc.nombre_corto(u["nombres"], u["nombre_completo"]) if u else "",
                   "cargo": (u["cargo"] if u else "") or "", "dni": (u["dni"] if u else "") or "",
                   "usuario": u["usuario"] if u else ""}
    limite = limite_para_rendir(datos.get("fecha_fin") or "", parametros["plazo_dias_habiles"]["valor"])
    hoy = date.today().isoformat()
    anexos = [_anexo(a) for a in await _anexos(sesion, r.id)]
    controles = calc.controles(
        {**datos, "estado": r.estado, "dni": comisionado["dni"], "cargo": comisionado["cargo"], "memorando": memo},
        liq, comprobantes, declarados, parametros, hoy, limite,
        await _repetidos_fuera(sesion, r) if completa else None, anexos,
    )
    pdf = await _ruta_pdf(sesion, r)
    miembros = []
    for o in await rc.rendiciones_de(sesion, comision.id):
        miembros.append({"id": o.id, "codigo": f"R-{o.id:03d}", "usuario_id": o.usuario_id, "estado": o.estado,
                         "etiqueta_estado": calc.ETIQUETA_ESTADO.get(o.estado, o.estado),
                         "comisionado": nombres.get(o.usuario_id, ""), "accesible": quien is None or _puede(o, quien)})
    rec = (comision.datos or {}).get("recibido_viaticos")
    salida = {
        "id": r.id, "codigo": f"R-{r.id:03d}", "estado": r.estado, "etiqueta_estado": calc.ETIQUETA_ESTADO.get(r.estado, r.estado),
        "version": r.version, "observacion": r.observacion,
        "comisionado": comisionado, "semana": semana, "memorando": memo,
        "datos": datos, "datos_propios": _publicos(r.datos), "origen_datos": origen,
        "parametros": parametros, "parametros_propios": r.parametros or {},
        "dias": dias, "comprobantes": comprobantes, "declarados": declarados, "anexos": anexos,
        "liquidacion": liq, "controles": controles, "limite": limite,
        "errores": sum(1 for c in controles if c["nivel"] == "error"),
        "unidad": str((r.datos or {}).get("unidad_organica") or ""),
        "documento": {"pdf": bool(pdf and pdf.exists()), "nombre": pdf.name if pdf else "",
                      "generado_en": r.generado_en.isoformat() if r.generado_en else None},
        "creado_en": r.creado_en.isoformat() if r.creado_en else None,
        "presentada_en": r.presentada_en.isoformat() if r.presentada_en else None,
        "creado_por": nombres.get(r.creado_por, "") if r.creado_por != r.usuario_id else "",
        "comision": {
            "id": comision.id, "clave": comision.clave, "carpeta": f"rendiciones/{comision.carpeta}", "miembros": miembros,
            "dj_objetivo": objetivos,
            "recibido": ({"valor": rec.get("valor"), "por": nombres.get(rec.get("por") or 0, "")} if isinstance(rec, dict) else None),
            "ultimo_cambio": await rc.ultimo_lote(sesion, comision.id) if completa else None,
            "bloqueada_por": await rc.bloqueada_por(sesion, comision.id),
        },
    }
    # ¿El PDF refleja lo de hoy? Se compara la huella de lo que se compondría ahora con la del último
    # generado (2026-10-18: un PDF viejo impreso por error es una rendición mal presentada).
    salida["nombre_archivo"] = _nombre_archivo(salida)
    al_dia = bool(salida["documento"]["pdf"]) and (r.datos or {}).get("_huella") == huella(salida)
    salida["documento"]["al_dia"] = al_dia
    salida["avance"] = calc.avance(datos, comprobantes, declarados, controles, salida["documento"])
    salida["pendientes"] = [x.strip(" -•\t") for x in str(datos.get("pendientes") or "").splitlines() if x.strip(" -•\t")]
    if parametros["recibido_viaticos"]["origen"] == "supuesto":
        # Lo que no consta queda PENDIENTE (2026-10-18): el importe recibido varía en cada comisión.
        salida["pendientes"].append("Anotar el importe recibido de viáticos (no consta en el memorando ni se registró)")
    return salida


def huella(v: dict) -> str:
    """La huella del documento que se compondría con la vista `v` (metadata + contenido)."""
    meta, contenido = rendicion_tex.componer(v)
    return hashlib.sha256((meta + contenido).encode()).hexdigest()[:16]


def carpeta_rendicion(carpeta_comision: str, rid: int, usuario: str) -> str:
    """La carpeta de una rendición, relativa a RENDICIONES_DIR: `<carpeta de la comisión>/R-NNN_<usuario>`
    (2026-10-18, Edison: los archivos de las rendiciones FUERA de la carpeta de la Semana, en una carpeta
    propia de la entidad, general para toda comisión). Pura."""
    return f"{carpeta_comision}/R-{rid:03d}_{sanear(usuario or 'comisionado', 30).lower() or 'comisionado'}"


async def _carpeta(sesion: AsyncSession, r: Rendicion) -> Path:
    """Donde viven los sustentos, el PDF y el Excel de la rendición: `<RENDICIONES_DIR>/AAAA/<comisión>/
    R-NNN_<usuario>/` (`comprobantes/`, `anexos/`, `documento/`). Nunca dentro del repositorio ni de la
    carpeta de la Semana (la Semana enlaza a sus rendiciones; no hay copias).

    La primera vez se FIJA en la rendición (`datos._carpeta`, relativa a RENDICIONES_DIR): cambiar después
    las fechas o el lugar no deja archivos huérfanos, y mudar RENDICIONES_DIR no obliga a tocar la base.
    Una carpeta ABSOLUTA guardada antes (la propuesta anterior, dentro de la Semana) se sigue usando
    mientras exista; si ya no existe (se movió), se re-ancla en la estructura nueva, como `carpetas.py`
    hace con `MDD_DOCUMENTOS`."""
    guardada = str((r.datos or {}).get("_carpeta") or "")
    if guardada:
        p = Path(guardada)
        if not p.is_absolute():
            return raiz_rendiciones() / p
        if p.exists():
            return p
    c = await rc.comision_de(sesion, r)
    u = await cuenta(r.usuario_id)
    relativa = carpeta_rendicion(c.carpeta, r.id, (u["usuario"] if u else "") or "comisionado")
    r.datos = {**(r.datos or {}), "_carpeta": relativa}
    return raiz_rendiciones() / relativa


async def _ruta_pdf(sesion: AsyncSession, r: Rendicion) -> Path | None:
    """El PDF generado; si su ruta guardada ya no existe (se movió la carpeta), el del mismo nombre en
    `documento/` de la carpeta vigente."""
    if not r.documento_pdf:
        return None
    p = Path(r.documento_pdf)
    if p.exists():
        return p
    otra = (await _carpeta(sesion, r)) / "documento" / p.name
    return otra if otra.exists() else p


# --- Parámetros de la entidad --------------------------------------------------------------------------


#: A nombre de quién van los comprobantes (DI 37-2025-DF-DGA-CR: «a nombre del Congreso de la República»).
#: En 2026 salen con el RUC de la Cámara de Diputados: es un dato de la entidad (Administración), nunca un
#: RUC literal en el código.
TEXTOS = {"a_nombre_de": "Congreso de la República", "ruc_a_nombre": ""}


def institucion_de(ajuste: dict) -> dict:
    return {k: str(ajuste.get(k) or v) for k, v in TEXTOS.items()}


@router.get("/parametros")
async def ver_parametros(u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    _equipo(u)
    ajuste = await parametros_despacho(sesion)
    return {"parametros": calc.parametros_vigentes(ajuste, {}, 0), "fabrica": calc.FABRICA, "institucion": institucion_de(ajuste),
            "estados": calc.ETIQUETA_ESTADO, "conceptos": {k: v[1] for k, v in calc.CONCEPTOS.items()},
            "secciones": {k: v[0] for k, v in calc.CONCEPTOS.items()}, "tipos": calc.TIPOS_COMPROBANTE}


@router.get("/equipo")
async def equipo(u: Usuario = Depends(usuario_actual)) -> list[dict]:
    """Las cuentas activas del equipo (sin invitados), para elegir al comisionado al crear una rendición: por
    «identidad.v1», así responde igual dentro de Qillqa y sola (antes la web pedía /api/admin/equipo de Qillqa)."""
    _equipo(u)
    return [{"id": c["id"], "nombre_completo": c["nombre_completo"], "rol": c["rol"], "cargo": c["cargo"]}
            for c in sorted(await cuentas(), key=lambda c: c["nombre_completo"]) if c["activo"] and c["rol"] != "invitado"]


class CambioParametros(BaseModel):
    valores: dict = Field(default_factory=dict)    # {clave: número | null}
    fuentes: dict = Field(default_factory=dict)    # {clave: «de dónde sale»}
    textos: dict = Field(default_factory=dict)     # {a_nombre_de, ruc_a_nombre}


@router.put("/parametros")
async def guardar_parametros(datos: CambioParametros, u: Usuario = Depends(usuario_actual),
                             sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    if not _admin(u):
        raise HTTPException(403, "Los parámetros de la entidad los cambia Administración.")
    actual = await parametros_despacho(sesion)
    for clave, valor in datos.textos.items():
        if clave not in TEXTOS:
            raise HTTPException(422, f"Dato desconocido: {clave}.")
        v = str(valor or "").strip()[:200]
        if clave == "ruc_a_nombre" and v and not re.match(r"^\d{11}$", v):
            raise HTTPException(422, "El RUC tiene 11 dígitos.")
        if v:
            actual[clave] = v
        else:
            actual.pop(clave, None)
    for clave, valor in datos.valores.items():
        if clave not in calc.CLAVES_PARAMETROS:
            raise HTTPException(422, f"Parámetro desconocido: {clave}.")
        if valor in (None, ""):
            actual.pop(clave, None)
        else:
            try:
                numero = float(str(valor).replace(",", "."))
            except ValueError:
                raise HTTPException(422, f"«{calc.FABRICA[clave]['etiqueta']}» debe ser un número.")
            if numero < 0:
                raise HTTPException(422, "Los parámetros no pueden ser negativos.")
            actual[clave] = {"valor": numero, "fuente": str(datos.fuentes.get(clave) or "Ajuste de la entidad (Administración)")[:300]}
    fila = await sesion.get(AjusteRendicion, AJUSTE)
    if fila is None:
        sesion.add(AjusteRendicion(clave=AJUSTE, valor=actual))
    else:
        fila.valor = actual
    await sesion.commit()
    return {"parametros": calc.parametros_vigentes(actual, {}, 0), "institucion": institucion_de(actual)}


# --- Lista, resumen y alta ----------------------------------------------------------------------------


@router.get("")
async def listar(semana_id: int | None = None, todas: bool = False, u: Usuario = Depends(usuario_actual),
                 sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """Las rendiciones de la cuenta (el administrador ve todas con `todas=true`), con su total,
    saldo, controles por corregir y plazo."""
    _equipo(u)
    q = select(Rendicion).order_by(Rendicion.creado_en.desc())
    if not (_admin(u) and todas):
        # Las suyas y las que hizo como encargado para un compañero.
        q = q.where((Rendicion.usuario_id == u.id) | (Rendicion.creado_por == u.id))
    if semana_id:
        q = q.where(Rendicion.semana_id == semana_id)
    salida = []
    for r in (await sesion.execute(q)).scalars():
        v = await vista(sesion, r, completa=False)
        liq = v["liquidacion"]
        salida.append({
            "id": r.id, "codigo": v["codigo"], "estado": r.estado, "etiqueta_estado": v["etiqueta_estado"],
            "comisionado": v["comisionado"]["nombre"], "usuario_id": r.usuario_id,
            "semana": v["semana"], "memorando": (v["memorando"] or {}).get("numero"),
            "inicio": v["datos"].get("fecha_inicio") or "", "fin": v["datos"].get("fecha_fin") or "",
            "recibido": liq["recibido"], "reconocido": liq["reconocido"], "saldo": liq["saldo"],
            "comprobantes": len(v["comprobantes"]), "errores": v["errores"],
            "avance": v["avance"], "pendientes": len(v["pendientes"]),
            "avisos": sum(1 for c in v["controles"] if c["nivel"] == "aviso"),
            "limite": v["limite"], "vencida": bool(v["limite"] and calc.corre_plazo(r.estado)
                                                   and date.today().isoformat() > v["limite"]),
            # Para agrupar por comisión en la lista (2026-10-18: «la lista parece duplicada»).
            "comision_id": v["comision"]["id"], "lugar": v["datos"].get("lugar") or "",
        })
    return {"rendiciones": salida, "admin": _admin(u), "yo": u.id}


@router.get("/resumen")
async def resumen(semana_id: int | None = None, u: Usuario = Depends(usuario_actual),
                  sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """El resumen de la entidad: cada comisionado de la semana con lo recibido, lo rendido y el saldo, y
    los totales. El administrador ve a todos; los demás, solo su fila."""
    _equipo(u)
    q = select(Rendicion).order_by(Rendicion.id)
    if semana_id:
        q = q.where(Rendicion.semana_id == semana_id)
    if not _admin(u):
        q = q.where((Rendicion.usuario_id == u.id) | (Rendicion.creado_por == u.id))
    filas, tot = [], {k: 0 for k in ("recibido", "con_comprobante", "dj", "reconocido", "exceso", "saldo")}
    for r in (await sesion.execute(q)).scalars():
        v = await vista(sesion, r, completa=False)
        liq = v["liquidacion"]
        fila = {"id": r.id, "codigo": v["codigo"], "comisionado": v["comisionado"]["nombre"], "estado": r.estado,
                "etiqueta_estado": v["etiqueta_estado"], "semana": (v["semana"] or {}).get("codigo"),
                **{k: liq[k] for k in tot}, "pct_dj": liq["pct_dj"], "errores": v["errores"]}
        for k in tot:
            tot[k] += calc.centimos(liq[k])
        filas.append(fila)
    faltan = await _faltan(sesion, semana_id, filas) if (semana_id and _admin(u)) else []
    return {"filas": filas, "totales": {k: calc.soles(v) for k, v in tot.items()}, "faltan": faltan}


def faltan_de(responsables: list[dict], con_rendicion: set[str], cuentas: dict[str, int]) -> list[dict]:
    """Quiénes del equipo de la semana aún no tienen rendición (2026-10-18). `responsables`: los del
    expediente [{nombre, rol}]; el congresista no rinde (su apoyo logístico no está sujeto a rendición:
    Directiva N.° 08-2022-DGA/CR, 4.2). Se compara por nombre sin tildes. Pura."""
    salida = []
    for p in responsables or []:
        nombre, rol = str(p.get("nombre") or "").strip(), _plano(str(p.get("rol") or ""))
        if not nombre or any(x in rol for x in ("diputad", "congresist", "senador")):
            continue
        clave = _plano(nombre)
        if clave not in con_rendicion:
            salida.append({"nombre": nombre, "rol": str(p.get("rol") or ""), "usuario_id": cuentas.get(clave)})
    return salida


AJUSTE_NO_RINDEN = "no_rinden"   # antes, «rendicion_no_rinden» de la plataforma


async def _no_rinden(sesion: AsyncSession) -> dict:
    fila = await sesion.get(AjusteRendicion, AJUSTE_NO_RINDEN)
    return dict(fila.valor or {}) if fila else {}


async def _faltan(sesion: AsyncSession, semana_id: int, filas: list[dict]) -> list[dict]:
    semanas = opcional("semanas.v1")
    responsables = await semanas.responsables(semana_id) if semanas is not None else None
    if responsables is None:
        return []
    por_nombre = {_plano(x["nombre_completo"] or ""): x["id"] for x in await cuentas()}
    # Quien estuvo en la semana sin viáticos (la directiva da viáticos a DOS servidores por congresista,
    # DI 37-2025-DF-DGA-CR, 6.1.2) no rinde: Administración lo marca y deja de figurar como pendiente.
    exentos = set((await _no_rinden(sesion)).get(str(semana_id)) or [])
    return faltan_de(responsables, {_plano(f["comisionado"]) for f in filas} | exentos, por_nombre)


class NoRinde(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    quitar: bool = False


@router.post("/semana/{semana_id}/no-rinde")
async def marcar_no_rinde(semana_id: int, datos: NoRinde, u: Usuario = Depends(usuario_actual),
                          sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """«No le corresponde rendir esta semana» (no recibió viáticos). Solo Administración."""
    if not _admin(u):
        raise HTTPException(403, "Lo marca Administración.")
    actual = await _no_rinden(sesion)
    lista = set(actual.get(str(semana_id)) or [])
    (lista.discard if datos.quitar else lista.add)(_plano(datos.nombre))
    actual[str(semana_id)] = sorted(lista)
    fila = await sesion.get(AjusteRendicion, AJUSTE_NO_RINDEN)
    if fila is None:
        sesion.add(AjusteRendicion(clave=AJUSTE_NO_RINDEN, valor=actual))
    else:
        fila.valor = actual
    await sesion.commit()
    return {"no_rinden": actual[str(semana_id)]}


class NuevaRendicion(BaseModel):
    semana_id: int | None = None
    documento_id: int | None = None
    usuario_id: int | None = None
    datos: dict = Field(default_factory=dict)


@router.post("", status_code=201)
async def crear(nueva: NuevaRendicion, u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """Una rendición nueva. Con semana, las fechas, el lugar y el motivo salen de ella (vigentes). La
    movilidad es de la comisión: si la comisión aún no tiene tramos, se proponen desde las actividades de
    la semana; si ya los tiene (los registró un compañero), la rendición nueva los usa tal cual.

    Dos formas de trabajar (2026-10-18): cada quien hace la suya, o un ENCARGADO hace las de todos los de la
    comisión eligiendo el comisionado; quien la crea para otro la ve y la edita como si fuera suya."""
    _equipo(u)
    usuario_id = nueva.usuario_id or u.id
    otro = await cuenta(usuario_id)
    if otro is None or (usuario_id != u.id and (not otro["activo"] or otro["rol"] == "invitado")):
        raise HTTPException(422, "La cuenta del comisionado no existe o no está activa.")
    if nueva.semana_id:
        if await semana_de(nueva.semana_id) is None:
            raise HTTPException(422, "La semana no existe.")
        ya = (await sesion.execute(select(Rendicion.id).where(Rendicion.semana_id == nueva.semana_id,
                                                               Rendicion.usuario_id == usuario_id))).scalar()
        if ya:
            raise HTTPException(409, {"codigo": "ya_existe", "id": ya, "mensaje": "Ya tiene una rendición de esa semana."})
    if nueva.documento_id and await _memorando(nueva.documento_id) is None:
        raise HTTPException(422, "El memorando no existe.")
    datos = {k: str(v).strip()[:LARGO_DATO.get(k, 400)] for k, v in (nueva.datos or {}).items()
             if k in CLAVES_DATOS and k != "dj_objetivo" and v not in (None, "")}
    for k in ("fecha_inicio", "fecha_fin"):
        if datos.get(k) and not re.match(r"^\d{4}-\d{2}-\d{2}$", datos[k]):
            raise HTTPException(422, "Las fechas van como AAAA-MM-DD.")
    if datos.get("fecha_inicio") and datos.get("fecha_fin") and datos["fecha_fin"] < datos["fecha_inicio"]:
        raise HTTPException(422, "La fecha de fin es anterior a la de inicio.")
    r = Rendicion(usuario_id=usuario_id, semana_id=nueva.semana_id, documento_id=nueva.documento_id, estado="borrador",
                  datos=datos, parametros={}, creado_por=u.id)
    sesion.add(r)
    await sesion.flush()
    c = await rc.comision_de(sesion, r)
    if nueva.semana_id and not await rc.tramos_de(sesion, c.id):
        lote = rc.Lote(sesion, c, u.id, "Tramos propuestos desde las actividades de la semana", r.id)
        await _proponer(sesion, r, c, lote, reemplazar=False)
    await sesion.commit()
    return {"id": r.id}


# --- Una rendición ------------------------------------------------------------------------------------


@router.get("/{rid}")
async def ver(rid: int, u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    r = await _rendicion(sesion, rid, u)
    v = await vista(sesion, r, quien=u)
    v["memorandos_sugeridos"] = await _memorandos_sugeridos(sesion, v["semana"], r.documento_id)
    v["actividades"] = await _actividades(sesion, r.semana_id)
    v["puede_administrar"] = _admin(u)
    v["institucion"] = institucion_de(await parametros_despacho(sesion))
    # Quiénes de la semana aún no tienen rendición: el encargado la crea desde aquí, sin salir.
    v["comision"]["faltan"] = (await _faltan(sesion, r.semana_id, [{"comisionado": m["comisionado_completo"]} for m in await _miembros_completos(sesion, v)])
                               if r.semana_id else [])
    await sesion.commit()   # la comisión, si se creó al leer
    return v


def ficha_comparar(v: dict, propia: bool) -> dict:
    """Lo que se compara de una rendición entre los comisionados de la misma comisión (2026-10-18, Edison:
    «una vista que compare lado a lado a los comisionados»): día por día, los comprobantes por concepto (con
    cuántos hay), la movilidad (la misma), lo reconocido y el saldo; y los totales. Pura."""
    liq = v["liquidacion"]
    cuantos: dict[str, dict[str, int]] = {}
    for c in v["comprobantes"]:
        f = str(c.get("fecha") or "")[:10]
        cuantos.setdefault(f, {})
        cuantos[f][c.get("concepto") or ""] = cuantos[f].get(c.get("concepto") or "", 0) + 1
    return {
        "id": v["id"], "codigo": v["codigo"], "estado": v["estado"], "etiqueta_estado": v["etiqueta_estado"],
        "comisionado": v["comisionado"]["corto"] or v["comisionado"]["nombre"], "nombre": v["comisionado"]["nombre"],
        "propia": propia,
        "dias": [{"fecha": d["fecha"], "por_concepto": d["por_concepto"], "subtotal_a": d["subtotal_a"],
                  "movilidad": d["movilidad"], "otros_dj": d["otros_dj"], "dj": d["dj"], "reconocido": d["reconocido"],
                  "exceso": d["exceso"], "saldo": d["saldo"], "cuantos": cuantos.get(d["fecha"], {})} for d in liq["dias"]],
        "totales": {k: liq[k] for k in ("rendido", "reconocido", "recibido", "saldo", "con_comprobante", "dj", "exceso",
                                         "pct_dj", "pct_dj_max", "pct_dj_ok")}
                   | {"comprobantes": len(v["comprobantes"]), "errores": v["errores"],
                      "pasajes": liq["pasajes"]["rendido"], "otros": liq["otros"]["rendido"]},
    }


@router.get("/{rid}/comparar")
async def comparar(rid: int, u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """Los comisionados de la misma comisión lado a lado, para la última revisión y para levantar las
    observaciones de la oficina que recibe. Solo los que la cuenta puede ver (`_puede`); de los demás, el
    nombre."""
    r = await _rendicion(sesion, rid, u)
    c = await rc.comision_de(sesion, r)
    nombres = await _nombres_cortos()
    personas, sin_acceso = [], []
    for o in await rc.rendiciones_de(sesion, c.id):
        if not _puede(o, u):
            sin_acceso.append(nombres.get(o.usuario_id, ""))
            continue
        personas.append(ficha_comparar(await vista(sesion, o, completa=False), o.id == r.id))
    personas.sort(key=lambda x: (not x["propia"], x["id"]))
    await sesion.commit()
    return {"personas": personas, "sin_acceso": sin_acceso}


async def _miembros_completos(sesion: AsyncSession, v: dict) -> list[dict]:
    salida = []
    for m in v["comision"]["miembros"]:
        x = await cuenta(m["usuario_id"])
        salida.append({**m, "comisionado_completo": x["nombre_completo"] if x else ""})
    return salida


async def _actividades(sesion: AsyncSession, semana_id: int | None) -> list[dict]:
    semanas = opcional("semanas.v1")
    if not semana_id or semanas is None:
        return []
    return await semanas.actividades(semana_id)


async def _memorandos_sugeridos(sesion: AsyncSession, semana: dict | None, actual: int | None) -> list[dict]:
    """Los memorandos que hablan de viáticos (los más recientes primero; con semana, los de los 45
    días previos a su inicio). Para vincular con un toque."""
    docs = opcional("documentos.v1")
    filas = await docs.recientes("memorando", 200) if docs is not None else []
    # El memorando que ya sustenta las rendiciones de OTRA semana no se sugiere para esta (ensayo del
    # 2026-10-18: el de la SR-01 aparecía también en la SR-02).
    otra = {doc for doc, sem in (await sesion.execute(select(Rendicion.documento_id, Rendicion.semana_id)
                                                       .where(Rendicion.documento_id.is_not(None)))).all()
            if semana and sem and sem != semana.get("id")}
    salida = []
    for d in filas:
        if d["id"] in otra:
            continue
        ficha = _ficha_memorando(d)
        texto = _plano(ficha["asunto"] + " " + str(d.get("referencia") or ""))
        if "viatic" not in texto and "pasaje" not in texto and "comision de servicio" not in texto:
            continue
        if semana and semana.get("inicio") and ficha["fecha"]:
            try:
                dias = (date.fromisoformat(semana["inicio"][:10]) - date.fromisoformat(ficha["fecha"])).days
            except ValueError:
                dias = 0
            if dias < -7 or dias > 45:
                continue
        if d["id"] != actual:
            salida.append(ficha)
        if len(salida) >= 8:
            break
    return salida


CLAVES_DATOS = ("fecha_inicio", "fecha_fin", "lugar", "motivo", "siaf", "comprobante_pago", "comprobante_pago_fecha",
                "solicitud_efectivo", "solicitud_efectivo_fecha", "fecha_rendicion", "lugar_firma", "unidad_organica",
                "dj_objetivo", "pendientes", "en_fisico",
                "inicio_confirmado")   # la ventana de inicio ya se respondió (2026-10-18)
#: Largo máximo de cada dato (los pendientes son una lista de renglones).
LARGO_DATO = {"pendientes": 2000}


class CambioRendicion(BaseModel):
    datos: dict | None = None            # solo las claves que cambian; "" o null las devuelve a lo vigente
    parametros: dict | None = None       # idem; null = rige el de la entidad
    semana_id: int | None = Field(default=None)
    documento_id: int | None = Field(default=None)
    quitar_semana: bool = False
    quitar_memorando: bool = False
    version_base: int | None = None


@router.put("/{rid}")
async def guardar(rid: int, cambio: CambioRendicion, u: Usuario = Depends(usuario_actual),
                  sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    r = await _rendicion(sesion, rid, u, bloquear=True)
    _editable(r, u)
    if cambio.version_base is not None and cambio.version_base != r.version:
        raise HTTPException(409, {"codigo": "rendicion_modificada", "mensaje": "Otra persona guardó antes: recargue para ver lo último."})
    if cambio.datos is not None:
        datos = dict(r.datos or {})
        for k, v in cambio.datos.items():
            if k not in CLAVES_DATOS:
                raise HTTPException(422, f"Dato desconocido: {k}.")
            if k == "dj_objetivo":
                # La DJ del día es de la COMISIÓN (la movilidad es compartida): se guarda allí, con constancia.
                c = await _movilidad_editable(sesion, r, u)
                if v not in (None, "", {}) and not isinstance(v, dict):
                    raise HTTPException(422, "dj_objetivo es {fecha: monto}.")
                lote = rc.Lote(sesion, c, u.id, "Fijar la DJ del día", r.id)
                lote.dato("dj_objetivo", {f: calc.soles(calc.centimos(m)) for f, m in (v or {}).items() if m not in (None, "")} or None)
                continue
            if v in (None, "") or v == {}:
                datos.pop(k, None)
            else:
                datos[k] = str(v).strip()[:LARGO_DATO.get(k, 400)]
        for k in ("fecha_inicio", "fecha_fin", "fecha_rendicion", "comprobante_pago_fecha", "solicitud_efectivo_fecha"):
            if datos.get(k) and not re.match(r"^\d{4}-\d{2}-\d{2}$", datos[k]):
                raise HTTPException(422, "Las fechas van como AAAA-MM-DD.")
        if datos.get("fecha_inicio") and datos.get("fecha_fin") and datos["fecha_fin"] < datos["fecha_inicio"]:
            raise HTTPException(422, "La fecha de fin es anterior a la de inicio.")
        r.datos = datos
    if cambio.parametros is not None:
        propios = dict(r.parametros or {})
        for k, v in cambio.parametros.items():
            if k not in calc.CLAVES_PARAMETROS:
                raise HTTPException(422, f"Parámetro desconocido: {k}.")
            if v in (None, ""):
                propios.pop(k, None)
            else:
                try:
                    propios[k] = float(str(v).replace(",", "."))
                except ValueError:
                    raise HTTPException(422, f"«{calc.FABRICA[k]['etiqueta']}» debe ser un número.")
        r.parametros = propios
    semana_antes = r.semana_id
    if cambio.quitar_semana:
        r.semana_id = None
    elif cambio.semana_id:
        if await semana_de(cambio.semana_id) is None:
            raise HTTPException(422, "La semana no existe.")
        r.semana_id = cambio.semana_id
    if r.semana_id != semana_antes:
        # Otra semana es otra comisión (con su propia movilidad compartida).
        r.comision_id = None
        await rc.comision_de(sesion, r)
    if cambio.quitar_memorando:
        r.documento_id = None
    elif cambio.documento_id:
        if await _memorando(cambio.documento_id) is None:
            raise HTTPException(422, "El memorando no existe.")
        r.documento_id = cambio.documento_id
    r.version += 1
    await sesion.commit()
    return await ver(rid, u, sesion)


class CambioEstado(BaseModel):
    estado: str
    observacion: str = ""


@router.post("/{rid}/estado")
async def cambiar_estado(rid: int, cambio: CambioEstado, u: Usuario = Depends(usuario_actual),
                         sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    r = await _rendicion(sesion, rid, u, bloquear=True)
    v = await vista(sesion, r)
    motivo = calc.puede_pasar(r.estado, cambio.estado, _admin(u), v["errores"])
    if motivo:
        raise HTTPException(409, motivo)
    if cambio.estado == "observada" and not cambio.observacion.strip():
        raise HTTPException(422, "Escriba qué hay que corregir.")
    r.estado = cambio.estado
    if cambio.estado == "observada":
        r.observacion = cambio.observacion.strip()[:2000]
    if cambio.estado == "presentada":
        r.presentada_en = datetime.now(timezone.utc)
    r.version += 1
    await sesion.commit()
    return await ver(rid, u, sesion)


@router.delete("/{rid}")
async def eliminar(rid: int, u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """Retira la rendición de la base. Sus fotos y documentos quedan en su carpeta (nada se borra del
    disco). Solo un borrador; el administrador, cualquiera."""
    r = await _rendicion(sesion, rid, u, bloquear=True)
    if r.estado != "borrador" and not _admin(u):
        raise HTTPException(409, "Solo se elimina una rendición en borrador.")
    await sesion.delete(r)
    await sesion.commit()
    return {"ok": True}


# --- Comprobantes -------------------------------------------------------------------------------------


class DatosComprobante(BaseModel):
    fecha: str = ""
    tipo: str = "boleta_electronica"
    serie: str = Field("", max_length=20)
    numero: str = Field("", max_length=30)
    ruc: str = Field("", max_length=11)
    proveedor: str = Field("", max_length=200)
    concepto: str = "almuerzo"
    importe: float | str = 0
    nota: str = Field("", max_length=500)


def _validar_comprobante(d: DatosComprobante) -> dict:
    if d.fecha and not re.match(r"^\d{4}-\d{2}-\d{2}$", d.fecha):
        raise HTTPException(422, "La fecha va como AAAA-MM-DD.")
    if d.tipo not in calc.TIPOS_COMPROBANTE:
        raise HTTPException(422, "Tipo de comprobante desconocido.")
    if d.concepto not in calc.CONCEPTOS:
        raise HTTPException(422, "Concepto desconocido.")
    if d.ruc and not re.match(r"^\d{11}$", d.ruc.strip()):
        raise HTTPException(422, "El RUC tiene 11 dígitos.")
    importe = calc.centimos(d.importe)
    if importe < 0:
        raise HTTPException(422, "El importe no puede ser negativo.")
    serie, numero = calc.partir_numero(d.serie, d.numero)   # «EB01-1586» en un solo campo → serie y número
    return {"fecha": d.fecha, "tipo": d.tipo, "serie": serie.strip().upper(), "numero": numero.strip(),
            "ruc": d.ruc.strip(), "proveedor": d.proveedor.strip(), "concepto": d.concepto,
            "importe": calc.soles(importe), "nota": d.nota.strip()}


async def _siguiente_orden(sesion: AsyncSession, modelo, rid: int) -> int:
    return ((await sesion.execute(select(func.max(modelo.orden)).where(modelo.rendicion_id == rid))).scalar() or 0) + 1


@router.post("/{rid}/comprobantes", status_code=201)
async def agregar_comprobante(rid: int, d: DatosComprobante, u: Usuario = Depends(usuario_actual),
                              sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    r = await _rendicion(sesion, rid, u)
    _editable(r, u)
    c = ComprobanteGasto(rendicion_id=rid, orden=await _siguiente_orden(sesion, ComprobanteGasto, rid), **_validar_comprobante(d))
    sesion.add(c)
    await sesion.commit()
    return _comprobante(c)


@router.put("/{rid}/comprobantes/{cid}")
async def cambiar_comprobante(rid: int, cid: int, d: DatosComprobante, u: Usuario = Depends(usuario_actual),
                              sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    r = await _rendicion(sesion, rid, u)
    _editable(r, u)
    c = await sesion.get(ComprobanteGasto, cid)
    if c is None or c.rendicion_id != rid:
        raise HTTPException(404, "Comprobante no encontrado.")
    for k, v in _validar_comprobante(d).items():
        setattr(c, k, v)
    await _nombrar_sustento(sesion, r, c)
    await sesion.commit()
    return _comprobante(c)


async def _nombrar_sustento(sesion: AsyncSession, r: Rendicion, c: ComprobanteGasto) -> None:
    """La foto que se subió sin datos (`foto_<huella>`) toma su nombre claro al completarse
    (`AAAAMMDD_SERIE-NUMERO_<huella>`); si otro comprobante comparte el archivo, se actualiza también."""
    if not c.archivo or not Path(c.archivo).name.startswith("foto_") or not (c.fecha and c.numero):
        return
    carpeta = await _carpeta(sesion, r)
    viejo = carpeta / c.archivo
    huella = viejo.stem.split("_")[-1]
    nuevo = viejo.with_name(nombre_sustento(c.fecha, c.serie, c.numero, huella, viejo.suffix))
    if not viejo.exists() or nuevo.exists():
        return
    viejo.rename(nuevo)
    relativo = str(nuevo.relative_to(carpeta))
    for otro in (await sesion.execute(select(ComprobanteGasto).where(ComprobanteGasto.rendicion_id == r.id,
                                                                      ComprobanteGasto.archivo == c.archivo))).scalars():
        otro.archivo = relativo
    c.archivo = relativo


@router.delete("/{rid}/comprobantes/{cid}")
async def quitar_comprobante(rid: int, cid: int, u: Usuario = Depends(usuario_actual),
                             sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    r = await _rendicion(sesion, rid, u)
    _editable(r, u)
    c = await sesion.get(ComprobanteGasto, cid)
    if c is None or c.rendicion_id != rid:
        raise HTTPException(404, "Comprobante no encontrado.")
    await sesion.delete(c)   # la foto queda en la carpeta: nada se borra del disco
    await sesion.commit()
    return {"ok": True}


def nombre_sustento(fecha: str, serie: str, numero: str, huella: str, ext: str) -> str:
    """`AAAAMMDD_SERIE-NUMERO_<huella>.ext` (o `foto_<huella>.ext` sin datos): se lee de un vistazo,
    se ordena por fecha y la huella del CONTENIDO evita guardar dos veces el mismo archivo. Pura."""
    num = sanear("-".join(x for x in (serie, numero) if x), 30)
    f = re.sub(r"\D", "", fecha or "")[:8]
    cabeza = "_".join(x for x in (f, num) if x) or "foto"
    return f"{cabeza}_{huella}{ext}"


def _guardar_archivo(carpeta: Path, nombre: str, contenido: bytes, sub: str = "comprobantes",
                     datos: dict | None = None) -> str:
    """La foto o el PDF en `comprobantes/` (o `anexos/`). Una foto grande se reduce (lado mayor 2000 px,
    JPEG): del celular llegan de 4 a 8 MB y para leer un comprobante sobra. Si el MISMO archivo (misma
    huella) ya está en la carpeta, se reutiliza: una foto con dos facturas se guarda una vez y la
    comparten los dos comprobantes (2026-10-18)."""
    ext = Path(nombre or "").suffix.lower() or ".jpg"
    if ext not in EXTENSIONES:
        raise HTTPException(422, "Suba una foto (JPG, PNG, WEBP, HEIC) o un PDF.")
    destino = carpeta / sub
    destino.mkdir(parents=True, exist_ok=True)
    huella = hashlib.sha256(contenido).hexdigest()[:10]
    ya = sorted(destino.glob(f"*_{huella}.*"))
    if ya:
        return str(ya[0].relative_to(carpeta))
    d = datos or {}
    if ext in (".jpg", ".jpeg", ".png", ".webp"):
        try:
            from io import BytesIO

            from PIL import Image, ImageOps

            img = ImageOps.exif_transpose(Image.open(BytesIO(contenido)))
            img.thumbnail((2000, 2000))
            salida = destino / nombre_sustento(d.get("fecha", ""), d.get("serie", ""), d.get("numero", ""), huella, ".jpg")
            img.convert("RGB").save(salida, "JPEG", quality=85)
            return str(salida.relative_to(carpeta))
        except Exception:  # noqa: BLE001 — si Pillow no la lee, se guarda tal cual
            pass
    salida = destino / nombre_sustento(d.get("fecha", ""), d.get("serie", ""), d.get("numero", ""), huella, ext)
    salida.write_bytes(contenido)
    return str(salida.relative_to(carpeta))


@router.post("/{rid}/comprobantes/{cid}/archivo")
async def subir_archivo(rid: int, cid: int, archivo: UploadFile = File(...), u: Usuario = Depends(usuario_actual),
                        sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    r = await _rendicion(sesion, rid, u)
    _editable(r, u)
    c = await sesion.get(ComprobanteGasto, cid)
    if c is None or c.rendicion_id != rid:
        raise HTTPException(404, "Comprobante no encontrado.")
    contenido = await archivo.read(MAX_ARCHIVO + 1)
    if len(contenido) > MAX_ARCHIVO:
        raise HTTPException(413, "El archivo pasa de 15 MB.")
    c.archivo = _guardar_archivo(await _carpeta(sesion, r), archivo.filename or "", contenido,
                                 datos={"fecha": c.fecha, "serie": c.serie, "numero": c.numero})
    await sesion.commit()
    return _comprobante(c)


@router.post("/{rid}/fotos", status_code=201)
async def subir_fotos(rid: int, archivos: list[UploadFile] = File(...), u: Usuario = Depends(usuario_actual),
                      sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """Varias fotos de una vez (desde el celular): un comprobante por foto, sin datos todavía. Se
    completan a mano o con el resultado del prompt, que las llena en el mismo orden."""
    r = await _rendicion(sesion, rid, u)
    _editable(r, u)
    carpeta = await _carpeta(sesion, r)
    orden = await _siguiente_orden(sesion, ComprobanteGasto, rid)
    creados = []
    for i, a in enumerate(archivos[:40]):
        contenido = await a.read(MAX_ARCHIVO + 1)
        if len(contenido) > MAX_ARCHIVO:
            raise HTTPException(413, f"{a.filename}: pasa de 15 MB.")
        # El nombre del archivo original va en el detalle: así se distinguen las fotos por completar.
        c = ComprobanteGasto(rendicion_id=rid, orden=orden + i, fecha="", importe=0, origen="foto",
                             nota=f"Archivo: {(a.filename or '')[:120]}" if a.filename else "")
        sesion.add(c)
        await sesion.flush()
        c.archivo = _guardar_archivo(carpeta, a.filename or "", contenido)
        creados.append(c)
    await sesion.commit()
    return {"comprobantes": [_comprobante(c) for c in creados]}


@router.get("/{rid}/comprobantes/{cid}/archivo")
async def ver_archivo(rid: int, cid: int, peticion: Request, u: Usuario = Depends(usuario_actual),
                      sesion: AsyncSession = Depends(obtener_sesion_rendicion)):
    r = await _rendicion(sesion, rid, u)
    c = await sesion.get(ComprobanteGasto, cid)
    if c is None or c.rendicion_id != rid or not c.archivo:
        raise HTTPException(404, "Sin archivo.")
    ruta = (await _carpeta(sesion, r)) / c.archivo
    if not ruta.exists():
        raise HTTPException(404, "El archivo ya no está en la carpeta.")
    tipo = "application/pdf" if ruta.suffix == ".pdf" else ("image/png" if ruta.suffix == ".png" else "image/jpeg")
    return enviar_archivo(ruta, ruta.name, tipo, peticion)


# --- Gastos declarados: los OTROS gastos sin comprobante (de la rendición) -----------------------------


class DatosDeclarado(BaseModel):
    clase: str = "movilidad"
    fecha: str = ""
    hora: str = Field("", max_length=5)
    desde: str = Field("", max_length=200)
    hasta: str = Field("", max_length=200)
    concepto: str = Field("", max_length=200)
    monto: float | str = 0


def _validar_declarado(d: DatosDeclarado) -> dict:
    if d.clase not in ("movilidad", "otro"):
        raise HTTPException(422, "Clase desconocida (movilidad u otro).")
    if d.fecha and not re.match(r"^\d{4}-\d{2}-\d{2}$", d.fecha):
        raise HTTPException(422, "La fecha va como AAAA-MM-DD.")
    if d.hora and not re.match(r"^\d{2}:\d{2}$", d.hora):
        raise HTTPException(422, "La hora va como HH:MM.")
    monto = calc.centimos(d.monto)
    if monto < 0:
        raise HTTPException(422, "El monto no puede ser negativo.")
    return {"clase": d.clase, "fecha": d.fecha, "hora": d.hora, "desde": d.desde.strip()[:200], "hasta": d.hasta.strip()[:200],
            "concepto": d.concepto.strip(), "monto": calc.soles(monto)}


def _texto_tramo(v: dict) -> str:
    return f"{calc.fecha_corta(v.get('fecha', ''))[:5]} {v.get('desde') or '¿?'} → {v.get('hasta') or '¿?'}"


@router.post("/{rid}/declarados", status_code=201)
async def agregar_declarado(rid: int, d: DatosDeclarado, u: Usuario = Depends(usuario_actual),
                            sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """Un gasto sin comprobante. Un tramo de movilidad (clase `movilidad`) va a la COMISIÓN, como
    `POST /{id}/tramos` (se acepta aquí para no romper a quien ya lo usaba)."""
    r = await _rendicion(sesion, rid, u)
    valores = _validar_declarado(d)
    if valores["clase"] == "movilidad":
        return await _agregar_tramo(sesion, r, u, valores)
    _editable(r, u)
    x = GastoDeclarado(rendicion_id=rid, orden=await _siguiente_orden(sesion, GastoDeclarado, rid), **valores)
    sesion.add(x)
    await sesion.commit()
    return _declarado(x)


async def _declarado_de(sesion: AsyncSession, rid: int, did: int) -> GastoDeclarado:
    x = await sesion.get(GastoDeclarado, did)
    if x is None or x.rendicion_id != rid or x.clase == "movilidad":
        raise HTTPException(404, "Gasto no encontrado (los tramos de movilidad se cambian en /tramos).")
    return x


@router.put("/{rid}/declarados/{did}")
async def cambiar_declarado(rid: int, did: int, d: DatosDeclarado, u: Usuario = Depends(usuario_actual),
                            sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    r = await _rendicion(sesion, rid, u)
    _editable(r, u)
    x = await _declarado_de(sesion, rid, did)
    for k, v in _validar_declarado(d).items():
        if k != "clase":
            setattr(x, k, v)
    await sesion.commit()
    return _declarado(x)


@router.delete("/{rid}/declarados/{did}")
async def quitar_declarado(rid: int, did: int, u: Usuario = Depends(usuario_actual),
                           sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    r = await _rendicion(sesion, rid, u)
    _editable(r, u)
    await sesion.delete(await _declarado_de(sesion, rid, did))
    await sesion.commit()
    return {"ok": True}


# --- Movilidad COMPARTIDA: los tramos de la comisión ------------------------------------------------


async def _agregar_tramo(sesion: AsyncSession, r: Rendicion, u: Usuario, valores: dict) -> dict:
    c = await _movilidad_editable(sesion, r, u)
    lote = rc.Lote(sesion, c, u.id, f"Agregar el tramo {_texto_tramo(valores)}", r.id)
    t = await lote.crear({k: v for k, v in valores.items() if k in rc.CAMPOS_TRAMO})
    await sesion.commit()
    return _tramo(t, await _nombres_cortos())


async def _tramo_de(sesion: AsyncSession, c: ComisionServicio, tid: int) -> TramoMovilidad:
    t = await sesion.get(TramoMovilidad, tid)
    if t is None or t.comision_id != c.id:
        raise HTTPException(404, "Tramo no encontrado (quizá otro de la comisión lo quitó: recargue).")
    return t


@router.post("/{rid}/tramos", status_code=201)
async def agregar_tramo(rid: int, d: DatosDeclarado, u: Usuario = Depends(usuario_actual),
                        sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """Un tramo de movilidad de la COMISIÓN: aparece en la rendición de todos los que viajaron juntos."""
    r = await _rendicion(sesion, rid, u)
    return await _agregar_tramo(sesion, r, u, {**_validar_declarado(d), "clase": "movilidad"})


@router.put("/{rid}/tramos/{tid}")
async def cambiar_tramo(rid: int, tid: int, d: DatosDeclarado, u: Usuario = Depends(usuario_actual),
                        sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """Corrige un tramo (ruta, hora, monto): el cambio se ve en todas las rendiciones de la comisión y
    queda constancia de quién lo hizo."""
    r = await _rendicion(sesion, rid, u)
    c = await _movilidad_editable(sesion, r, u)
    t = await _tramo_de(sesion, c, tid)
    valores = {k: v for k, v in _validar_declarado(d).items() if k in rc.CAMPOS_TRAMO}
    rc.Lote(sesion, c, u.id, f"Corregir el tramo {_texto_tramo(rc.ficha(t))}", r.id).cambiar(t, valores)
    await sesion.commit()
    return _tramo(t, await _nombres_cortos())


@router.delete("/{rid}/tramos/{tid}")
async def quitar_tramo(rid: int, tid: int, u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    r = await _rendicion(sesion, rid, u)
    c = await _movilidad_editable(sesion, r, u)
    t = await _tramo_de(sesion, c, tid)
    await rc.Lote(sesion, c, u.id, f"Quitar el tramo {_texto_tramo(rc.ficha(t))}", r.id).quitar(t)
    await sesion.commit()
    return {"ok": True}


async def _ajustar(sesion: AsyncSession, r: Rendicion, c: ComisionServicio, lote: rc.Lote | None,
                   fechas: set[str] | None = None) -> list[dict]:
    """Reparte en los tramos de cada día la DJ fijada o, si no hay, la movilidad que ALCANZA A TODOS los
    de la comisión (`movilidad_compartida`). Sin `lote`, solo SIMULA y devuelve el plan; con él, aplica."""
    extra: dict = {}
    v = await vista(sesion, r, completa=False, extra=extra)
    tramos = await rc.tramos_de(sesion, c.id)
    dias = [d for d in v["liquidacion"]["dias"] if not fechas or d["fecha"] in fechas]
    plan = calc.plan_ajuste(dias, [{"id": t.id, "fecha": t.fecha, "monto": float(t.monto or 0)} for t in tramos],
                            limites_dj(extra["personas"], {d["fecha"] for d in dias}, tramos, v["dias"]))
    if lote is not None:
        por_id = {t.id: t for t in tramos}
        for p in plan:
            for tid, monto in p["montos"]:
                lote.cambiar(por_id[tid], {"monto": monto})
    exp = {d["fecha"]: d.get("explicacion") or "" for d in dias}
    obj = {d["fecha"]: d.get("objetivo") for d in dias}
    return [{"fecha": p["fecha"], "antes": p["antes"], "despues": p["despues"], "cambia": p["cambia"],
             "motivo": p.get("motivo", ""), "explicacion": explicar_plan(p, exp.get(p["fecha"], ""), obj.get(p["fecha"]))}
            for p in plan]


def limites_dj(personas: list[dict], alcance: set[str], tramos: list, dias_comision: list[str]) -> list[dict]:
    """Lo que a cada comisionado le queda para la movilidad de los días que se ajustan, sin pasar el 30 % de lo
    recibido: su `tope_total` menos sus otros gastos sin comprobante y la movilidad de sus días que NO se tocan
    (`alcance`). Pura (los tramos, cualquier objeto con `fecha` y `monto`)."""
    salida = []
    for p in personas:
        suyos = set(p.get("dias") or dias_comision)
        fuera = sum(calc.centimos(t.monto) for t in tramos if t.fecha in suyos and t.fecha not in alcance)
        salida.append({"nombre": p["nombre"], "dias": sorted(suyos),
                       "disponible": p["tope_total"] - p["otros_total"] - fuera})
    return salida


def explicar_plan(p: dict, explicacion: str, objetivo) -> str:
    """La línea que explica el monto de un día del plan."""
    if p.get("motivo") == "pct":
        rec = p.get("recorte") or {}
        quien = f" de {rec['nombre']}" if rec.get("nombre") else ""
        return (f"{calc.texto_corto(calc.centimos(p['despues']))}: recortado para no pasar el 30 % de lo recibido{quien} "
                f"(le quedan {calc.texto_corto(calc.centimos(rec.get('disponible') or 0))} para la movilidad de estos días).")
    if p.get("motivo") == "fijada_tope":
        return (f"La DJ fijada ({calc.texto_corto(calc.centimos(objetivo))}) pasa lo que alcanza a todos: queda en "
                f"{calc.texto_corto(calc.centimos(p['despues']))}. {explicacion}").strip()
    if p.get("motivo") == "fijada":
        return f"{calc.texto_corto(calc.centimos(p['despues']))}: la DJ del día fijada para la comisión."
    return explicacion


async def _proponer(sesion: AsyncSession, r: Rendicion, c: ComisionServicio, lote: rc.Lote, reemplazar: bool) -> int:
    """Crea en la comisión los tramos que se deducen de las actividades de la semana (para los días sin
    tramos, o todos si `reemplazar`) y les reparte la movilidad sugerida."""
    if not r.semana_id:
        return 0
    v = await vista(sesion, r, completa=False)
    existentes = await rc.tramos_de(sesion, c.id)
    con_tramos = {t.fecha for t in existentes}
    if reemplazar:
        for t in existentes:
            await lote.quitar(t)
        con_tramos = set()
    dias = [d for d in v["dias"] if d not in con_tramos]
    nuevos = calc.tramos_desde_actividades(await _actividades(sesion, r.semana_id), dias)
    orden = await rc.siguiente_orden(sesion, c.id)
    for i, t in enumerate(nuevos):
        await lote.crear({"fecha": t["fecha"], "hora": t["hora"], "desde": t["desde"][:200], "hasta": t["hasta"][:200],
                          "monto": 0, "actividad": t["actividad"], "orden": orden + i})
    await sesion.flush()
    if nuevos:
        await _ajustar(sesion, r, c, lote, {t["fecha"] for t in nuevos})
    return len(nuevos)


class Vaciar(BaseModel):
    fecha: str | None = None   # un día; sin fecha, todos


@router.post("/{rid}/movilidad/vaciar")
async def vaciar(rid: int, datos: Vaciar, u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """Quita los tramos de movilidad de la comisión (de un día o todos). Se puede deshacer."""
    r = await _rendicion(sesion, rid, u, bloquear=True)
    c = await _movilidad_editable(sesion, r, u)
    lote = rc.Lote(sesion, c, u.id, f"Quitar los tramos del {calc.fecha_corta(datos.fecha)[:5]}" if datos.fecha else "Quitar todos los tramos", r.id)
    n = 0
    for t in await rc.tramos_de(sesion, c.id):
        if not datos.fecha or t.fecha == datos.fecha:
            await lote.quitar(t)
            n += 1
    r.version += 1
    await sesion.commit()
    return {"quitados": n, "rendicion": await ver(rid, u, sesion)}


async def _companeras(sesion: AsyncSession, r: Rendicion) -> list[Rendicion]:
    """Las OTRAS rendiciones de la misma comisión."""
    c = await rc.comision_de(sesion, r)
    return [o for o in await rc.rendiciones_de(sesion, c.id) if o.id != r.id]


@router.get("/{rid}/companeros")
async def companeros(rid: int, u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> list[dict]:
    """Quién más rindió la misma comisión y qué se le puede copiar (otros gastos sin comprobante, importes
    y topes, lugar de la firma, memorando). La movilidad no se copia: ya es la misma para todos."""
    r = await _rendicion(sesion, rid, u)
    salida = []
    for o in await _companeras(sesion, r):
        dueno = await cuenta(o.usuario_id)
        decl = list((await sesion.execute(select(GastoDeclarado).where(GastoDeclarado.rendicion_id == o.id, GastoDeclarado.clase == "otro"))).scalars())
        salida.append({"id": o.id, "codigo": f"R-{o.id:03d}", "comisionado": dueno["nombre_completo"] if dueno else "",
                       "tramos": 0, "otros": len(decl),
                       "parametros": len(o.parametros or {}), "lugar_firma": bool((o.datos or {}).get("lugar_firma")),
                       "memorando": bool(o.documento_id)})
    return salida


class Copiar(BaseModel):
    desde: int
    tramos: bool = False        # sin efecto desde el 2026-10-18: la movilidad es de la comisión
    otros: bool = False
    parametros: bool = False
    lugar_firma: bool = False
    memorando: bool = False     # vincular el mismo memorando (uno solo pidió los viáticos de todos)
    reemplazar: bool = True     # quitar antes los otros gastos propios


@router.post("/{rid}/copiar")
async def copiar(rid: int, datos: Copiar, u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """Copia de la rendición de un compañero de la MISMA comisión lo que suele ser igual: los otros gastos
    sin comprobante, los importes y topes ajustados, el lugar de la firma y el memorando. Los comprobantes
    NO (cada quien rinde los suyos) y la movilidad tampoco: ya es compartida."""
    r = await _rendicion(sesion, rid, u, bloquear=True)
    _editable(r, u)
    origen = next((o for o in await _companeras(sesion, r) if o.id == datos.desde), None)
    if origen is None:
        raise HTTPException(404, "Esa rendición no es de la misma comisión.")
    copiados = 0
    if datos.otros:
        if datos.reemplazar:
            for x in (await sesion.execute(select(GastoDeclarado).where(GastoDeclarado.rendicion_id == rid, GastoDeclarado.clase == "otro"))).scalars():
                await sesion.delete(x)
        orden = await _siguiente_orden(sesion, GastoDeclarado, rid)
        fuente = (await sesion.execute(select(GastoDeclarado).where(GastoDeclarado.rendicion_id == origen.id, GastoDeclarado.clase == "otro")
                                        .order_by(GastoDeclarado.fecha, GastoDeclarado.orden, GastoDeclarado.id))).scalars()
        for i, x in enumerate(fuente):
            sesion.add(GastoDeclarado(rendicion_id=rid, clase="otro", orden=orden + i, fecha=x.fecha, hora=x.hora, desde=x.desde,
                                      hasta=x.hasta, concepto=x.concepto, monto=x.monto, actividad=x.actividad))
            copiados += 1
    if datos.parametros and origen.parametros:
        r.parametros = {**(r.parametros or {}), **origen.parametros}
    if datos.memorando and origen.documento_id:
        r.documento_id = origen.documento_id
    if datos.lugar_firma and (origen.datos or {}).get("lugar_firma"):
        r.datos = {**(r.datos or {}), "lugar_firma": origen.datos["lugar_firma"]}
    r.version += 1
    await sesion.commit()
    return {"copiados": copiados, "rendicion": await ver(rid, u, sesion)}


class Proponer(BaseModel):
    reemplazar: bool = False


@router.post("/{rid}/movilidad/proponer")
async def proponer(rid: int, datos: Proponer, u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    r = await _rendicion(sesion, rid, u, bloquear=True)
    c = await _movilidad_editable(sesion, r, u)
    if not r.semana_id:
        raise HTTPException(422, "Vincule la semana de representación: sus actividades dan los tramos.")
    lote = rc.Lote(sesion, c, u.id, "Volver a proponer todos los tramos" if datos.reemplazar else "Proponer tramos de los días sin tramos", r.id)
    n = await _proponer(sesion, r, c, lote, datos.reemplazar)
    await sesion.commit()
    return {"creados": n, "rendicion": await ver(rid, u, sesion)}


class Ajustar(BaseModel):
    fecha: str | None = None   # un día; sin fecha, todos
    simular: bool = False      # solo decir qué haría (2026-10-18: «que diga en una línea qué hará antes»)


@router.post("/{rid}/movilidad/ajustar")
async def ajustar(rid: int, datos: Ajustar, u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """«Ajustar a lo sugerido»: en cada día, la DJ fijada o la movilidad que alcanza a todos, repartida en
    soles enteros entre sus tramos. Con `simular`, solo el plan (día, antes, después, por qué). Se puede
    deshacer (`POST /{id}/movilidad/deshacer`)."""
    r = await _rendicion(sesion, rid, u, bloquear=True)
    c = await _movilidad_editable(sesion, r, u)
    fechas = {datos.fecha} if datos.fecha else None
    if datos.simular:
        return {"plan": await _ajustar(sesion, r, c, None, fechas)}
    lote = rc.Lote(sesion, c, u.id, f"Ajustar a lo sugerido el {calc.fecha_corta(datos.fecha)[:5]}" if datos.fecha else "Ajustar a lo sugerido", r.id)
    plan = await _ajustar(sesion, r, c, lote, fechas)
    await sesion.commit()
    return {"tocados": lote.filas, "dias": sum(1 for p in plan if p["cambia"]), "plan": plan, "rendicion": await ver(rid, u, sesion)}


@router.post("/{rid}/movilidad/deshacer")
async def deshacer(rid: int, u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """Deshace el último cambio de la movilidad de la comisión (lo hiciera quien lo hiciera; queda constancia)."""
    r = await _rendicion(sesion, rid, u, bloquear=True)
    c = await _movilidad_editable(sesion, r, u)
    res = await rc.deshacer(sesion, c, u.id, r.id)
    if res["deshecho"] is None:
        raise HTTPException(409, "No hay nada que deshacer.")
    r.version += 1
    await sesion.commit()
    return {**res, "rendicion": await ver(rid, u, sesion)}


@router.get("/{rid}/movilidad/cambios")
async def cambios(rid: int, u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> list[dict]:
    """Quién cambió qué en la movilidad de la comisión, del más nuevo al más viejo."""
    r = await _rendicion(sesion, rid, u)
    c = await rc.comision_de(sesion, r)
    return await rc.historial(sesion, c.id)


class CambioComision(BaseModel):
    recibido_viaticos: float | str | None = None
    quitar_recibido: bool = False


@router.put("/{rid}/comision")
async def guardar_comision(rid: int, cambio: CambioComision, u: Usuario = Depends(usuario_actual),
                           sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """El importe recibido cuando es el MISMO para toda la comisión (cada rendición puede anotar el suyo,
    que manda). Queda constancia de quién lo anotó."""
    r = await _rendicion(sesion, rid, u, bloquear=True)
    _editable(r, u)
    c = await rc.comision_de(sesion, r)
    lote = rc.Lote(sesion, c, u.id, "Importe recibido para toda la comisión", r.id)
    if cambio.quitar_recibido:
        lote.dato("recibido_viaticos", None)
    elif cambio.recibido_viaticos not in (None, ""):
        monto = calc.centimos(cambio.recibido_viaticos)
        if monto <= 0:
            raise HTTPException(422, "El importe recibido debe ser mayor que cero.")
        lote.dato("recibido_viaticos", {"valor": calc.soles(monto), "por": u.id})
    r.version += 1
    await sesion.commit()
    return await ver(rid, u, sesion)


# --- Pegar el resultado del prompt de comprobantes ----------------------------------------------------


class Pegar(BaseModel):
    texto: str = Field(min_length=1, max_length=60000)


@router.post("/{rid}/pegar")
async def pegar(rid: int, datos: Pegar, u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """El bloque `comprobantes-gasto` pegado → vista previa: cada comprobante con su estado (nuevo,
    repetido, fuera de la comisión) y los tramos. No escribe nada (servicios/pegado)."""
    svc_pegado = opcional("pegado.v1")
    if svc_pegado is None:
        raise HTTPException(503, "Leer lo pegado no está disponible aquí.")
    r = await _rendicion(sesion, rid, u)
    le = svc_pegado.interpretar(datos.texto, ("comprobantes-gasto",))
    if not le.valido:
        raise HTTPException(422, {"codigo": "pegado_invalido", "errores": le.errores, "avisos": le.avisos,
                                  "formatos": [f for f in svc_pegado.formatos() if f["tipo"] == "comprobantes-gasto"]})
    v = await vista(sesion, r)
    dias = set(v["dias"])
    propias = {calc.clave_comprobante(c) for c in v["comprobantes"]} - {None}
    fuera = await _repetidos_fuera(sesion, r)
    sin_datos = sum(1 for c in v["comprobantes"] if not c["numero"] and not c["importe"])
    salida = []
    for i, c in enumerate(le.valores.get("comprobantes") or [], 1):
        k = calc.clave_comprobante(c)
        estado, motivo = "nuevo", ""
        if k and k in propias:
            estado, motivo = "repetido", "Ya está en esta rendición."
        elif k and k in fuera:
            estado, motivo = "repetido", f"Ya figura {fuera[k]}."
        elif dias and c.get("fecha") and c["fecha"] not in dias:
            estado, motivo = "fuera", "Fecha fuera de la comisión."
        elif c.get("legible") is False:
            estado, motivo = "dudoso", "La IA no lo leyó con certeza: revíselo."
        salida.append({"n": i, "datos": {**c, "documento": calc.documento_de(c)}, "estado": estado, "motivo": motivo,
                       "dudas": {kk.split(".", 1)[1]: vv for kk, vv in le.dudas.items() if kk.startswith(f"comprobantes[{i}].")}})
    tramos = [dict(t, clase="movilidad") for t in (le.valores.get("movilidad") or [])]
    return {"lectura": le.como_dict(), "comprobantes": salida, "tramos": tramos, "fotos_sin_datos": sin_datos, "resto": le.resto}


class Lote(BaseModel):
    comprobantes: list[DatosComprobante] = Field(default_factory=list)
    tramos: list[DatosDeclarado] = Field(default_factory=list)
    emparejar: bool = True       # llenar primero las fotos subidas sin datos, en orden
    texto: str = Field("", max_length=60000)   # el pegado, para la constancia


@router.post("/{rid}/lote", status_code=201)
async def lote(rid: int, datos: Lote, u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """Agrega de una vez lo aceptado del pegado. Con `emparejar`, cada comprobante leído llena la
    siguiente foto subida sin datos (mismo orden en que se subieron y se leyeron)."""
    r = await _rendicion(sesion, rid, u, bloquear=True)
    _editable(r, u)
    comp, _ = await _hijos(sesion, rid)
    libres = [c for c in sorted(comp, key=lambda c: (c.orden, c.id)) if c.origen == "foto" and not c.numero and not float(c.importe or 0)] if datos.emparejar else []
    orden = await _siguiente_orden(sesion, ComprobanteGasto, rid)
    hechos = 0
    for i, d in enumerate(datos.comprobantes):
        valores = _validar_comprobante(d)
        if libres:
            c = libres.pop(0)
            for k, v in valores.items():
                setattr(c, k, v)
            c.origen = "pegado"
        else:
            sesion.add(ComprobanteGasto(rendicion_id=rid, orden=orden + i, origen="pegado", **valores))
        hechos += 1
    if datos.tramos:
        # Los tramos van a la movilidad COMPARTIDA de la comisión.
        c = await _movilidad_editable(sesion, r, u)
        lote_m = rc.Lote(sesion, c, u.id, f"Pegar {len(datos.tramos)} tramo(s) leídos por la IA", r.id)
        for t in datos.tramos:
            await lote_m.crear({k: v for k, v in _validar_declarado(t).items() if k in rc.CAMPOS_TRAMO})
    await sesion.commit()
    pegado = opcional("pegado.v1")
    if datos.texto and pegado is not None:
        # La constancia de lo pegado la guarda quien guarda los pegados (después: es un registro, no parte del lote).
        await pegado.constancia(u.id, "comprobantes-gasto", datos.texto,
                                {"comprobantes": hechos, "tramos": len(datos.tramos)}, f"rend:{rid}")
    return {"agregados": hechos, "tramos": len(datos.tramos), "rendicion": await ver(rid, u, sesion)}


# --- Documento y Excel --------------------------------------------------------------------------------


def _nombre_archivo(v: dict) -> str:
    """«RV-SR-02_Nombre-Apellido» o, sin semana, «RV-CS-20261005_Nombre-Apellido» (comisión de servicio
    por su inicio): la convención de `servicios/nombres.py` (prefijo de qué es, la comisión y la persona;
    sin tildes ni espacios; lo lee nombrado.sh tal cual). El Excel añade `_liquidacion`."""
    comision = (v.get("semana") or {}).get("codigo")
    if not comision:
        inicio = re.sub(r"\D", "", str((v.get("datos") or {}).get("fecha_inicio") or ""))[:8]
        comision = f"CS-{inicio}" if inicio else v["codigo"]
    return f"RV-{comision}_{sanear(v['comisionado']['nombre'], 40) or 'comisionado'}"


@router.post("/{rid}/documento")
async def generar_documento(rid: int, u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """Compone los Anexos 3 y 4 con el marco y los compila (build.sh). Se puede generar con controles
    pendientes (es un borrador para revisar); lo que falta sale como renglón para llenar a mano."""
    r = await _rendicion(sesion, rid, u, bloquear=True)
    v = await vista(sesion, r)
    carpeta = (await _carpeta(sesion, r)) / "documento"
    resultado = await rendicion_tex.generar(carpeta, v)
    if not resultado.exito or resultado.ruta_pdf is None:
        raise HTTPException(500, resultado.mensaje)
    r.documento_pdf = str(resultado.ruta_pdf)
    r.generado_en = datetime.now(timezone.utc)
    r.datos = {**(r.datos or {}), "_huella": huella(v)}
    # El Excel acompaña al PDF en la misma carpeta (para quien lo pida en papel o por correo).
    try:
        (carpeta / f"{v['nombre_archivo']}_liquidacion.xlsx").write_bytes(rendicion_excel.bytes_de(v))
    except Exception:  # noqa: BLE001 — el Excel no impide el PDF
        pass
    await sesion.commit()
    return await ver(rid, u, sesion)


@router.get("/{rid}/documento.pdf")
async def ver_documento(rid: int, peticion: Request, u: Usuario = Depends(usuario_actual),
                        sesion: AsyncSession = Depends(obtener_sesion_rendicion)):
    r = await _rendicion(sesion, rid, u)
    ruta = await _ruta_pdf(sesion, r)
    if ruta is None or not ruta.exists():
        raise HTTPException(404, "Aún no se generó el documento.")
    return enviar_archivo(ruta, ruta.name, "application/pdf", peticion)


@router.get("/{rid}/liquidacion.xlsx")
async def liquidacion_excel(rid: int, u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> Response:
    r = await _rendicion(sesion, rid, u)
    v = await vista(sesion, r, completa=False)
    nombre = f"{_nombre_archivo(v)}_liquidacion.xlsx"
    return Response(rendicion_excel.bytes_de(v), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"', "Cache-Control": "private, no-cache"})


# --- Anexos: lo que acompaña y no se rinde (boleto aéreo, recibo de devolución) ----------------------

CLASES_ANEXO = {"boleto": "Boleto aéreo", "devolucion": "Recibo de devolución del saldo", "otro": "Otro sustento"}


@router.post("/{rid}/anexos", status_code=201)
async def agregar_anexo(rid: int, clase: str = Form("otro"), descripcion: str = Form("", max_length=200),
                        archivo: UploadFile = File(...), u: Usuario = Depends(usuario_actual),
                        sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    r = await _rendicion(sesion, rid, u, bloquear=True)
    _editable(r, u)
    if clase not in CLASES_ANEXO:
        raise HTTPException(422, "Clase de anexo desconocida (boleto, devolucion u otro).")
    contenido = await archivo.read(MAX_ARCHIVO + 1)
    if len(contenido) > MAX_ARCHIVO:
        raise HTTPException(413, "El archivo pasa de 15 MB.")
    ruta = _guardar_archivo(await _carpeta(sesion, r), archivo.filename or "", contenido, sub="anexos",
                            datos={"serie": clase})
    a = AnexoRendicion(rendicion_id=rid, clase=clase, descripcion=descripcion.strip() or CLASES_ANEXO[clase], archivo=ruta)
    sesion.add(a)
    await sesion.commit()
    return _anexo(a)


@router.get("/{rid}/anexos/{aid}/archivo")
async def ver_anexo(rid: int, aid: int, peticion: Request, u: Usuario = Depends(usuario_actual),
                    sesion: AsyncSession = Depends(obtener_sesion_rendicion)):
    r = await _rendicion(sesion, rid, u)
    a = await sesion.get(AnexoRendicion, aid)
    if a is None or a.rendicion_id != rid or not a.archivo:
        raise HTTPException(404, "Sin archivo.")
    ruta = (await _carpeta(sesion, r)) / a.archivo
    if not ruta.exists():
        raise HTTPException(404, "El archivo ya no está en la carpeta.")
    tipo = "application/pdf" if ruta.suffix == ".pdf" else ("image/png" if ruta.suffix == ".png" else "image/jpeg")
    return enviar_archivo(ruta, ruta.name, tipo, peticion)


@router.delete("/{rid}/anexos/{aid}")
async def quitar_anexo(rid: int, aid: int, u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    r = await _rendicion(sesion, rid, u)
    _editable(r, u)
    a = await sesion.get(AnexoRendicion, aid)
    if a is None or a.rendicion_id != rid:
        raise HTTPException(404, "Anexo no encontrado.")
    await sesion.delete(a)   # el archivo queda en la carpeta: nada se borra del disco
    await sesion.commit()
    return {"ok": True}


@router.get("/semana/{semana_id}/equipo")
async def equipo_de_semana(semana_id: int, u: Usuario = Depends(usuario_actual), sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> dict:
    """Quién del equipo ya tiene rendición de esa semana (para el resumen y el acceso desde la semana)."""
    _equipo(u)
    filas = (await sesion.execute(select(Rendicion).where(Rendicion.semana_id == semana_id).order_by(Rendicion.id))).scalars().all()
    # La suya o, si es el encargado, la primera que hizo para un compañero (las demás, en pestañas).
    mia = next((x.id for x in filas if x.usuario_id == u.id), None) or next((x.id for x in filas if _puede(x, u)), None)
    return {"mia": mia, "total": len(filas)}


@router.get("/buscar/memorandos")
async def buscar_memorandos(q: str = Query("", max_length=80), u: Usuario = Depends(usuario_actual),
                            sesion: AsyncSession = Depends(obtener_sesion_rendicion)) -> list[dict]:
    """Memorandos por número o asunto, para vincular el que solicitó los viáticos."""
    _equipo(u)
    docs = opcional("documentos.v1")
    filas = await docs.recientes("memorando", 300) if docs is not None else []
    n = _plano(q)
    salida = []
    for d in filas:
        f = _ficha_memorando(d)
        if not n or n in _plano(f["numero"] + " " + f["asunto"]):
            salida.append(f)
        if len(salida) >= 20:
            break
    return salida


# --- En el mapa de relaciones (2026-10-18) -------------------------------------------------------------
# El Mapa (Qillqa) los pide por «rendiciones.v1» (servicios/rendicion_contrato.py) y arma él sus nodos.


async def rendiciones_visibles(sesion: AsyncSession, u: Usuario) -> list[dict]:
    """Las rendiciones que la cuenta puede ver, como las pide `grafo.unir_rendiciones` (Vínculos al modo
    Obsidian: Semana, memorando, comisionado y la otra rendición de la comisión). El invitado, ninguna."""
    if u.rol == "invitado":
        return []
    q = select(Rendicion)
    if not _admin(u):
        q = q.where((Rendicion.usuario_id == u.id) | (Rendicion.creado_por == u.id))
    filas = (await sesion.execute(q.order_by(Rendicion.id))).scalars().all()
    if not filas:
        return []
    usuarios = {x["id"]: x for x in await cuentas()}
    semanas = opcional("semanas.v1")
    fichas = await semanas.fichas({r.semana_id for r in filas if r.semana_id}) if semanas is not None else {}
    salida = []
    for r in filas:
        x = usuarios.get(r.usuario_id)
        s = fichas.get(r.semana_id) if r.semana_id else None
        salida.append({"id": r.id, "codigo": f"R-{r.id:03d}", "usuario_id": r.usuario_id,
                       "comisionado": (x["nombre_completo"] if x else "") or "",
                       "corto": calc.nombre_corto(x["nombres"], x["nombre_completo"]) if x else "",
                       "semana_id": r.semana_id, "documento_id": r.documento_id, "comision_id": r.comision_id,
                       "estado": calc.ETIQUETA_ESTADO.get(r.estado, r.estado),
                       "titulo": f"{s['codigo']} · {s['tema']}" if s else "Comisión de servicio"})
    return salida


async def sustentos_de_rendicion(sesion: AsyncSession, rid: int) -> dict | None:
    """Los sustentos de una rendición para su mapa local: {comprobantes (cuántos), anexos, pdf (nombre o '')}."""
    r = await sesion.get(Rendicion, rid)
    if r is None:
        return None
    n = (await sesion.execute(select(func.count()).select_from(ComprobanteGasto).where(ComprobanteGasto.rendicion_id == rid))).scalar() or 0
    anexos = [{"id": a.id, "descripcion": a.descripcion, "archivo": a.archivo} for a in await _anexos(sesion, rid)]
    pdf = await _ruta_pdf(sesion, r)
    return {"comprobantes": int(n), "anexos": anexos, "pdf": pdf.name if pdf and pdf.exists() else ""}
