"""El MARCO de Yupay: la base LaTeX propia de Rendición de cuentas (fase 10.2b de docs/plataforma/
propuesta-repositorios.md §3.5, 2026-10-20). Sus anexos ya no dependen del marco de Gestión documental.

    latex/yupay.cls             la base (metadatos, colores, tipografía, página, idioma, perfil)
    latex/yupay-rendicion.cls   el formulario de la rendición de viáticos (Anexos 3 y 4)
    latex/yupay-rendicion.sty   su esqueleto (cabeceras, tablas, firmas)
    latex/rendicion-viaticos.tex  el maestro; latex/prueba/ trae datos ficticios
    fuentes/                    Source Serif 4, Archivo e Inter (SIL OFL), por nombre de archivo
    escape.py                   el escape de LaTeX (copia del marco; una prueba los mantiene iguales)

`compilar` hace lo que el build.sh del marco: LuaLaTeX con TEXINPUTS y TTFONTS armados aquí (nunca lualatex
pelado), al menos dos pasadas y más mientras el .aux cambie (el folio «de N»), y el PDF con el nombre que pide su
metadata.tex (`nombrearchivo`). Los colores salen de Unancha (sus tokens → yupay-marca.tex en la carpeta) y el
titular, del perfil de la institución (TEXINPUTS): las dos bases leen la misma marca.

    python -m yupay.marco prueba <carpeta>     compila la prueba en esa carpeta
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
LATEX = RAIZ / "latex"
FUENTES = RAIZ / "fuentes"
MOTOR = "lualatex"
OPCIONES = ["-interaction=nonstopmode", "-halt-on-error", "-file-line-error"]
PASADAS, PASADAS_MAX = 2, 4
_SEMAFORO = asyncio.Semaphore(2)

# Los colores que la base toma de Unancha: nombre en LaTeX → ruta en tokens/colors.json.
COLORES = {"papel": ("escalas", "neutral", "100"), "neutral500": ("escalas", "neutral", "500"),
           "neutral700": ("escalas", "neutral", "700"), "tinta": ("escalas", "neutral", "900"),
           "puka800": ("escalas", "puka", "800")}


@dataclass
class Resultado:
    exito: bool
    ruta_pdf: Path | None
    mensaje: str
    log: str = ""


def plantilla(tipo: str = "rendicion-viaticos") -> Path:
    return LATEX / f"{tipo}.tex"


def marca(colores: Path | None) -> str:
    """yupay-marca.tex desde los tokens de Unancha ('' si no están o no traen esos colores)."""
    if not colores or not Path(colores).is_file():
        return ""
    tokens = json.loads(Path(colores).read_text(encoding="utf-8"))
    lineas = []
    for nombre, ruta in COLORES.items():
        valor = tokens
        for parte in ruta:
            valor = valor.get(parte) if isinstance(valor, dict) else None
        if isinstance(valor, str) and re.fullmatch(r"#?[0-9A-Fa-f]{6}", valor):
            lineas.append(f"\\definecolor{{{nombre}}}{{HTML}}{{{valor.lstrip('#').upper()}}}")
    return ("%% GENERADO por yupay/marco/__init__.py desde los tokens de Unancha; no editar.\n"
            + "\n".join(lineas) + "\n") if lineas else ""


def entorno(perfil: Path | None) -> dict[str, str]:
    """TEXINPUTS: la carpeta de trabajo, el marco y el perfil (kpathsea tolera espacios: sin comillas)."""
    e = dict(os.environ)
    perfil_txt = f"{perfil}//:" if perfil and Path(perfil).is_dir() else ""
    e["TEXINPUTS"] = f".:{LATEX}//:{perfil_txt}"
    e["TTFONTS"] = e["OPENTYPEFONTS"] = f".:{FUENTES}//:"
    return e


def _nombre_final(carpeta: Path) -> str:
    m = re.search(r"^\\setmeta\{nombrearchivo\}\{([A-Za-z0-9_-]+)\}\s*$",
                  (carpeta / "metadata.tex").read_text(encoding="utf-8") if (carpeta / "metadata.tex").is_file() else "", re.M)
    return m.group(1) if m else ""


def _errores(registro: Path) -> str:
    if not registro.is_file():
        return ""
    lineas = registro.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join([ln for ln in lineas if ln.startswith("!") or " Error: " in ln or "not found" in ln][:20])


async def compilar(maestro: Path, *, perfil: Path | None = None, colores: Path | None = None,
                   tiempo: float = 120) -> Resultado:
    """Compila un maestro ya escrito en su carpeta. El PDF queda junto a él, con el nombre de su metadata."""
    carpeta, trabajo = maestro.parent, maestro.stem
    texto_marca = marca(colores)
    (carpeta / "yupay-marca.tex").unlink(missing_ok=True)
    if texto_marca:
        (carpeta / "yupay-marca.tex").write_text(texto_marca, encoding="utf-8")
    env, salida, firma_previa = entorno(perfil), "", None
    async with _SEMAFORO:
        for pasada in range(1, PASADAS_MAX + 1):
            proceso = await asyncio.create_subprocess_exec(
                MOTOR, *OPCIONES, maestro.name, cwd=carpeta, env=env,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            try:
                bruto, _ = await asyncio.wait_for(proceso.communicate(), timeout=tiempo)
            except TimeoutError:
                proceso.kill()
                await proceso.wait()
                return Resultado(False, None, "La compilación tardó demasiado y fue cancelada.")
            salida = bruto.decode("utf-8", errors="replace")
            if proceso.returncode != 0:
                detalle = _errores(carpeta / f"{trabajo}.log")
                primera = next((ln for ln in detalle.splitlines() if ln.startswith("!")), "")
                return Resultado(False, None, f"No se pudo componer el documento. {primera}".strip(),
                                 salida + ("\n--- errores del .log ---\n" + detalle if detalle else ""))
            aux = carpeta / f"{trabajo}.aux"
            firma = hashlib.md5(aux.read_bytes()).hexdigest() if aux.is_file() else ""
            if pasada >= PASADAS and firma == firma_previa:
                break
            firma_previa = firma
    pdf = carpeta / f"{trabajo}.pdf"
    if not pdf.is_file():
        return Resultado(False, None, "LuaLaTeX terminó sin PDF.", salida)
    nombre = _nombre_final(carpeta)
    if nombre:
        destino = carpeta / f"{nombre}.pdf"
        pdf.replace(destino)
        pdf = destino
    return Resultado(True, pdf, "PDF generado.", salida)


def _principal(argv: list[str]) -> int:
    import shutil
    import sys

    if len(argv) != 2 or argv[0] != "prueba":
        print("Uso: python -m yupay.marco prueba <carpeta>")
        return 2
    carpeta = Path(argv[1])
    carpeta.mkdir(parents=True, exist_ok=True)
    shutil.copy2(plantilla(), carpeta / plantilla().name)
    for nombre in ("metadata.tex", "contenido.tex"):
        shutil.copy2(LATEX / "prueba" / nombre, carpeta / nombre)
    from yupay.config import colores, perfil

    r = asyncio.run(compilar(carpeta / plantilla().name, perfil=perfil(), colores=colores()))
    print(r.mensaje, r.ruta_pdf or "", file=sys.stdout if r.exito else sys.stderr)
    if not r.exito:
        print(r.log[-3000:], file=sys.stderr)
    return 0 if r.exito else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(_principal(sys.argv[1:]))
