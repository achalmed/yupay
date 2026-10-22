"""El manifiesto de Rendición de cuentas (proyecto Yupay; fase 10.2b de docs/plataforma/propuesta-repositorios.md,
2026-10-20): el mismo dentro de Qillqa (app/plataforma.py) y, cuando arranque sola, con el anfitrión mínimo.

Necesita solo la identidad (la da cualquier anfitrión, también el mínimo con que arranca sola: app/rendicion_sola.py).
Su PDF lo compone su propio marco (app/rendicion_marco). Aprovecha la Semana de representación («semanas.v1»: fechas, lugar, actividades y responsables), el memorando de viáticos
(«documentos.v1»), la lectura de lo pegado («pegado.v1») y los feriados («calendario.v1»): sin ellos, esas partes
no se ofrecen y lo demás funciona.
"""
from __future__ import annotations

from tiqsi import Manifiesto

from yupay import api as rendiciones
from yupay import contrato as rendicion_contrato, db as rendicion_db

VERSION = "0.1.0"


async def _preparar_base(_anfitrion) -> None:
    """Sus tablas, sus migraciones y sus ajustes (idempotente)."""
    await rendicion_db.preparar()


MANIFIESTO = Manifiesto(
    id="rendicion", nombre="Rendición de cuentas", version=VERSION, contrato="^0.1",
    routers=[rendiciones.router], prefijos=("/api/rendiciones",),
    ofrece={"rendiciones.v1": rendicion_contrato.V1}, resolutores={"rendicion": rendicion_contrato.resolver_rendicion},
    necesita=("identidad.v1",),
    aprovecha=("semanas.v1", "documentos.v1", "pegado.v1", "calendario.v1"),
    al_arrancar=[_preparar_base],
)
