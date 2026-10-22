"""Modelos de la RENDICIÓN DE CUENTAS de viáticos (2026-10-18; servicios/rendicion.py, api/rendiciones.py,
`docs/arquitectura.md` §32). Las tablas las crea `create_all` al arrancar (main.py importa este módulo).

Una rendición es de UN comisionado y UNA comisión de servicio. Lo que nombra se guarda por clave y se
muestra vigente (§27): el comisionado (`usuario_id`: nombre, cargo y DNI de su cuenta), la semana de
representación (`semana_id`: código, tema, fechas y actividades) y el memorando que solicitó los
viáticos (`documento_id`: su número y su fecha de hoy). Nada de eso se copia en `datos`.

Desde la fase 10.2b (2026-10-20) Rendición es un módulo aislado (proyecto Yupay): sus tablas viven sobre
`BaseRendicion`, no sobre `app.modelos.Base`, y las crea su manifiesto al arrancar
(`servicios/rendicion_db.py`). Lo de otros (la cuenta, la semana, el memorando) se guarda como número, sin clave
foránea: se pide por el contrato (`identidad.v1`, `semanas.v1`, `documentos.v1`) y, si ya no existe, la rendición
lo muestra vacío. Las bases que ya tenían esas claves foráneas las conservan hasta que la base se separe.

La MOVILIDAD es de la COMISIÓN, no de cada rendición (2026-10-18, Edison: «los dos trabajadores tienen
los mismos tramos, porque viajan juntos con el diputado al mismo lugar y en las mismas fechas»): los
tramos viven en `rendicion_tramos` colgados de `rendicion_comisiones` (la Semana de representación o la
comisión de servicio) y cada rendición de esa comisión los usa. Un solo lugar de verdad (§27); cada cambio
deja constancia en `rendicion_cambios` (quién, cuándo, antes y después) y se puede deshacer.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class BaseRendicion(DeclarativeBase):
    """Las tablas de Rendición (proyecto Yupay): su `create_all` no es el de la base documental."""


class Rendicion(BaseRendicion):
    __tablename__ = "rendiciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(Integer)                       # la cuenta del comisionado (identidad.v1)
    semana_id: Mapped[int | None] = mapped_column(Integer, nullable=True)    # la semana (semanas.v1)
    documento_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # el memorando (documentos.v1)
    # La comisión cuya movilidad comparte (2026-10-18). Columna añadida por ALTER (servicios/rendicion_db.py).
    comision_id: Mapped[int | None] = mapped_column(ForeignKey("rendicion_comisiones.id", ondelete="SET NULL"), nullable=True, index=True)
    # borrador | lista | presentada | observada | cerrada (servicios/rendicion.py: ESTADOS)
    estado: Mapped[str] = mapped_column(String(20), default="borrador")
    # La cabecera del Formato 03-VN que el sistema no sabe por sí mismo: fecha_inicio, fecha_fin, lugar,
    # motivo, siaf, comprobante_pago, comprobante_pago_fecha, solicitud_efectivo, solicitud_efectivo_fecha,
    # fecha_rendicion, lugar_firma, unidad_organica (vacío = la del perfil), dj_objetivo {fecha: monto}.
    datos: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Lo que esta rendición ajusta de los parámetros (tope diario, % DJ, recibidos…); lo demás rige del
    # despacho (`AjusteRendicion` «parametros») o de fábrica.
    parametros: Mapped[dict] = mapped_column(JSONB, default=dict)
    observacion: Mapped[str] = mapped_column(Text, default="")
    # Control de concurrencia (como documentos.version_contenido): 409 si otro guardó antes.
    version: Mapped[int] = mapped_column(Integer, default=0)
    # El PDF y el Excel generados (rutas absolutas en la carpeta de la rendición) y cuándo.
    documento_pdf: Mapped[str] = mapped_column(Text, default="")
    generado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    creado_por: Mapped[int] = mapped_column(Integer)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    presentada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ComprobanteGasto(BaseRendicion):
    """Un comprobante de pago (boleta, factura, ticket…) con su foto o PDF."""

    __tablename__ = "rendicion_comprobantes"

    id: Mapped[int] = mapped_column(primary_key=True)
    rendicion_id: Mapped[int] = mapped_column(ForeignKey("rendiciones.id", ondelete="CASCADE"), index=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    fecha: Mapped[str] = mapped_column(String(10), default="")
    tipo: Mapped[str] = mapped_column(String(30), default="boleta_electronica")
    serie: Mapped[str] = mapped_column(String(20), default="")
    numero: Mapped[str] = mapped_column(String(30), default="")
    ruc: Mapped[str] = mapped_column(String(11), default="")
    proveedor: Mapped[str] = mapped_column(String(200), default="")
    concepto: Mapped[str] = mapped_column(String(30), default="almuerzo")
    importe: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    # Ruta relativa a la carpeta de la rendición: `comprobantes/AAAAMMDD_SERIE-NUMERO_<sha8>.jpg` (o
    # `foto_<sha8>.jpg` si se subió sin datos). Un mismo archivo (misma huella) se guarda UNA vez y lo
    # comparten los comprobantes que sustenta (una foto con dos facturas; 2026-10-18).
    archivo: Mapped[str] = mapped_column(String(200), default="")
    nota: Mapped[str] = mapped_column(Text, default="")
    # manual | pegado
    origen: Mapped[str] = mapped_column(String(20), default="manual")


class GastoDeclarado(BaseRendicion):
    """Un gasto sin comprobante de UNA persona, sustentado con la declaración jurada (Formato 02-VN): otro
    gasto (fecha, concepto, monto). Hasta el 2026-10-18 guardaba también los tramos de movilidad de cada
    rendición; desde entonces la movilidad es de la comisión (`TramoMovilidad`) y la migración de
    `servicios/rendicion_comision.py::migrar` los pasó allí."""

    __tablename__ = "rendicion_declarados"

    id: Mapped[int] = mapped_column(primary_key=True)
    rendicion_id: Mapped[int] = mapped_column(ForeignKey("rendiciones.id", ondelete="CASCADE"), index=True)
    # movilidad | otro
    clase: Mapped[str] = mapped_column(String(20), default="movilidad")
    orden: Mapped[int] = mapped_column(Integer, default=0)
    fecha: Mapped[str] = mapped_column(String(10), default="")
    hora: Mapped[str] = mapped_column(String(5), default="")
    desde: Mapped[str] = mapped_column(String(200), default="")
    hasta: Mapped[str] = mapped_column(String(200), default="")
    concepto: Mapped[str] = mapped_column(String(200), default="")
    monto: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    # La actividad de la semana de la que salió el tramo (A-NN), si lo propuso el sistema.
    actividad: Mapped[str] = mapped_column(String(10), default="")


class AnexoRendicion(BaseRendicion):
    """Un sustento que acompaña a la rendición y NO se rinde (2026-10-18): el boleto aéreo (DI
    37-2025-DF-DGA-CR, 7.9.1.1.5: se adjunta para verificar las fechas), el recibo de devolución del
    saldo (7.9.4.2) u otro (informe, autorización). Su archivo vive en `anexos/` de la carpeta de la
    rendición; un mismo archivo se guarda una sola vez (huella en el nombre)."""

    __tablename__ = "rendicion_anexos"

    id: Mapped[int] = mapped_column(primary_key=True)
    rendicion_id: Mapped[int] = mapped_column(ForeignKey("rendiciones.id", ondelete="CASCADE"), index=True)
    # boleto | devolucion | otro
    clase: Mapped[str] = mapped_column(String(20), default="otro")
    descripcion: Mapped[str] = mapped_column(String(200), default="")
    archivo: Mapped[str] = mapped_column(String(200), default="")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ComisionServicio(BaseRendicion):
    """La comisión de servicio que comparten quienes viajaron juntos (2026-10-18): la Semana de
    representación (`clave` = `sr:<id>`) o una comisión sin semana (`cs:<inicio>_<lugar>`; una rendición
    sin fechas tiene la suya, `r:<id>`). De ella son la movilidad (`TramoMovilidad`), la DJ del día fijada
    a mano y el importe recibido cuando es el mismo para todos. Su carpeta (relativa a RENDICIONES_DIR,
    `AAAA/<carpeta de la semana>` o `AAAA/AAAA-MM-DD_<lugar>`) se FIJA al crearla."""

    __tablename__ = "rendicion_comisiones"

    id: Mapped[int] = mapped_column(primary_key=True)
    clave: Mapped[str] = mapped_column(String(120), unique=True)
    semana_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    carpeta: Mapped[str] = mapped_column(String(200), default="")
    # {dj_objetivo: {fecha: monto}, recibido_viaticos: monto}
    datos: Mapped[dict] = mapped_column(JSONB, default=dict)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TramoMovilidad(BaseRendicion):
    """Un tramo de movilidad de la comisión (fecha, hora, del, al, monto): sale en el Anexo 3 de TODAS sus
    rendiciones. Lo puede corregir cualquiera de ellas; queda quién lo tocó por última vez."""

    __tablename__ = "rendicion_tramos"

    id: Mapped[int] = mapped_column(primary_key=True)
    comision_id: Mapped[int] = mapped_column(ForeignKey("rendicion_comisiones.id", ondelete="CASCADE"), index=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    fecha: Mapped[str] = mapped_column(String(10), default="")
    hora: Mapped[str] = mapped_column(String(5), default="")
    desde: Mapped[str] = mapped_column(String(200), default="")
    hasta: Mapped[str] = mapped_column(String(200), default="")
    monto: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    # La actividad de la semana de la que salió el tramo (A-NN), si lo propuso el sistema.
    actividad: Mapped[str] = mapped_column(String(10), default="")
    actualizado_por: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CambioMovilidad(BaseRendicion):
    """La constancia de quién cambió qué en la movilidad de una comisión (2026-10-18). Un `lote` agrupa lo
    que hizo una sola acción («Ajustar a lo sugerido», quitar los tramos de un día, agregar un tramo); cada
    fila guarda el tramo (o el dato de la comisión) antes y después, y así se DESHACE: el último lote no
    deshecho vuelve atrás, salvo lo que alguien cambió después."""

    __tablename__ = "rendicion_cambios"

    id: Mapped[int] = mapped_column(primary_key=True)
    comision_id: Mapped[int] = mapped_column(ForeignKey("rendicion_comisiones.id", ondelete="CASCADE"), index=True)
    lote: Mapped[str] = mapped_column(String(32), index=True)
    texto: Mapped[str] = mapped_column(String(300), default="")
    # crear | cambiar | quitar (un tramo) | dato (un dato de la comisión: `antes`/`despues` = {clave: valor})
    accion: Mapped[str] = mapped_column(String(20), default="cambiar")
    tramo_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    antes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    despues: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    usuario_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rendicion_id: Mapped[int | None] = mapped_column(Integer, nullable=True)   # desde qué rendición se hizo
    en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deshecho: Mapped[bool] = mapped_column(Boolean, default=False)
    # El lote que esta fila deshizo ('' si es un cambio normal): un deshacer no se vuelve a deshacer.
    deshace: Mapped[str] = mapped_column(String(32), default="")


class AjusteRendicion(BaseRendicion):
    """Los ajustes del módulo (fase 10.2b, 2026-10-20): «parametros» (los de la entidad: tope diario, % DJ, plazo…) y
    «no_rinden» ({semana_id: [nombres]}). Antes vivían en `ajustes` de la plataforma (`rendicion_parametros`,
    `rendicion_no_rinden`); al arrancar se copian aquí una vez (servicios/rendicion_db.py)."""

    __tablename__ = "rendicion_ajustes"

    clave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[dict] = mapped_column(JSONB, default=dict)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
