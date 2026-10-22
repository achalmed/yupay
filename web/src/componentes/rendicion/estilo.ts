/**
 * Colores de la rendición de cuentas, desde la paleta ÚNICA (`src/paleta.ts`): estados y niveles de los
 * controles. Sin naranja ni rosa; el apoyo (azul, petróleo, verde) solo para estados.
 */
import { PALETA } from '@qillqa/tiqsi'
import type { Estado, EstadoSeccion, Nivel } from './modelo'

export const COLOR_ESTADO: Record<Estado, string> = {
  borrador: PALETA.borrador,
  lista: PALETA.aprobado,
  presentada: PALETA.firmado,
  observada: PALETA.observado,
  cerrada: PALETA.enviado,
}

export const colorNivel = (n: Nivel): string => (n === 'error' ? PALETA.error : n === 'aviso' ? PALETA.avisoOscuro : PALETA.info)

/** El estado de una sección del avance: pendiente (apagado), registrado (aviso), validado (éxito). */
export const COLOR_SECCION: Record<EstadoSeccion, string> = {
  pendiente: PALETA.apagado,
  registrado: PALETA.avisoOscuro,
  validado: PALETA.exito,
}
export const ETIQUETA_SECCION: Record<EstadoSeccion, string> = { pendiente: 'Pendiente', registrado: 'Registrado', validado: 'Validado' }
