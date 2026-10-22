"""El escape de LaTeX del marco de Yupay (Rendición de cuentas; fase 10.2b, 2026-10-20): todo texto que viene de la
persona pasa por `escapar` antes de entrar a un .tex. Es una COPIA de `app/latex/serializador.py` (el marco de Gestión
documental): las dos bases LaTeX escapan igual y tests/test_rendicion_marco.py comprueba que sigan iguales.
"""
from __future__ import annotations

import unicodedata

_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

# Caracteres INVISIBLES que llegan al pegar desde Word/web y que rompen o
# ensucian la compilación: controles C0/C1 (salvo \n en bloques), espacios
# raros y ancho-cero. Se sustituyen ANTES de escapar (texto pegado -> texto
# limpio -> LaTeX). Ver docs/redaccion-administrativa.md (§9, typos).
_INVISIBLES = {
    " ": " ",   # espacio no separable (nbsp de Word)
    " ": " ",   # nbsp fino
    " ": " ",   # espacio de cifra
    " ": " ",   # espacio fino
    "\t": " ",
    "​": "",    # ancho cero
    "‌": "",
    "‍": "",
    "﻿": "",    # BOM
    "­": "",    # guion suave
    "\r": "",
}


# Word escribe los símbolos de sus fuentes Symbol y Wingdings en la zona de USO PRIVADO
# (U+F000–U+F0FF): el «°» de Symbol llega como U+F0B0, la viñeta como U+F0B7… Ninguna fuente
# del marco los dibuja y desaparecían del PDF. Se traducen al carácter real; el resto de la
# zona privada se descarta.
_PRIVADOS_WORD = {
    "\uf0b0": "°", "\uf0b7": "•", "\uf0a7": "•", "\uf0a8": "•", "\uf076": "•", "\uf0d8": "•",
    "\uf0fc": "✓", "\uf0fb": "✗", "\uf0e0": "→", "\uf0ae": "→", "\uf0ac": "←", "\uf0b1": "±",
    "\uf0b4": "×", "\uf0a3": "≤", "\uf0b3": "≥", "\uf0b9": "≠", "\uf02d": "-", "\uf02a": "*",
}
# Lo que las fuentes del marco (Source Serif 4, Archivo, Inter) no tienen: se compone en modo
# matemático, que sí lo dibuja.
_SIN_GLIFO = {
    "→": r"\ensuremath{\rightarrow}", "←": r"\ensuremath{\leftarrow}", "↔": r"\ensuremath{\leftrightarrow}",
    "⇒": r"\ensuremath{\Rightarrow}", "≤": r"\ensuremath{\leq}", "≥": r"\ensuremath{\geq}",
    "≠": r"\ensuremath{\neq}", "≈": r"\ensuremath{\approx}", "✓": r"\ensuremath{\surd}",
    "✔": r"\ensuremath{\surd}", "✗": "x", "✘": "x", "\u2011": "-", "−": "-",
}


def _visible(c: str) -> bool:
    """Fuera: controles C0 (salvo salto de línea) y C1, selectores de variante, zona privada y
    emoji (ninguna fuente del marco los tiene)."""
    o = ord(c)
    if c == "\n":
        return True
    if o < 32 or 0x7F <= o <= 0x9F or 0xFE00 <= o <= 0xFE0F or 0xE000 <= o <= 0xF8FF:
        return False
    return not (0x1F000 <= o <= 0x1FAFF or 0x2600 <= o <= 0x26FF or 0x2700 <= o <= 0x27BF and c not in _SIN_GLIFO)


def limpiar(texto: str) -> str:
    """Texto pegado de Word o de la web → texto limpio: forma Unicode compuesta (NFC: la «é»
    de dos piezas pasa a una), invisibles y espacios raros, separadores de línea Unicode, los
    símbolos de las fuentes de Word y fuera lo que no se puede imprimir."""
    texto = unicodedata.normalize("NFC", texto or "")
    texto = texto.replace("\u2028", "\n").replace("\u2029", "\n")
    texto = "".join(_PRIVADOS_WORD.get(c, _INVISIBLES.get(c, c)) for c in texto)
    return "".join(c for c in texto if _visible(c))


def escapar(texto: str) -> str:
    """Neutraliza los caracteres especiales de LaTeX en un solo paso
    (limpiando antes los caracteres invisibles del pegado)."""
    return "".join(_ESCAPES.get(c) or _SIN_GLIFO.get(c, c) for c in limpiar(texto))


def escapar_linea(texto: str) -> str:
    """`escapar` para un campo de UNA línea (asunto, referencia): los saltos y las líneas en
    blanco pegadas de Word se vuelven un espacio. Una línea en blanco dentro de \\asunto{…}
    es un \\par que corta el argumento y el asunto no sale."""
    return escapar(" ".join(limpiar(texto).split()))
