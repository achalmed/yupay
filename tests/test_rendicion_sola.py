"""tests/test_rendicion_sola.py — Rendición de cuentas arranca SOLA, con el anfitrión mínimo de Tiqsi, sin Qillqa ni la
base documental (yupay/sola.py; nació en Qillqa el 2026-10-20). Sin base de datos: lo
que necesita la base se prueba en vivo contra una vacía (qillqa/scripts/verde.sh sola-rendicion).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SECRETO = "r" * 40


def _entorno_limpio(tmp_path) -> dict:
    """Solo lo que Rendición necesita: ni DATABASE_URL de Qillqa ni nada del despacho."""
    return {"HOME": os.environ.get("HOME", "/tmp"), "PATH": os.environ.get("PATH", ""),
            "RENDICION_DATABASE_URL": "postgresql+asyncpg://nadie:nada@127.0.0.1:1/yupay_prueba",
            "RENDICIONES_DIR": str(tmp_path / "rendiciones"), "JWT_SECRET": SECRETO}


def test_sola_no_carga_nada_de_qillqa(tmp_path):
    codigo = ("import sys, json; import yupay.sola as m; "
              "print(json.dumps({'ajenos': sorted(x for x in sys.modules if x == 'app' or x.startswith('app.')), "
              "'informe': m.app.state.anfitrion.informe(), 'capacidades': m.app.state.anfitrion.capacidades.ofrecidas()}))")
    r = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, env=_entorno_limpio(tmp_path),
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    datos = json.loads(r.stdout.strip().splitlines()[-1])
    assert datos["ajenos"] == []                                    # nada de Qillqa
    assert datos["informe"] == [{"id": "rendicion", "nombre": "Rendición de cuentas", "version": "0.1.0"}]
    # Ni el marco, ni la semana, ni el memorando, ni el pegado, ni los feriados: lo suyo y la identidad.
    assert set(datos["capacidades"]) == {"identidad.v1", "rendiciones.v1"}


def test_sola_sin_su_base_no_arranca(tmp_path):
    entorno = {k: v for k, v in _entorno_limpio(tmp_path).items() if k != "RENDICION_DATABASE_URL"}
    r = subprocess.run([sys.executable, "-c", "import yupay.sola"], cwd=RAIZ, env=entorno,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode != 0 and "RENDICION_DATABASE_URL" in r.stderr


def test_sola_atiende_con_su_propia_sesion(tmp_path):
    """La aplicación sola, sin arrancar (no hay base aquí): sus rutas y su inicio de sesión."""
    from fastapi.testclient import TestClient
    from tiqsi import Manifiesto
    from tiqsi.minimo import Cuentas, crear_app

    from yupay.manifiesto import MANIFIESTO

    cuentas = tmp_path / "cuentas.json"
    Cuentas(cuentas).crear("ana", "clave-larga-1", "administrador", "Ana Pérez")
    copia = Manifiesto(**{**MANIFIESTO.__dict__, "al_arrancar": []})          # sin preparar la base
    c = TestClient(crear_app([copia], nombre="Rendición de cuentas", secreto=SECRETO, cuentas=cuentas))
    assert c.get("/api/health").json()["anfitrion"] == "Rendición de cuentas"
    assert c.get("/api/rendiciones").status_code == 401
    assert c.post("/api/auth/login", json={"usuario": "ana", "clave": "clave-larga-1"}).json()["token"]
    rutas = {x.path for x in c.app.routes}
    assert {"/api/rendiciones", "/api/rendiciones/{rid}", "/api/rendiciones/{rid}/liquidacion.xlsx"} <= rutas
