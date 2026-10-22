/**
 * Lo pequeño que Rendición de cuentas usa y antes tomaba de Qillqa (proyecto Yupay; fase 10.2b, 2026-10-20): ahora es
 * suyo, para no importar nada de la plataforma. Lo del contrato (la API, el error, el marco) viene de `@qillqa/tiqsi`.
 */
import { ErrorApi, api } from '@qillqa/tiqsi'

/** Hoy en AAAA-MM-DD con la hora de aquí (toISOString es la de Greenwich: de noche ya sería mañana). */
export const hoyIso = (): string => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Una cuenta del equipo, para elegir al comisionado (`GET /api/rendiciones/equipo`). */
export interface MiembroEquipo {
  id: number
  nombre_completo: string
  rol: string
  cargo?: string
}

/** El mensaje para la persona cuando el pegado falla: la primera causa, en una frase. */
export function mensajePegado(e: unknown): string {
  if (e instanceof ErrorApi && typeof e.detalle === 'object' && e.detalle !== null
    && (e.detalle as { codigo?: string }).codigo === 'pegado_invalido') {
    return (e.detalle as { errores?: string[] }).errores?.[0] ?? 'No se reconoció el formato.'
  }
  return e instanceof Error ? e.message : 'No se pudo leer lo pegado.'
}

/** El texto de un mensaje del Chat que trae comprobantes (`/rendiciones?pegar=<id>`). Solo llega así dentro de
 *  Qillqa, que tiene el Chat: sola, nadie abre esa dirección. */
export async function textoDeMensaje(mid: number | string): Promise<string> {
  const m = await api<{ texto: string }>(`/api/chat/mensajes/${mid}`)
  return m.texto ?? ''
}

/** Copia un texto plano al portapapeles; sin portapapeles moderno (sin HTTPS), a la antigua. */
export async function copiarTexto(texto: string): Promise<void> {
  if (typeof navigator.clipboard?.writeText === 'function' && window.isSecureContext) {
    await navigator.clipboard.writeText(texto)
    return
  }
  const caja = document.createElement('textarea')
  caja.value = texto
  Object.assign(caja.style, { position: 'fixed', left: '-10000px', top: '0' })
  document.body.appendChild(caja)
  caja.select()
  const ok = document.execCommand('copy')
  caja.remove()
  if (!ok) throw new Error('No se pudo copiar.')
}
