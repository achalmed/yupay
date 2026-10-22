"""tests/test_fronteras.py — Yupay solo usa lo suyo, Tiqsi y sus dependencias declaradas: nada de Qillqa (`app.`)
ni de otro proyecto de la plataforma. Así funciona igual dentro de Qillqa que sola."""
import ast
from pathlib import Path

PAQUETE = Path(__file__).resolve().parents[1] / "yupay"
TERCEROS = {"fastapi", "sqlalchemy", "pydantic", "pydantic_settings", "jwt", "PIL", "pillow_heif", "starlette", "tiqsi",
            "cv2", "numpy", "multipart", "openpyxl"}


def _importados(archivo: Path) -> set[str]:
    raiz = set()
    for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            raiz |= {a.name.split(".")[0] for a in nodo.names}
        elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
            raiz.add(nodo.module.split(".")[0])
    return raiz


def test_solo_usa_lo_suyo_tiqsi_y_sus_dependencias():
    import sys
    estandar = set(sys.stdlib_module_names) | {"__future__"}
    faltas = {f"{p.name}: {m}" for p in PAQUETE.glob("*.py") for m in _importados(p)
              if m not in estandar and m not in TERCEROS and m != "yupay"}
    assert not faltas, sorted(faltas)
