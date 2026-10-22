"""Lo que Rendición de cuentas ofrece a los demás módulos: la capacidad «rendiciones.v1» y el resolutor de
«rendicion» (proyecto Yupay; fase 10.2b de docs/plataforma/propuesta-repositorios.md, 2026-10-20).

La aprovecha el Mapa de relaciones (Qillqa): con Rendición, las rendiciones que la cuenta puede ver y los sustentos
de una salen en el mapa; sin ella, no. Cada operación abre su propia sesión: quien la usa no ve sus tablas. Las
etiquetas («rend:12») la nombran por referencia («rendicion:rendicion:12»).
"""
from __future__ import annotations

FUNCIONES = ("visibles", "sustentos")


async def visibles(usuario) -> list[dict]:
    """Las rendiciones que la cuenta puede ver, como las une el mapa (`grafo.unir_rendiciones`)."""
    from yupay.api import rendiciones_visibles
    from yupay.db import SesionRendicion

    async with SesionRendicion() as sesion:
        return await rendiciones_visibles(sesion, usuario)


async def sustentos(rendicion_id: int) -> dict | None:
    """{comprobantes (cuántos), anexos [{id, descripcion, archivo}], pdf (nombre o '')} o None si no existe."""
    from yupay.api import sustentos_de_rendicion
    from yupay.db import SesionRendicion

    async with SesionRendicion() as sesion:
        return await sustentos_de_rendicion(sesion, rendicion_id)


class _RendicionesV1:
    """Resuelve cada nombre al usarlo y rechaza lo que no está en la lista (el contrato se cumple)."""

    def __getattr__(self, nombre: str):
        if nombre in FUNCIONES:
            return globals()[nombre]
        raise AttributeError(f"«{nombre}» no es parte de «rendiciones.v1» (servicios/rendicion_contrato.py)")

    def __dir__(self):
        return sorted(FUNCIONES)


V1 = _RendicionesV1()


async def resolver_rendicion(ident: str) -> dict | None:
    """«rendicion:rendicion:<id>» → {titulo («Rendición R-003 — Nombre (SR-02)»), estado, enlace}."""
    from yupay.modelos import Rendicion
    from yupay import rendicion as calc
    from yupay.comision import cuenta, semana_de
    from yupay.db import SesionRendicion

    if not ident.isdigit():
        return None
    async with SesionRendicion() as sesion:
        r = await sesion.get(Rendicion, int(ident))
    if r is None:
        return None
    u = await cuenta(r.usuario_id)
    s = await semana_de(r.semana_id)
    return {"titulo": f"Rendición R-{r.id:03d} — {(u['nombre_completo'] if u else '')}" + (f" ({s['codigo']})" if s else ""),
            "estado": calc.ETIQUETA_ESTADO.get(r.estado, r.estado), "enlace": f"/rendiciones/{r.id}"}
