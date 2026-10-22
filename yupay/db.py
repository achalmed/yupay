"""La base de Rendición de cuentas: su motor, su sesión y la preparación de sus tablas (proyecto Yupay; fase 10.2b,
2026-10-20). Con RENDICION_DATABASE_URL, su base propia (nace al arrancar si falta); sin ella, la documental.

Separar sus datos de la base documental es una orden del módulo (simula por omisión; tiqsi.sql.separar verifica
cada tabla y nunca toca el origen). Lee el origen de DATABASE_URL y el destino de RENDICION_DATABASE_URL:

    python -m yupay.db separar             # qué copiaría (filas y huella por tabla)
    python -m yupay.db separar --aplicar   # copia, verifica y trae los ajustes viejos
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from yupay.config import url_base

motor = create_async_engine(url_base(), pool_pre_ping=True)
SesionRendicion = async_sessionmaker(motor, expire_on_commit=False)

# Migraciones ligeras e idempotentes (antes en main.py): lo que `create_all` no altera en tablas ya existentes.
MIGRACIONES = (
    # Movilidad compartida (2026-10-18): cada rendición apunta a su comisión.
    "ALTER TABLE rendiciones ADD COLUMN IF NOT EXISTS comision_id integer REFERENCES rendicion_comisiones(id) ON DELETE SET NULL",
    "CREATE INDEX IF NOT EXISTS ix_rendiciones_comision_id ON rendiciones (comision_id)",
)
# Los ajustes que vivían en `ajustes` de la plataforma pasan a los del módulo, una vez (fase 10.2b, 2026-10-20). Solo
# si esa tabla está en la misma base (en una base propia no hay nada que copiar).
COPIAR_AJUSTES = (
    "INSERT INTO rendicion_ajustes (clave, valor) "
    "SELECT CASE clave WHEN 'rendicion_parametros' THEN 'parametros' ELSE 'no_rinden' END, valor FROM ajustes "
    "WHERE despacho_id = 1 AND clave IN ('rendicion_parametros', 'rendicion_no_rinden') ON CONFLICT (clave) DO NOTHING"
)


async def obtener_sesion_rendicion() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia de FastAPI: una sesión de la base de Rendición, siempre cerrada."""
    async with SesionRendicion() as sesion:
        yield sesion


class SinSeparar(SystemExit):
    """Su base propia está vacía y la documental aún tiene las rendiciones: arrancar así empezaría un módulo vacío."""


async def _sin_separar() -> bool:
    """¿Su base es otra, está vacía y la documental aún tiene las rendiciones? Solo si DATABASE_URL está definida (sola, no)."""
    import os

    from tiqsi.sql import sin_separar

    from yupay.config import config

    if not config.rendicion_database_url or "DATABASE_URL" not in os.environ:
        return False
    return await sin_separar(config.rendicion_database_url, config.database_url, ('rendiciones',))


async def preparar() -> None:
    """Su base (si falta), sus tablas, sus migraciones, sus ajustes y la movilidad compartida (idempotente). Se NIEGA a arrancar sobre su
    base propia vacía si la documental aún tiene sus datos (separe primero; tiqsi.sql.sin_separar)."""
    from tiqsi.sql import crear_base_si_falta

    from yupay.modelos import BaseRendicion
    from yupay import comision as rendicion_comision

    await crear_base_si_falta(motor.url)
    if await _sin_separar():
        raise SinSeparar("La base propia está vacía y la documental aún tiene las rendiciones: sepárela primero "
                         "(python -m yupay.db separar --aplicar).")
    async with motor.begin() as conexion:
        await conexion.run_sync(BaseRendicion.metadata.create_all)
        for sql in MIGRACIONES:
            await conexion.execute(text(sql))
        if (await conexion.execute(text("SELECT to_regclass('ajustes')"))).scalar():
            await conexion.execute(text(COPIAR_AJUSTES))
    async with SesionRendicion() as sesion:
        await rendicion_comision.migrar(sesion)


async def separar(aplicar: bool = False) -> dict:
    """Sus tablas, de la base documental (DATABASE_URL) a la suya (RENDICION_DATABASE_URL). Con `aplicar`, además, los
    ajustes que aún vivieran en `ajustes` de la plataforma (una base de producción que nunca arrancó este código)."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from tiqsi.sql import crear_base_si_falta, separar as separar_tablas

    from yupay.modelos import BaseRendicion
    from yupay.config import config

    if not config.rendicion_database_url:
        raise SystemExit("Falta RENDICION_DATABASE_URL (la base propia de Rendición).")
    if aplicar:
        await crear_base_si_falta(motor.url)
    plan = await separar_tablas(config.database_url, config.rendicion_database_url, BaseRendicion.metadata, aplicar=aplicar)
    if aplicar:
        origen = create_async_engine(config.database_url)
        try:
            async with origen.connect() as o:
                viejos = ((await o.execute(text(
                    "SELECT clave, valor FROM ajustes WHERE despacho_id = 1 AND clave IN "
                    "('rendicion_parametros', 'rendicion_no_rinden')"))).all()
                    if (await o.execute(text("SELECT to_regclass('ajustes')"))).scalar() else [])
        finally:
            await origen.dispose()
        nombres = {"rendicion_parametros": "parametros", "rendicion_no_rinden": "no_rinden"}
        async with motor.begin() as d:
            for clave, valor in viejos:
                await d.execute(text("INSERT INTO rendicion_ajustes (clave, valor) VALUES (:c, CAST(:v AS jsonb)) "
                                     "ON CONFLICT (clave) DO NOTHING"),
                                {"c": nombres[clave], "v": __import__("json").dumps(valor)})
    return plan


def _principal(argv: list[str]) -> int:
    import argparse
    import asyncio

    from tiqsi.sql import ErrorDeSeparacion

    p = argparse.ArgumentParser(prog="python -m yupay.db",
                                description="La base propia de Rendición de cuentas.")
    sub = p.add_subparsers(dest="orden", required=True)
    s = sub.add_parser("separar", help="sus tablas a su base (simula sin --aplicar)")
    s.add_argument("--aplicar", action="store_true")
    a = p.parse_args(argv)
    try:
        plan = asyncio.run(separar(a.aplicar))
    except ErrorDeSeparacion as e:
        print(f"[error] {e}")
        return 1
    for tabla, d in plan.items():
        print(f"  {tabla:<24} {d['filas']:>6} filas  {d['huella'][:12]}")
    print("Copiado y verificado." if a.aplicar else "Simulación: nada se copió (--aplicar para hacerlo).")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_principal(sys.argv[1:]))
