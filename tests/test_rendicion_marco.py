"""tests/test_rendicion_marco.py — el marco LaTeX propio de Yupay (yupay/marco; fase 10.2b, 2026-10-20).

Las dos bases LaTeX (la del marco documental y la de Yupay) leen la misma marca y escapan igual; el formulario
compila con su propio marco (si hay LuaLaTeX en esta máquina). Que el PDF es idéntico al del marco documental se
comprobó píxel a píxel al crearlo; aquí, que compila y trae sus dos anexos.
"""
import asyncio
import json
import shutil
import subprocess

import pytest

from yupay import marco
from yupay.marco import escape

def test_la_marca_sale_de_los_tokens_de_unancha(tmp_path):
    tokens = tmp_path / "colors.json"
    tokens.write_text(json.dumps({"escalas": {"neutral": {"100": "#f5f1ec", "500": "#A99E92", "700": "#6E655D",
                                                          "900": "#241F1C"}, "puka": {"800": "#6E0F22"}}}))
    texto = marco.marca(tokens)
    assert "\\definecolor{papel}{HTML}{F5F1EC}" in texto and "\\definecolor{puka800}{HTML}{6E0F22}" in texto
    assert texto.count("\\definecolor") == 5
    assert marco.marca(tmp_path / "no-existe.json") == "" and marco.marca(None) == ""


def test_trae_sus_fuentes_y_su_plantilla():
    assert marco.plantilla().is_file() and "\\documentclass{yupay-rendicion}" in marco.plantilla().read_text()
    for f in ("SourceSerif4-Regular.ttf", "Archivo-SemiBold.ttf", "Inter-Regular.ttf", "Inter-SemiBold.ttf"):
        assert (marco.FUENTES / f).is_file(), f


@pytest.mark.skipif(not shutil.which("lualatex"), reason="sin LuaLaTeX en esta máquina")
def test_el_formulario_compila_con_su_marco(tmp_path):
    shutil.copy2(marco.plantilla(), tmp_path / marco.plantilla().name)
    for nombre in ("metadata.tex", "contenido.tex"):
        shutil.copy2(marco.LATEX / "prueba" / nombre, tmp_path / nombre)
    r = asyncio.run(marco.compilar(tmp_path / marco.plantilla().name))
    assert r.exito, r.log[-2000:]
    if shutil.which("pdfinfo"):
        info = subprocess.run(["pdfinfo", str(r.ruta_pdf)], capture_output=True, text=True).stdout
        assert "Pages:           2" in info
