"""El documento de la rendición de viáticos (2026-10-18): de la rendición al `metadata.tex` y al
`contenido.tex` del formulario de rendición (Anexo N.° 3, Formato 02-VN, declaración jurada de gastos sin
comprobante; Anexo N.° 4, Formato 03-VN, rendición de cuentas), y su compilación con el marco PROPIO de Yupay
(`app/rendicion_marco`: su base LaTeX, sus fuentes y su compilador; nunca `lualatex` pelado).

`componer(vista)` es PURA (la prueba `tests/test_rendicion.py`); `generar` escribe los tres archivos en
la carpeta de la rendición y compila. Todo texto que viene de la persona pasa por `escapar`.

Hasta el 2026-10-20 el formulario lo componía el marco de Gestión documental; desde la fase 10.2b es de Yupay
(docs/plataforma/propuesta-repositorios.md §3.5), con la misma marca (el perfil y Unancha) y el mismo aspecto.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from yupay import marco
from yupay.marco.escape import escapar, escapar_linea
from yupay import rendicion as r
from yupay.config import colores, perfil

MARCA = "%% GENERADO por yupay/tex.py (Yupay, Rendición de cuentas); no editar."


def _meta(clave: str, valor: str) -> str:
    return f"\\setmeta{{{clave}}}{{{escapar_linea(valor)}}}" if valor else f"% \\setmeta{{{clave}}}{{}}   (sin dato: renglón para llenar a mano)"


def _casillas(prefijo: str, iso: str) -> list[str]:
    """«2026-08-20» → \\setmeta{<prefijo>dia}{20}, …mes{08}, …anio{2026} (las casillas del Anexo 4)."""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", iso or "")
    if not m:
        return []
    return [_meta(f"{prefijo}dia", m.group(3)), _meta(f"{prefijo}mes", m.group(2)), _meta(f"{prefijo}anio", m.group(1))]


def _celda(texto: str) -> str:
    return escapar_linea(texto or "")


def componer(vista: dict) -> tuple[str, str]:
    """(metadata.tex, contenido.tex). `vista`: la rendición como la arma la API —`comisionado`
    {nombre, dni, cargo}, `datos`, `memorando` {numero, fecha}|None, `unidad`, `liquidacion`,
    `comprobantes`, `declarados`, `parametros`—, todo vigente."""
    datos = vista.get("datos") or {}
    com = vista.get("comisionado") or {}
    liq = vista["liquidacion"]
    inicio, fin = str(datos.get("fecha_inicio") or ""), str(datos.get("fecha_fin") or "")
    dias = r.dias_de(inicio, fin)
    fecha_dj = str(datos.get("fecha_rendicion") or fin or "")
    memo = vista.get("memorando") or {}
    periodo = ""
    if inicio and fin:
        a, b = r.fecha_larga(inicio), r.fecha_larga(fin)
        periodo = f"del día {a.rsplit(' de ', 1)[0]} al día {b}" if inicio[:4] == fin[:4] else f"del día {a} al día {b}"
    nombre = str(com.get("nombre") or "")
    meta = [
        MARCA,
        _meta("comisionado", nombre),
        _meta("dnicomisionado", str(com.get("dni") or "")),
        _meta("cargocomisionado", str(com.get("cargo") or "")),
        _meta("fechadeclaracion", r.fecha_larga(fecha_dj)),
        _meta("lugarfirma", str(datos.get("lugar_firma") or "")),
        _meta("unidad", str(vista.get("unidad") or "")),
        _meta("siaf", str(datos.get("siaf") or "")),
        _meta("comprobantepago", str(datos.get("comprobante_pago") or "")),
        _meta("comprobantepagofecha", r.fecha_corta(datos["comprobante_pago_fecha"]) if datos.get("comprobante_pago_fecha") else ""),
        _meta("solicitudefectivo", str(datos.get("solicitud_efectivo") or "")),
        _meta("solicitudefectivofecha", r.fecha_corta(datos["solicitud_efectivo_fecha"]) if datos.get("solicitud_efectivo_fecha") else ""),
        # Las tres casillas de cada FECHA del Anexo 4 (día, mes, año; 2026-10-18).
        *_casillas("comprobantepago", str(datos.get("comprobante_pago_fecha") or "")),
        *_casillas("solicitudefectivo", str(datos.get("solicitud_efectivo_fecha") or "")),
        # Un memorando aún sin número no se imprime como «Memorando (borrador)»: renglón a mano.
        _meta("documentoviaje", str(memo.get("numero") or "") if memo.get("numerado", True) else ""),
        _meta("documentoviajefecha", r.fecha_corta(memo["fecha"]).replace("/", "-") if memo.get("fecha") else ""),
        _meta("lugarcomision", str(datos.get("lugar") or "")),
        _meta("periodo", periodo),
        _meta("dias", r.dias_en_letras(len(dias)) if dias else ""),
        _meta("motivo", str(datos.get("motivo") or "")),
        _meta("fecharendicion", r.fecha_corta(fecha_dj) if fecha_dj else ""),
    ]
    # El nombre del PDF lo lee scripts/lib/nombrado.sh TAL CUAL (sed, sin TeX): sin escapar, y solo
    # letras, cifras, guion y guion bajo (con escapar_linea salía «RV-SR-04\_…» en el disco).
    nombre_pdf = re.sub(r"[^A-Za-z0-9_-]", "", str(vista.get("nombre_archivo") or ""))
    if nombre_pdf:
        meta.append(f"\\setmeta{{nombrearchivo}}{{{nombre_pdf}}}")

    c = [MARCA, "\\cabeceraanexo{ANEXO N.° 3}{FORMATO N.° 02-VN}{Declaración jurada de gastos sin comprobante}", "\\textodeclaracion"]
    en_rango = set(dias)
    tramos = sorted((x for x in vista.get("declarados") or [] if (x.get("clase") or "movilidad") == "movilidad" and x.get("fecha") in en_rango),
                    key=lambda x: (x.get("fecha") or "", x.get("hora") or "99:99", x.get("orden") or 0))
    otros = sorted((x for x in vista.get("declarados") or [] if x.get("clase") == "otro" and x.get("fecha") in en_rango),
                   key=lambda x: (x.get("fecha") or "", x.get("orden") or 0))
    c.append("\\begin{tablamovilidad}")
    for t in tramos:
        c.append(f"\\tramo{{{r.fecha_corta(t['fecha'])}}}{{{_celda(r.hora_12(t.get('hora') or ''))}}}{{{_celda(t.get('desde'))}}}"
                 f"{{{_celda(t.get('hasta'))}}}{{{r.texto_soles(r.centimos(t.get('monto')))}}}")
    if not tramos:
        c.append("\\filavacia{5}")
    c.append(f"\\totaltabla{{4}}{{{r.texto_soles(r.centimos(liq['movilidad']))}}}")
    c.append("\\end{tablamovilidad}")
    c.append("\\begin{tablaotros}")
    for o in otros:
        c.append(f"\\otrogasto{{{r.fecha_corta(o['fecha'])}}}{{{_celda(o.get('concepto'))}}}{{{r.texto_soles(r.centimos(o.get('monto')))}}}")
    if not otros:
        c.append("\\filavacia{3}")
    c.append(f"\\totaltabla{{2}}{{{r.texto_soles(r.centimos(liq['otros_dj']))}}}")
    c.append("\\end{tablaotros}")
    dj = r.centimos(liq["dj"])
    c.append(f"\\cierredeclaracion{{{r.texto_soles(dj)}}}{{{escapar(r.importe_en_letras(dj))}}}")
    c += ["", "\\newpage",
          "\\cabeceraanexo{ANEXO N.° 4}{FORMATO N.° 03-VN}{Rendición de cuentas por viáticos, pasajes terrestres y/u otros recursos asignados para la comisión de servicio dentro del territorio nacional}",
          "\\datosrendicion"]
    pct = int(round(float(liq.get("pct_dj_max") or 30)))
    comp = sorted(vista.get("comprobantes") or [], key=lambda x: (x.get("fecha") or "", x.get("orden") or 0, x.get("id") or 0))

    def filas(seccion: str) -> list[dict]:
        return [x for x in comp if r.CONCEPTOS.get(str(x.get("concepto") or ""), ("?",))[0] == seccion
                and (seccion != "A" or x.get("fecha") in en_rango)]

    def fila(n: int, x: dict) -> str:
        concepto = r.CONCEPTOS[x["concepto"]][2]
        if x["concepto"] == "otro_recurso" and x.get("nota"):
            concepto = str(x["nota"])[:40]
        return (f"\\gasto{{{n}}}{{{_celda(r.documento_de(x))}}}{{{r.fecha_corta(x.get('fecha') or '')}}}"
                f"{{{_celda(concepto)}}}{{{r.texto_soles(r.centimos(x.get('importe')))}}}")

    c.append(f"\\begin{{seccionrendicion}}{{A.}}{{VIÁTICOS (Documentados {100 - pct} \\% y Declaración Jurada {pct} \\%)}}")
    a = filas("A")
    for i, x in enumerate(a, 1):
        c.append(fila(i, x))
    if dj:
        rotulo = "MOVILIDAD" if not r.centimos(liq["otros_dj"]) else ("OTROS" if not r.centimos(liq["movilidad"]) else "MOVILIDAD Y OTROS")
        c.append(f"\\gasto{{{len(a) + 1}}}{{Declaración jurada}}{{{r.fecha_corta(fecha_dj)}}}{{{rotulo}}}{{{r.texto_soles(dj)}}}")
    if not a and not dj:
        c.append("\\singastos")
    rendido = sum(r.centimos(x.get("importe")) for x in a) + dj
    c.append(f"\\totalseccionfuerte{{Total gastos rendidos}}{{{r.texto_soles(rendido)}}}")
    exceso = r.centimos(liq["exceso"])
    if exceso:
        c.append(f"\\totalseccion{{Sobre el viático (lo asume)}}{{{r.texto_soles(-exceso)}}}")
        c.append(f"\\totalseccionfuerte{{Total reconocido}}{{{r.texto_soles(r.centimos(liq['reconocido']))}}}")
    c.append(f"\\totalseccion{{Importe recibido}}{{{r.texto_soles(r.centimos(liq['recibido']))}}}")
    c.append(f"\\totalseccionfuerte{{Saldo}}{{{r.texto_soles(r.centimos(liq['saldo']))}}}")
    c.append("\\end{seccionrendicion}")
    for letra, seccion, titulo, clave in (("B.", "B", "PASAJES TERRESTRES", "pasajes"), ("C.", "C", "OTROS RECURSOS (Documentado 100 \\%)", "otros")):
        xs = filas(seccion)
        # La última sección va con la firma en un solo bloque (la firma nunca queda sola en una hoja);
        # con muchas filas no cabría en una caja y sigue en longtable.
        final = seccion == "C" and len(xs) <= 12
        entorno = "seccioncorta" if final else "seccionrendicion"
        if final:
            c.append("\\begin{bloquefinal}")
        c.append(f"\\begin{{{entorno}}}{{{letra}}}{{{titulo}}}")
        for i, x in enumerate(xs, 1):
            c.append(fila(i, x))
        if not xs:
            c.append("\\singastos")
        bloque = liq[clave]
        c.append(f"\\totalseccionfuerte{{Total gastos rendidos}}{{{r.texto_soles(r.centimos(bloque['rendido']))}}}")
        c.append(f"\\totalseccion{{Importe recibido}}{{{r.texto_soles(r.centimos(bloque['recibido']))}}}")
        c.append(f"\\totalseccionfuerte{{Saldo}}{{{r.texto_soles(r.centimos(bloque['saldo']))}}}")
        c.append(f"\\end{{{entorno}}}")
    c.append("\\firmarendicion")
    if final:
        c.append("\\end{bloquefinal}")
    return "\n".join(meta) + "\n", "\n".join(c) + "\n"


def maestro() -> str:
    """El maestro de la plantilla del marco, tal cual (la plantilla es el test del tipo)."""
    return marco.plantilla("rendicion-viaticos").read_text(encoding="utf-8")


async def generar(carpeta: Path, vista: dict):
    """Escribe maestro + metadata + contenido en `carpeta` y compila. El PDF anterior se aparta
    mientras tanto y vuelve si la compilación falla (como los documentos: nunca se pierde el último
    bueno). Devuelve el ResultadoCompilacion."""
    carpeta.mkdir(parents=True, exist_ok=True)
    meta, contenido = componer(vista)
    (carpeta / "rendicion-viaticos.tex").write_text(maestro(), encoding="utf-8")
    (carpeta / "metadata.tex").write_text(meta, encoding="utf-8")
    (carpeta / "contenido.tex").write_text(contenido, encoding="utf-8")
    anteriores = list(carpeta.glob("*.pdf"))
    apartado = carpeta / ".anterior"
    if anteriores:
        apartado.mkdir(exist_ok=True)
        for p in anteriores:
            shutil.move(str(p), apartado / p.name)
    resultado = await marco.compilar(carpeta / "rendicion-viaticos.tex", perfil=perfil(), colores=colores())
    if apartado.exists():
        if resultado.exito:
            shutil.rmtree(apartado, ignore_errors=True)
        else:
            for p in apartado.glob("*.pdf"):
                shutil.move(str(p), carpeta / p.name)
            shutil.rmtree(apartado, ignore_errors=True)
    return resultado
