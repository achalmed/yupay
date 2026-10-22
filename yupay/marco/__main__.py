"""python -m yupay.marco prueba <carpeta>: compila la prueba del formulario con el marco de Yupay."""
import sys

from yupay.marco import _principal

raise SystemExit(_principal(sys.argv[1:]))
