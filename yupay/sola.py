"""Rendición de cuentas SOLA: sin Qillqa y sin la base documental, con el anfitrión mínimo de Tiqsi (proyecto Yupay;
fase 10.2b de docs/plataforma/propuesta-repositorios.md, 2026-10-20). Es el arranque que tendrá Yupay en su repositorio.

    RENDICION_DATABASE_URL=postgresql+asyncpg://…/yupay  RENDICIONES_DIR=…  JWT_SECRET=<32 o más caracteres> \\
      .venv/bin/uvicorn yupay.sola:app --port 8031

Su página la da RENDICION_WEB (la carpeta construida con `npx vite build --config vite.rendicion.config.ts`).
Las cuentas viven en RENDICION_CUENTAS (por omisión <RENDICIONES_DIR>/cuentas.json) y se crean con
`python -m tiqsi.minimo cuenta <archivo> <usuario> --rol administrador --nombre … --nombres … --dni …`. Sin la Semana
de representación, el memorando, el pegado ni los feriados, esas partes no se ofrecen. Lo demás —rendiciones,
comprobantes, movilidad compartida, liquidación, controles, Excel y el PDF de los Anexos 3 y 4 con su propio marco
(RENDICION_TOKENS: los colores de Unancha; RENDICION_PERFIL: el titular, si lo hay)— funciona completo con lo suyo.
"""
from __future__ import annotations

import os

from tiqsi.minimo import crear_app

from yupay.config import config, raiz
from yupay.manifiesto import MANIFIESTO

if not config.rendicion_database_url:
    raise SystemExit("Rendición sola necesita su base: RENDICION_DATABASE_URL.")

app = crear_app([MANIFIESTO], nombre="Rendición de cuentas", secreto=config.jwt_secret,
                cuentas=os.environ.get("RENDICION_CUENTAS") or raiz() / "cuentas.json",
                # Su página: la cáscara mínima de Tiqsi web con Rendición (frontend/vite.rendicion.config.ts).
                web=os.environ.get("RENDICION_WEB") or None)
