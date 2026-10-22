"""La configuración PROPIA de Rendición de cuentas (proyecto Yupay; fase 10.2b de
docs/plataforma/propuesta-repositorios.md, 2026-10-20).

Lee las mismas variables que Qillqa (RENDICIONES_DIR, MDD_DOCUMENTOS, MDD_RUTA, DATABASE_URL) más la suya,
RENDICION_DATABASE_URL (vacía: la base documental, como hasta hoy; cuando la base se separe, la de Yupay). No
depende de `app.config`: viaja con el módulo cuando salga a su repositorio. `app.config.raiz_rendiciones()` sigue
para los scripts; tests/test_fronteras.py comprueba que las dos digan lo mismo.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class ConfigRendicion(BaseSettings):
    database_url: str = "postgresql+asyncpg://qillqa:qillqa@db:5432/qillqa"
    rendicion_database_url: str = ""
    # Sus carpetas: RENDICIONES_DIR o, si falta, la hermana `rendiciones/` del archivo documental.
    rendiciones_dir: str = ""
    mdd_documentos: str = ""
    mdd_ruta: str = "/framework"
    # Su marco (rendicion_marco): el perfil de la institución (el titular; RENDICION_PERFIL o el del marco documental,
    # MDD_PERFIL) y los colores de Unancha (RENDICION_TOKENS, ISR_TOKENS o <IDENTIDAD_TOKENS>/colors.json).
    rendicion_perfil: str = ""
    mdd_perfil: str = ""
    rendicion_tokens: str = ""
    isr_tokens: str = ""
    identidad_tokens: str = ""
    # Firma de las sesiones cuando corre SOLA (app/rendicion_sola.py); dentro de Qillqa, la sesión es de Qillqa.
    jwt_secret: str = ""


config = ConfigRendicion()


def raiz() -> Path:
    """La carpeta de las rendiciones."""
    if config.rendiciones_dir:
        return Path(config.rendiciones_dir)
    documentos = Path(config.mdd_documentos) if config.mdd_documentos else Path(config.mdd_ruta) / "documentos"
    return documentos.parent / "rendiciones"


def url_base() -> str:
    """La URL de su base: RENDICION_DATABASE_URL o, mientras no se separe, la documental."""
    return config.rendicion_database_url or config.database_url


def perfil() -> Path | None:
    """La carpeta del perfil de la institución (perfil-despacho.tex), si hay una."""
    for c in (config.rendicion_perfil, config.mdd_perfil):
        if c and (Path(c) / "perfil-despacho.tex").is_file():
            return Path(c)
    return None


def colores() -> Path | None:
    """El colors.json de Unancha, si hay uno."""
    for c in (config.rendicion_tokens, config.isr_tokens,
              str(Path(config.identidad_tokens) / "colors.json") if config.identidad_tokens else ""):
        if c and Path(c).is_file():
            return Path(c)
    return None
