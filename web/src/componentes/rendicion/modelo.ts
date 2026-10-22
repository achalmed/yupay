/**
 * RENDICIÓN DE CUENTAS — tipos de la API (`backend/app/api/rendiciones.py`) y la lógica pura de la
 * interfaz (formato de soles, plazo, agrupar por día, a qué paso lleva un control). Sin imports: la prueba
 * corre en Node sin el resto de la web; los colores están en `estilo.ts`. El cálculo NO se repite aquí:
 * lo hace el servidor (`servicios/rendicion.py`) y la web lo muestra. Pruebas en `pruebas/rendicion.test.ts`.
 */
export type Estado = 'borrador' | 'lista' | 'presentada' | 'observada' | 'cerrada'
export type Nivel = 'error' | 'aviso' | 'info'

export type OrigenParametro = 'fabrica' | 'despacho' | 'rendicion' | 'comision' | 'memorando' | 'supuesto'
export interface Parametro { valor: number | null; etiqueta: string; norma?: string; simple?: string; fuente: string; origen: OrigenParametro }
export interface Comprobante {
  id: number; orden: number; fecha: string; tipo: string; serie: string; numero: string; ruc: string; proveedor: string
  concepto: string; importe: number; archivo: string; nota: string; origen: string; documento: string
}
/** Un gasto sin comprobante: un tramo de movilidad (de la COMISIÓN, compartido) u otro gasto (de la rendición). */
export interface Declarado {
  id: number; clase: 'movilidad' | 'otro'; orden: number; fecha: string; hora: string; desde: string; hasta: string; concepto: string; monto: number; actividad: string
  actualizado_por?: string; actualizado_en?: string | null
}
export interface DiaLiquidacion {
  fecha: string; por_concepto: Record<string, number>; subtotal_a: number; movilidad: number; otros_dj: number; dj: number
  asignado: number; reconocido: number; exceso: number; saldo: number; sugerida: number; objetivo: number | null
  dj_ok: boolean; total_ok: boolean; sin_exceso: boolean
  /** La movilidad del día que alcanza a TODOS los de la comisión, y la línea que la explica. */
  compartida?: number; explicacion?: string; limita?: string
}
export interface Bloque { rendido: number; recibido: number; saldo: number }
export interface Liquidacion {
  dias: DiaLiquidacion[]; por_concepto: Record<string, number>; tope_diario: number; tope_dj: number; pct_dj_max: number
  asignado: number; recibido: number; con_comprobante: number; dj: number; movilidad: number; otros_dj: number
  rendido: number; reconocido: number; exceso: number; saldo: number; saldo_por_dias: number; pct_dj: number; pct_dj_ok: boolean
  conforme: Record<string, string>; pasajes: Bloque; otros: Bloque; dj_en_letras: string
}
export interface Control { codigo: string; nivel: Nivel; texto: string; dia?: string; ref?: string; urgente?: boolean }
export interface Memorando { id: number; numero: string; fecha: string; asunto: string; estado: string; numerado: boolean }
export interface SemanaVinculada { id: number; codigo: string; tema: string; inicio: string; fin: string; provincias: string[]; region: string }
export type EstadoSeccion = 'pendiente' | 'registrado' | 'validado'
export interface SeccionAvance { clave: 'datos' | 'comprobantes' | 'movilidad' | 'documento'; etiqueta: string; estado: EstadoSeccion; texto: string }
export interface Avance { secciones: SeccionAvance[]; validadas: number; total: number }
export interface Anexo { id: number; clase: 'boleto' | 'devolucion' | 'otro'; descripcion: string; archivo: string; creado_en: string | null }
export interface MiembroComision { id: number; codigo: string; usuario_id: number; estado: Estado; etiqueta_estado: string; comisionado: string; accesible: boolean }
export interface UltimoCambio { lote: string; texto: string; usuario: string; en: string | null; cambios: number }
export interface Comision {
  id: number; clave: string; carpeta: string; miembros: MiembroComision[]; dj_objetivo: Record<string, number>
  recibido: { valor: number; por: string } | null; ultimo_cambio: UltimoCambio | null; bloqueada_por: string
  faltan?: { nombre: string; rol: string; usuario_id: number | null }[]
}
export interface PasoPlan { fecha: string; antes: number; despues: number; cambia: boolean; explicacion: string; motivo?: '' | 'fijada' | 'fijada_tope' | 'pct' }
export interface Companero { id: number; codigo: string; comisionado: string; tramos: number; otros: number; parametros: number; lugar_firma: boolean; memorando: boolean }
export interface Rendicion {
  id: number; codigo: string; estado: Estado; etiqueta_estado: string; version: number; observacion: string
  comisionado: { id: number; nombre: string; corto: string; cargo: string; dni: string; usuario: string }
  semana: SemanaVinculada | null; memorando: Memorando | null
  datos: Record<string, string | Record<string, number>>; datos_propios: Record<string, unknown>; origen_datos: Record<string, string>
  parametros: Record<string, Parametro>; parametros_propios: Record<string, number>
  dias: string[]; comprobantes: Comprobante[]; declarados: Declarado[]; anexos: Anexo[]
  liquidacion: Liquidacion; controles: Control[]; limite: string | null; errores: number; unidad: string
  documento: { pdf: boolean; nombre: string; generado_en: string | null; al_dia: boolean }
  avance: Avance; pendientes: string[]; nombre_archivo: string
  memorandos_sugeridos: Memorando[]
  actividades: { codigo: string; fecha: string; hora_inicio: string; titulo: string; lugar: string }[]
  puede_administrar: boolean
  comision: Comision; creado_por: string; institucion?: { a_nombre_de: string; ruc_a_nombre: string }
}
export interface FilaLista {
  id: number; codigo: string; estado: Estado; etiqueta_estado: string; comisionado: string; usuario_id: number
  semana: SemanaVinculada | null; memorando: string | null; inicio: string; fin: string
  recibido: number; reconocido: number; saldo: number; comprobantes: number; errores: number; avisos: number
  limite: string | null; vencida: boolean; avance?: Avance; pendientes?: number
  /** Para agrupar por comisión (2026-10-18): la comisión que comparten y su lugar. */
  comision_id?: number; lugar?: string
}

export const CONCEPTOS: { v: string; t: string; seccion: 'A' | 'B' | 'C' }[] = [
  { v: 'desayuno', t: 'Desayuno', seccion: 'A' },
  { v: 'almuerzo', t: 'Almuerzo', seccion: 'A' },
  { v: 'cena', t: 'Cena', seccion: 'A' },
  { v: 'otros_alimentacion', t: 'Otros de alimentación', seccion: 'A' },
  { v: 'hospedaje', t: 'Hospedaje', seccion: 'A' },
  { v: 'pasaje_terrestre', t: 'Pasaje terrestre', seccion: 'B' },
  { v: 'otro_recurso', t: 'Otro recurso', seccion: 'C' },
]
export const TIPOS: { v: string; t: string }[] = [
  { v: 'boleta_electronica', t: 'Boleta electrónica' },
  { v: 'boleta', t: 'Boleta de venta' },
  { v: 'factura_electronica', t: 'Factura electrónica' },
  { v: 'factura', t: 'Factura' },
  { v: 'ticket', t: 'Ticket' },
  { v: 'recibo', t: 'Recibo' },
  { v: 'otro', t: 'Otro' },
]
/** «Boleta EB01-0101»: el tipo corto y el número, lo que se busca de un vistazo en el celular. */
export function numeroCorto(c: { tipo: string; serie: string; numero: string }): string {
  const tipo = c.tipo.startsWith('boleta') ? 'Boleta' : c.tipo.startsWith('factura') ? 'Factura' : c.tipo === 'ticket' ? 'Ticket' : c.tipo === 'recibo' ? 'Recibo' : 'Comprobante'
  const num = c.serie && c.numero ? `${c.serie}-${c.numero}` : c.serie || c.numero
  return num ? `${tipo} ${num}` : tipo
}
export const conceptoDe = (v: string) => CONCEPTOS.find((c) => c.v === v)?.t ?? v

export const ESTADOS: Record<Estado, string> = {
  borrador: 'Borrador', lista: 'Lista', presentada: 'Presentada', observada: 'Observada', cerrada: 'Cerrada',
}

/** 2345.6 → «S/ 2,345.60» (la forma de los formatos). */
export function soles(n: number | null | undefined): string {
  const v = Number(n ?? 0)
  const signo = v < 0 ? '-' : ''
  const c = Math.round(Math.abs(v) * 100)
  const entero = Math.floor(c / 100).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return `${signo}S/ ${entero}.${String(c % 100).padStart(2, '0')}`
}

/** «AAAA-MM-DD» → «lun 24/08». */
export function diaCorto(iso: string): string {
  if (!/^\d{4}-\d{2}-\d{2}/.test(iso ?? '')) return iso ?? ''
  const [a, m, d] = iso.slice(0, 10).split('-').map(Number)
  const nombre = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'][new Date(a, m - 1, d).getDay()]
  return `${nombre} ${String(d).padStart(2, '0')}/${String(m).padStart(2, '0')}`
}

export function fechaCorta(iso: string | null | undefined): string {
  if (!iso || !/^\d{4}-\d{2}-\d{2}/.test(iso)) return iso ?? ''
  const [a, m, d] = iso.slice(0, 10).split('-')
  return `${d}/${m}/${a}`
}

/**
 * ¿Corre el plazo para rendir? Solo en borrador o lista (2026-10-18, Edison: «una rendición presentada,
 * observada o cerrada no lleva el chip “Vencida el …”»; la observada se subsana en 72 horas, aparte). Lo
 * mismo dice el servidor (`rendicion.corre_plazo`).
 */
export const correPlazo = (estado: Estado): boolean => estado === 'borrador' || estado === 'lista'

/** «Rendir hasta el 11/09 · faltan 3 días» / «Vencida el 11/09». */
export function textoPlazo(limite: string | null, hoy: string, estado: Estado): string {
  if (!limite || !correPlazo(estado)) return ''
  const dias = Math.round((Date.parse(limite) - Date.parse(hoy)) / 86_400_000)
  if (dias < 0) return `Vencida el ${fechaCorta(limite)}`
  if (dias === 0) return 'Vence hoy'
  return `Hasta el ${fechaCorta(limite)} · ${dias === 1 ? 'falta 1 día' : `faltan ${dias} días`}`
}

/** Los gastos de una lista agrupados por día, en el orden de los días de la comisión (y los de fuera al final). */
export function porDia<T extends { fecha: string }>(filas: T[], dias: string[]): { fecha: string; filas: T[]; fuera: boolean }[] {
  const grupos = new Map<string, T[]>()
  for (const d of dias) grupos.set(d, [])
  for (const f of filas) {
    const k = f.fecha || ''
    if (!grupos.has(k)) grupos.set(k, [])
    grupos.get(k)!.push(f)
  }
  const dentro = new Set(dias)
  return [...grupos.entries()]
    .filter(([, fs]) => fs.length > 0 || dentro.has(''))
    .map(([fecha, fs]) => ({ fecha, filas: fs, fuera: !dentro.has(fecha) }))
    .sort((a, b) => Number(a.fuera) - Number(b.fuera) || a.fecha.localeCompare(b.fecha))
}

/** El paso de la rendición donde se corrige un control (`comprobante:12` → comprobantes). */
export function pasoDeControl(c: Control): 'datos' | 'comprobantes' | 'movilidad' | 'revision' {
  if (c.ref?.startsWith('comprobante:')) return 'comprobantes'
  if (c.ref?.startsWith('declarado:') || c.ref?.startsWith('tramo:') || ['dj_tope', 'tramos_dj', 'dia_tope', 'movilidad_compartida'].includes(c.codigo)) return 'movilidad'
  if (['sin_dni', 'sin_cargo', 'sin_memorando', 'memorando_sin_numero', 'sin_fechas', 'recibido', 'recibido_supuesto'].includes(c.codigo)) return 'datos'
  return 'revision'
}

/** RUC peruano: 11 dígitos, prefijo 10/15/17/20 y dígito verificador. Vacío = sin RUC (válido). */
export function rucValido(ruc: string): boolean {
  if (!ruc) return true
  if (!/^(10|15|17|20)\d{9}$/.test(ruc)) return false
  const pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
  const resto = 11 - (pesos.reduce((s, p, i) => s + p * Number(ruc[i]), 0) % 11)
  return (resto >= 10 ? resto - 10 : resto) === Number(ruc[10])
}

/**
 * «EB01-1586», «F001 - 00004711», «FR95 / 12841» o «001 026812» escritos en Número → serie y número
 * (2026-10-18: en el ensayo, cada comprobante se copiaba del Word en una sola pieza). Si la serie ya se
 * escribió aparte o no hay separador, queda tal cual. El servidor hace lo mismo (`partir_numero`).
 */
export function partirNumero(serie: string, numero: string): { serie: string; numero: string } {
  const s = (serie ?? '').trim()
  const n = (numero ?? '').trim()
  if (s) return { serie: s.toUpperCase(), numero: n }
  const m = /^([A-Za-z0-9]{1,6})\s*[-–/ ]\s*(\d{1,12})$/.exec(n)
  return m ? { serie: m[1].toUpperCase(), numero: m[2] } : { serie: s, numero: n }
}

/** La semana que conviene rendir: la que terminó más recientemente (hasta hoy); si ninguna terminó, la más próxima. */
export function semanaPorDefecto<T extends { id: number; inicio: string; fin: string }>(semanas: T[], hoy: string): number | '' {
  const terminadas = semanas.filter((s) => s.fin && s.fin <= hoy).sort((a, b) => b.fin.localeCompare(a.fin))
  if (terminadas.length) return terminadas[0].id
  const proximas = semanas.filter((s) => s.inicio).sort((a, b) => a.inicio.localeCompare(b.inicio))
  return proximas[0]?.id ?? semanas[0]?.id ?? ''
}

/** El tramo que sigue a uno recién guardado: el mismo día, desde donde llegó el anterior (alta en serie). */
export function siguienteTramo(anterior: { fecha: string; hasta: string }): { fecha: string; hora: string; desde: string; hasta: string; concepto: string; monto: string } {
  return { fecha: anterior.fecha, hora: '', desde: anterior.hasta, hasta: '', concepto: '', monto: '' }
}

/** «2 de 4 listas» y la fracción para la barra. */
export function textoAvance(a: Avance | undefined): { texto: string; fraccion: number } {
  if (!a || !a.total) return { texto: '', fraccion: 0 }
  const registradas = a.secciones.filter((s) => s.estado === 'registrado').length
  return { texto: `${a.validadas} de ${a.total} listas`, fraccion: (a.validadas + registradas * 0.5) / a.total }
}

/** «S/ 90» o «S/ 82.50» (las líneas breves). */
export function solesCorto(n: number | null | undefined): string {
  const t = soles(n)
  return t.endsWith('.00') ? t.slice(0, -3) : t
}

/**
 * Lo que hará «Ajustar a lo sugerido», en UNA línea, antes de hacerlo (2026-10-18: Edison lo tocó y no
 * entendió qué hacía). `plan`: el de `POST /movilidad/ajustar {simular: true}`.
 */
export function textoPlan(plan: PasoPlan[]): string {
  const cambian = plan.filter((p) => p.cambia)
  if (!cambian.length) return 'Todos los días ya suman lo sugerido: no hay nada que ajustar.'
  const partes = cambian.slice(0, 3).map((p) => `${diaCorto(p.fecha)} a ${solesCorto(p.despues)} (hoy ${solesCorto(p.antes)})`)
  const mas = cambian.length > 3 ? ` y ${cambian.length - 3} día(s) más` : ''
  return `Pondrá ${partes.join(', ')}${mas}, repartido entre sus tramos. Los demás días quedan como están.`
}

/** Los parámetros que rigen, en lenguaje simple y con ejemplo (2026-10-18: «hoy son difíciles de entender»). */
export function lineasParametros(p: Record<string, Parametro>, dias: number, limite: string | null): { rotulo: string; valor: string; nota: string }[] {
  const tope = Number(p.tope_diario?.valor ?? 0)
  const pct = Number(p.pct_dj?.valor ?? 0)
  const topeDj = Number(p.tope_dj?.valor ?? 0)
  const recibido = Number(p.recibido_viaticos?.valor ?? 0)
  const plazo = Number(p.plazo_dias_habiles?.valor ?? 0)
  const lineas = [
    { rotulo: 'Viático por día', valor: `${solesCorto(tope)} por día`, nota: p.tope_diario?.norma ?? '' },
    { rotulo: 'Declaración jurada', valor: `hasta ${pct} % de lo recibido${recibido ? ` (${solesCorto(Math.round(recibido * pct) / 100)})` : ''}`, nota: `solo movilidad · ${p.pct_dj?.norma ?? ''}` },
    { rotulo: 'Movilidad por día', valor: `hasta ${solesCorto(topeDj)}`, nota: `${pct} % de ${solesCorto(tope)}` },
    { rotulo: 'Plazo para rendir', valor: `${plazo} días hábiles${limite ? `: hasta el ${fechaCorta(limite)}` : ''}`, nota: p.plazo_dias_habiles?.norma ?? '' },
  ]
  if (dias && tope) lineas.splice(1, 0, { rotulo: 'Viático de la comisión', valor: `${solesCorto(tope * dias)}`, nota: `${solesCorto(tope)} × ${dias} día(s)` })
  return lineas
}

/** El ejemplo que hace entender la movilidad del día. */
export function ejemploMovilidad(tope: number, topeDj: number): string {
  if (!tope || !topeDj) return ''
  const gastado = Math.round(tope * 0.72 / 10) * 10
  const falta = tope - gastado
  return `Ejemplo: si un día gastó ${solesCorto(gastado)} con comprobante, la movilidad de ese día llega a ${solesCorto(Math.min(topeDj, falta))} (lo que falta para ${solesCorto(tope)}, sin pasar ${solesCorto(topeDj)}).`
}

/** De dónde sale el importe recibido, en una línea. */
export function textoRecibido(p: Parametro | undefined): string {
  if (!p) return ''
  switch (p.origen) {
    case 'rendicion': return 'Anotado en esta rendición.'
    case 'comision': return `${p.fuente}.`
    case 'memorando': return `${p.fuente}.`
    case 'despacho': return 'Del ajuste del despacho.'
    default: return 'No consta: anótelo del memorando o del comprobante de pago. Mientras, se calcula con viático × días.'
  }
}


/** La línea que dice que «Ajustar a lo sugerido» nunca pasa los topes (2026-10-18, Edison: «¿altera o
 * sobrepasa los topes?»). */
export function lineaTopes(l: { tope_dj: number; tope_diario: number; pct_dj_max: number }): string {
  return `Nunca pasa los topes: ${solesCorto(l.tope_dj)} por día, ${solesCorto(l.tope_diario)} de viático, ${Number(l.pct_dj_max).toFixed(0)} % de lo recibido. Solo cambia los montos de los tramos.`
}

// --- La lista agrupada por comisión (2026-10-18: «la lista parece duplicada») ---------------------------

export interface GrupoComision {
  clave: string
  semana: SemanaVinculada | null
  lugar: string
  inicio: string
  fin: string
  filas: FilaLista[]
  /** El estado si es el mismo para todos; si no, null (cada fila lleva el suyo). */
  estadoComun: Estado | null
  /** El avance de la comisión: lo validado de todas sus rendiciones. */
  avance: { validadas: number; total: number; fraccion: number }
  limite: string | null
  /** Alguna sigue abierta (borrador, lista u observada): el grupo va arriba. */
  abierta: boolean
}

const ABIERTAS: Estado[] = ['borrador', 'lista', 'observada']

/**
 * Las rendiciones de una misma comisión, juntas: una cabecera (semana, fechas, avance y estado común) y una
 * fila por comisionado. Se agrupan por `comision_id` (o, sin él, por semana; si tampoco, cada una sola), en
 * el orden en que llegan (la más reciente primero); dentro, por nombre.
 */
export function agruparPorComision(filas: FilaLista[]): GrupoComision[] {
  const grupos = new Map<string, FilaLista[]>()
  for (const f of filas) {
    const clave = f.comision_id ? `c${f.comision_id}` : f.semana ? `s${f.semana.id}` : `r${f.id}`
    if (!grupos.has(clave)) grupos.set(clave, [])
    grupos.get(clave)!.push(f)
  }
  return [...grupos.entries()].map(([clave, fs]) => {
    const orden = [...fs].sort((a, b) => a.comisionado.localeCompare(b.comisionado, 'es'))
    const estados = new Set(orden.map((f) => f.estado))
    const validadas = orden.reduce((s, f) => s + (f.avance?.validadas ?? 0), 0)
    const total = orden.reduce((s, f) => s + (f.avance?.total ?? 0), 0)
    const fraccion = total ? orden.reduce((s, f) => s + textoAvance(f.avance).fraccion * (f.avance?.total ?? 0), 0) / total : 0
    const p = orden[0]
    return {
      clave, semana: p.semana, lugar: p.lugar ?? '', inicio: p.inicio, fin: p.fin, filas: orden,
      estadoComun: estados.size === 1 ? p.estado : null,
      avance: { validadas, total, fraccion },
      limite: orden.find((f) => correPlazo(f.estado))?.limite ?? null,
      abierta: orden.some((f) => ABIERTAS.includes(f.estado)),
    }
  })
}

/** «3 de 8 listas»: el avance de la comisión. */
export const textoAvanceComision = (a: { validadas: number; total: number }): string => (a.total ? `${a.validadas} de ${a.total} listas` : '')

// --- Comprobantes sin repetir (2026-10-18) ---------------------------------------------------------------

/** El orden en que se registran los comprobantes de un día («Guardar y siguiente»). */
export const ORDEN_DEL_DIA = ['desayuno', 'almuerzo', 'cena', 'otros_alimentacion', 'hospedaje'] as const
/** Lo que va UNA vez por día; el hospedaje y los otros pueden ser más de uno (solo se avisa). */
export const UNO_POR_DIA = ['desayuno', 'almuerzo', 'cena']

/** «una cena», «un desayuno»: el concepto con su artículo, para las líneas breves. */
export function unConcepto(concepto: string): string {
  const t: Record<string, string> = {
    desayuno: 'un desayuno', almuerzo: 'un almuerzo', cena: 'una cena', otros_alimentacion: 'otro gasto de alimentación',
    hospedaje: 'un hospedaje', pasaje_terrestre: 'un pasaje terrestre', otro_recurso: 'otro recurso',
  }
  return t[concepto] ?? conceptoDe(concepto).toLowerCase()
}

/** Lo ya registrado de un día (sin el comprobante que se está editando), en el orden del día. */
export function registradosDelDia(comprobantes: Comprobante[], fecha: string, sinId?: number | null): Comprobante[] {
  const pos = (c: string) => { const i = (ORDEN_DEL_DIA as readonly string[]).indexOf(c); return i < 0 ? 99 : i }
  return comprobantes
    .filter((c) => c.fecha === fecha && c.id !== sinId && (c.importe || c.numero))
    .sort((a, b) => pos(a.concepto) - pos(b.concepto) || a.orden - b.orden)
}

/**
 * ¿Se puede guardar ese concepto ese día? Un desayuno, un almuerzo y una cena por día: si ya hay uno, no
 * (`bloquea` con el que ya está); el hospedaje y los otros, sí, pero se avisa.
 */
export function revisarConcepto(concepto: string, registrados: Comprobante[]): { nivel: 'bloquea' | 'aviso' | ''; ya?: Comprobante } {
  const ya = registrados.find((c) => c.concepto === concepto)
  if (!ya) return { nivel: '' }
  return { nivel: UNO_POR_DIA.includes(concepto) ? 'bloquea' : 'aviso', ya }
}

/**
 * Lo que sigue tras «Guardar y siguiente»: el próximo concepto del día en orden (desayuno → almuerzo → cena →
 * otros de alimentación → hospedaje), saltando desayuno, almuerzo o cena ya registrados; al acabar, el día
 * siguiente. `ocupados`: {fecha: conceptos ya registrados} (con el recién guardado). Pasajes y otros recursos
 * no tienen orden: se quedan donde están.
 */
export function siguienteConcepto(concepto: string, fecha: string, dias: string[], ocupados: Record<string, string[]>): { fecha: string; concepto: string } {
  const orden = ORDEN_DEL_DIA as readonly string[]
  const i = orden.indexOf(concepto)
  if (i < 0) return { fecha, concepto }
  const libre = (f: string, c: string) => !(UNO_POR_DIA.includes(c) && (ocupados[f] ?? []).includes(c))
  for (let j = i + 1; j < orden.length; j++) if (libre(fecha, orden[j])) return { fecha, concepto: orden[j] }
  const resto = dias.slice(dias.indexOf(fecha) + 1)
  for (const f of resto) {
    const c = orden.find((x) => libre(f, x))
    if (c) return { fecha: f, concepto: c }
  }
  return { fecha, concepto: orden[orden.length - 1] }
}

/**
 * Dónde empieza un comprobante NUEVO: el primer día con alguna comida por registrar y, en él, el primer
 * concepto libre en orden (si todo está, el primer día y «otros de alimentación»).
 */
export function dondeEmpezar(dias: string[], ocupados: Record<string, string[]>): { fecha: string; concepto: string } {
  for (const f of dias) {
    const c = UNO_POR_DIA.find((x) => !(ocupados[f] ?? []).includes(x))
    if (c) return { fecha: f, concepto: c }
  }
  return { fecha: dias[0] ?? '', concepto: 'otros_alimentacion' }
}

/** {fecha: conceptos} de una lista de comprobantes (los que tienen datos). */
export function conceptosPorDia(comprobantes: Comprobante[]): Record<string, string[]> {
  const salida: Record<string, string[]> = {}
  for (const c of comprobantes) if (c.importe || c.numero) (salida[c.fecha] ??= []).push(c.concepto)
  return salida
}

// --- Revisión: comparar a los comisionados (2026-10-18) --------------------------------------------------

export interface DiaComparar {
  fecha: string; por_concepto: Record<string, number>; subtotal_a: number; movilidad: number; otros_dj: number; dj: number
  reconocido: number; exceso: number; saldo: number; cuantos: Record<string, number>
}
export interface PersonaComparar {
  id: number; codigo: string; estado: Estado; etiqueta_estado: string; comisionado: string; nombre: string; propia: boolean
  dias: DiaComparar[]
  totales: {
    rendido: number; reconocido: number; recibido: number; saldo: number; con_comprobante: number; dj: number; exceso: number
    pct_dj: number; pct_dj_max: number; pct_dj_ok: boolean; comprobantes: number; errores: number; pasajes: number; otros: number
  }
}
export interface FilaComparar { clave: string; rotulo: string; valores: number[]; cuantos?: number[]; difiere: boolean; formato: 'soles' | 'pct' | 'numero'; fuerte?: boolean }
export interface DiaComparado { fecha: string; filas: FilaComparar[]; diferencias: number }

const igual = (vs: number[]) => vs.every((v) => Math.round(v * 100) === Math.round(vs[0] * 100))

/**
 * La comparación lado a lado: por día, los comprobantes por concepto (con cuántos hay), la movilidad (la
 * misma), otros sin comprobante, lo reconocido y el saldo; y los totales (rendido, recibido, saldo y % de
 * declaración jurada). Cada fila dice si DIFIERE entre las personas; un concepto en cero para todos no sale.
 */
export function compararComision(personas: PersonaComparar[]): { dias: DiaComparado[]; totales: FilaComparar[]; diferencias: number } {
  const fechas = [...new Set(personas.flatMap((p) => p.dias.map((d) => d.fecha)))].sort()
  const del = (p: PersonaComparar, f: string) => p.dias.find((d) => d.fecha === f)
  const fila = (clave: string, rotulo: string, valores: number[], extra: Partial<FilaComparar> = {}): FilaComparar =>
    ({ clave, rotulo, valores, difiere: personas.length > 1 && !igual(valores), formato: 'soles', ...extra })
  const dias = fechas.map((f) => {
    const filas: FilaComparar[] = []
    for (const c of CONCEPTOS.filter((x) => x.seccion === 'A')) {
      const valores = personas.map((p) => del(p, f)?.por_concepto[c.v] ?? 0)
      const cuantos = personas.map((p) => del(p, f)?.cuantos[c.v] ?? 0)
      if (valores.every((v) => !v) && cuantos.every((n) => !n)) continue
      const x = fila(c.v, c.t, valores, { cuantos })
      x.difiere = x.difiere || (personas.length > 1 && !cuantos.every((n) => n === cuantos[0]))
      filas.push(x)
    }
    filas.push(fila('movilidad', 'Movilidad (la misma)', personas.map((p) => del(p, f)?.movilidad ?? 0)))
    const otros = personas.map((p) => del(p, f)?.otros_dj ?? 0)
    if (otros.some(Boolean)) filas.push(fila('otros_dj', 'Otros sin comprobante', otros))
    filas.push(fila('reconocido', 'Reconocido', personas.map((p) => del(p, f)?.reconocido ?? 0)))
    filas.push(fila('saldo', 'Saldo del día', personas.map((p) => del(p, f)?.saldo ?? 0), { fuerte: true }))
    return { fecha: f, filas, diferencias: filas.filter((x) => x.difiere).length }
  })
  const t = (k: keyof PersonaComparar['totales']) => personas.map((p) => Number(p.totales[k] ?? 0))
  const totales: FilaComparar[] = [
    fila('comprobantes', 'Comprobantes', t('comprobantes'), { formato: 'numero' }),
    fila('con_comprobante', 'Con comprobante', t('con_comprobante')),
    fila('dj', 'Declaración jurada', t('dj')),
    fila('reconocido', 'Rendido', t('reconocido'), { fuerte: true }),
    fila('recibido', 'Recibido', t('recibido')),
    fila('saldo', 'Saldo a devolver', t('saldo'), { fuerte: true }),
    fila('pct_dj', 'Declaración jurada (%)', t('pct_dj'), { formato: 'pct' }),
  ]
  return { dias, totales, diferencias: dias.reduce((s, d) => s + d.diferencias, 0) + totales.filter((x) => x.difiere).length }
}

/** Un valor de la comparación con su formato. */
export function valorComparar(v: number, formato: FilaComparar['formato']): string {
  return formato === 'pct' ? `${v.toFixed(2)} %` : formato === 'numero' ? String(v) : soles(v)
}
