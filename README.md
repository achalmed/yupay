# Yupay — rendición de cuentas de viáticos

Yupay («contar» en quechua) lleva la rendición de cuentas de una comisión de servicio: comprobantes y movilidad, topes,
declaración jurada, la liquidación en Excel con sus fórmulas y los anexos en PDF con su propio marco LaTeX. Es un
módulo de [Tiqsi](https://github.com/achalmed/tiqsi): funciona solo, con el anfitrión mínimo de Tiqsi, o dentro de una
plataforma que lo monte por su manifiesto (como Qillqa).

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -e '.[pruebas,sola]'   # requiere tiqsi
.venv/bin/python -m pytest -q tests
npm install && npm run web:construir && npm run web:pruebas
RENDICION_DATABASE_URL=postgresql+asyncpg://…/yupay RENDICIONES_DIR=/ruta/rendiciones JWT_SECRET=<32 o más caracteres> \
  RENDICION_WEB=web/dist .venv/bin/uvicorn yupay.sola:app --port 8031
```

Esta es una **versión de demostración**. Licencia: AGPL-3.0 (`LICENSE`); las fuentes del marco, la suya.
