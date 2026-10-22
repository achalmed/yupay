// Pruebas de la lógica pura de la rendición de cuentas (2026-10-18). Correr desde frontend/:
//   node --test pruebas/*.test.ts
// El cálculo lo hace el servidor (backend/tests/test_rendicion.py); aquí, lo que la web compone.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { agruparPorComision, compararComision, conceptosPorDia, dondeEmpezar, correPlazo, lineaTopes, registradosDelDia, revisarConcepto, siguienteConcepto, textoAvanceComision, type Comprobante, type FilaLista, type PersonaComparar } from '../src/componentes/rendicion/modelo.ts'
import { diaCorto, ejemploMovilidad, fechaCorta, lineasParametros, partirNumero, pasoDeControl, porDia, rucValido, semanaPorDefecto, siguienteTramo, soles, solesCorto, textoAvance, textoPlan, textoPlazo, textoRecibido } from '../src/componentes/rendicion/modelo.ts'

test('soles con miles, céntimos y signo', () => {
  assert.equal(soles(2345.6), 'S/ 2,345.60')
  assert.equal(soles(0), 'S/ 0.00')
  assert.equal(soles(-10), '-S/ 10.00')
  assert.equal(soles(0.1 + 0.2), 'S/ 0.30')
  assert.equal(soles(1234567.891), 'S/ 1,234,567.89')
})

test('fechas cortas', () => {
  assert.equal(fechaCorta('2026-08-24'), '24/08/2026')
  assert.equal(diaCorto('2026-08-24'), 'lun 24/08')
  assert.equal(fechaCorta(''), '')
})

test('plazo: por vencer, hoy, vencido y fuera de los estados abiertos', () => {
  assert.equal(textoPlazo('2026-09-11', '2026-09-08', 'borrador'), 'Hasta el 11/09/2026 · faltan 3 días')
  assert.equal(textoPlazo('2026-09-11', '2026-09-10', 'lista'), 'Hasta el 11/09/2026 · falta 1 día')
  assert.equal(textoPlazo('2026-09-11', '2026-09-11', 'lista'), 'Vence hoy')
  // Presentada, observada o cerrada ya se rindió: sin «Vencida» (2026-10-18).
  assert.equal(textoPlazo('2026-09-11', '2026-09-20', 'observada'), '')
  assert.equal(textoPlazo('2026-09-11', '2026-09-20', 'cerrada'), '')
  assert.deepEqual((['borrador', 'lista', 'presentada', 'observada', 'cerrada'] as const).map(correPlazo), [true, true, false, false, false])
  assert.equal(textoPlazo('2026-09-11', '2026-09-20', 'borrador'), 'Vencida el 11/09/2026')
  assert.equal(textoPlazo('2026-09-11', '2026-09-20', 'presentada'), '')
  assert.equal(textoPlazo(null, '2026-09-20', 'borrador'), '')
})

test('por día: los de la comisión en orden, días vacíos fuera, lo de fuera al final', () => {
  const dias = ['2026-08-24', '2026-08-25']
  const g = porDia([{ fecha: '2026-08-25', n: 1 }, { fecha: '2026-08-23', n: 2 }, { fecha: '2026-08-25', n: 3 }], dias)
  assert.deepEqual(g.map((x) => [x.fecha, x.filas.length, x.fuera]), [['2026-08-25', 2, false], ['2026-08-23', 1, true]])
  const sinFecha = porDia([{ fecha: '' }], dias)
  assert.equal(sinFecha[0].fuera, true)
})

test('cada control lleva a su paso', () => {
  assert.equal(pasoDeControl({ codigo: 'sin_foto', nivel: 'aviso', texto: '', ref: 'comprobante:3' }), 'comprobantes')
  assert.equal(pasoDeControl({ codigo: 'dj_tope', nivel: 'error', texto: '', dia: '2026-08-24' }), 'movilidad')
  assert.equal(pasoDeControl({ codigo: 'sin_memorando', nivel: 'aviso', texto: '' }), 'datos')
  assert.equal(pasoDeControl({ codigo: 'saldo', nivel: 'info', texto: '' }), 'revision')
})

test('RUC con dígito verificador', () => {
  const conVerificador = (base: string) => {
    const pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    const resto = 11 - (pesos.reduce((s, p, i) => s + p * Number(base[i]), 0) % 11)
    return base + String(resto >= 10 ? resto - 10 : resto)
  }
  assert.ok(rucValido(conVerificador('2060000000')))
  assert.ok(rucValido(''))
  assert.ok(!rucValido('3060000000' + '1'))
  assert.ok(!rucValido('123'))
})

test('número corto de un comprobante', async () => {
  const { numeroCorto } = await import('../src/componentes/rendicion/modelo.ts')
  assert.equal(numeroCorto({ tipo: 'boleta_electronica', serie: 'EB01', numero: '0101' }), 'Boleta EB01-0101')
  assert.equal(numeroCorto({ tipo: 'ticket', serie: '', numero: '777' }), 'Ticket 777')
  assert.equal(numeroCorto({ tipo: 'otro', serie: '', numero: '' }), 'Comprobante')
})

test('el número del comprobante escrito de una pieza se parte en serie y número', () => {
  assert.deepEqual(partirNumero('', 'EB01-1586'), { serie: 'EB01', numero: '1586' })
  assert.deepEqual(partirNumero('', 'F001 - 00004711'), { serie: 'F001', numero: '00004711' })
  assert.deepEqual(partirNumero('', 'FR95 / 12841'), { serie: 'FR95', numero: '12841' })
  assert.deepEqual(partirNumero('', '001 026812'), { serie: '001', numero: '026812' })
  assert.deepEqual(partirNumero('', '12345'), { serie: '', numero: '12345' })
  assert.deepEqual(partirNumero('eb01', '1586'), { serie: 'EB01', numero: '1586' })
})

test('la semana por defecto es la última que terminó', () => {
  const semanas = [
    { id: 4, inicio: '2026-12-07', fin: '2026-12-11' }, { id: 1, inicio: '2026-08-24', fin: '2026-08-28' },
    { id: 2, inicio: '2026-09-21', fin: '2026-09-25' },
  ]
  assert.equal(semanaPorDefecto(semanas, '2026-10-18'), 2)
  assert.equal(semanaPorDefecto(semanas, '2026-08-01'), 1)
  assert.equal(semanaPorDefecto([], '2026-08-01'), '')
})

test('el tramo siguiente sale de donde llegó el anterior', () => {
  assert.deepEqual(siguienteTramo({ fecha: '2026-08-24', hasta: 'Plaza de Armas' }),
    { fecha: '2026-08-24', hora: '', desde: 'Plaza de Armas', hasta: '', concepto: '', monto: '' })
})

test('el avance cuenta lo validado y medio lo registrado', () => {
  const a = { validadas: 1, total: 4, secciones: [
    { clave: 'datos', etiqueta: 'Datos', estado: 'validado', texto: '' }, { clave: 'comprobantes', etiqueta: 'Comprobantes', estado: 'registrado', texto: '' },
    { clave: 'movilidad', etiqueta: 'Movilidad', estado: 'pendiente', texto: '' }, { clave: 'documento', etiqueta: 'Documento', estado: 'pendiente', texto: '' },
  ] } as const
  const r = textoAvance({ ...a, secciones: [...a.secciones] })
  assert.equal(r.texto, '1 de 4 listas')
  assert.equal(r.fraccion, 0.375)
  assert.equal(textoAvance(undefined).texto, '')
})

test('movilidad compartida: el plan de «Ajustar» en una línea y los tramos llevan a Movilidad', () => {
  const plan = [
    { fecha: '2026-08-24', antes: 90, despues: 96, cambia: true, explicacion: '' },
    { fecha: '2026-08-25', antes: 96, despues: 96, cambia: false, explicacion: '' },
  ]
  assert.equal(textoPlan(plan), 'Pondrá lun 24/08 a S/ 96 (hoy S/ 90), repartido entre sus tramos. Los demás días quedan como están.')
  assert.match(textoPlan([plan[1]]), /no hay nada que ajustar/)
  assert.equal(pasoDeControl({ codigo: 'sin_importe', nivel: 'aviso', texto: '', ref: 'tramo:4' }), 'movilidad')
  assert.equal(pasoDeControl({ codigo: 'recibido_supuesto', nivel: 'aviso', texto: '' }), 'datos')
  assert.equal(solesCorto(82.5), 'S/ 82.50')
  assert.equal(solesCorto(90), 'S/ 90')
})

test('parámetros en lenguaje simple, con ejemplo y de dónde sale lo recibido', () => {
  const p = {
    tope_diario: { valor: 320, etiqueta: '', norma: 'D.S. 007-2013-EF', fuente: '', origen: 'fabrica' as const },
    pct_dj: { valor: 30, etiqueta: '', norma: 'DI 37-2025-DF-DGA-CR', fuente: '', origen: 'fabrica' as const },
    tope_dj: { valor: 96, etiqueta: '', fuente: '', origen: 'fabrica' as const },
    recibido_viaticos: { valor: 1600, etiqueta: '', fuente: 'Del memorando MEM-0001', origen: 'memorando' as const },
    plazo_dias_habiles: { valor: 10, etiqueta: '', norma: 'DI 37-2025-DF-DGA-CR', fuente: '', origen: 'fabrica' as const },
  }
  const l = lineasParametros(p, 5, '2026-09-11')
  assert.deepEqual(l[0], { rotulo: 'Viático por día', valor: 'S/ 320 por día', nota: 'D.S. 007-2013-EF' })
  assert.equal(l.find((x) => x.rotulo === 'Declaración jurada')?.valor, 'hasta 30 % de lo recibido (S/ 480)')
  assert.equal(l.find((x) => x.rotulo === 'Plazo para rendir')?.valor, '10 días hábiles: hasta el 11/09/2026')
  assert.equal(ejemploMovilidad(320, 96), 'Ejemplo: si un día gastó S/ 230 con comprobante, la movilidad de ese día llega a S/ 90 (lo que falta para S/ 320, sin pasar S/ 96).')
  assert.equal(textoRecibido(p.recibido_viaticos), 'Del memorando MEM-0001.')
  assert.match(textoRecibido({ ...p.recibido_viaticos, origen: 'supuesto' }), /No consta/)
})


const fila = (id: number, comisionado: string, extra: Partial<FilaLista> = {}): FilaLista => ({
  id, codigo: `R-00${id}`, estado: 'borrador', etiqueta_estado: 'Borrador', comisionado, usuario_id: id, semana: null, memorando: null,
  inicio: '2026-08-24', fin: '2026-08-28', recibido: 1600, reconocido: 1000, saldo: 600, comprobantes: 3, errores: 0, avisos: 0,
  limite: '2026-09-11', vencida: false, pendientes: 0, comision_id: 1,
  avance: { secciones: [], validadas: 2, total: 4 }, ...extra,
})

test('la lista se agrupa por comisión: una cabecera y una fila por comisionado', () => {
  const g = agruparPorComision([fila(2, 'Zoila Ruiz'), fila(1, 'Ana Pérez'), fila(3, 'Luis Rojas', { comision_id: 2, estado: 'presentada' })])
  assert.equal(g.length, 2)
  assert.deepEqual(g[0].filas.map((f) => f.comisionado), ['Ana Pérez', 'Zoila Ruiz'])
  assert.equal(g[0].estadoComun, 'borrador')
  assert.equal(textoAvanceComision(g[0].avance), '4 de 8 listas')
  assert.equal(g[0].abierta, true)
  assert.equal(g[1].abierta, false)
  assert.equal(g[1].limite, null)   // presentada: el plazo ya no corre
  const mixto = agruparPorComision([fila(1, 'Ana'), fila(2, 'Luis', { estado: 'presentada' })])
  assert.equal(mixto[0].estadoComun, null)
  assert.equal(agruparPorComision([fila(1, 'Ana', { comision_id: undefined }), fila(2, 'Luis', { comision_id: undefined })]).length, 2)
})

const comp = (id: number, fecha: string, concepto: string, importe = 10): Comprobante => ({
  id, orden: id, fecha, tipo: 'boleta_electronica', serie: 'EB01', numero: String(id), ruc: '', proveedor: '', concepto, importe,
  archivo: '', nota: '', origen: 'manual', documento: `Boleta EB01-${id}`,
})

test('comprobantes sin repetir: lo registrado del día, uno por día y el siguiente concepto', () => {
  const dias = ['2026-08-24', '2026-08-25']
  const todos = [comp(1, dias[0], 'hospedaje'), comp(2, dias[0], 'desayuno'), comp(3, dias[1], 'almuerzo')]
  assert.deepEqual(registradosDelDia(todos, dias[0]).map((c) => c.concepto), ['desayuno', 'hospedaje'])
  assert.deepEqual(registradosDelDia(todos, dias[0], 2).map((c) => c.id), [1])
  const del0 = registradosDelDia(todos, dias[0])
  assert.equal(revisarConcepto('desayuno', del0).nivel, 'bloquea')
  assert.equal(revisarConcepto('hospedaje', del0).nivel, 'aviso')
  assert.equal(revisarConcepto('cena', del0).nivel, '')
  const ocupados = { [dias[0]]: ['desayuno', 'hospedaje'], [dias[1]]: ['almuerzo'] }
  assert.deepEqual(siguienteConcepto('desayuno', dias[0], dias, ocupados), { fecha: dias[0], concepto: 'almuerzo' })
  assert.deepEqual(siguienteConcepto('cena', dias[0], dias, ocupados), { fecha: dias[0], concepto: 'otros_alimentacion' })
  // Al acabar el día, al siguiente, saltando lo que ya tiene (el almuerzo del 25).
  assert.deepEqual(siguienteConcepto('hospedaje', dias[0], dias, ocupados), { fecha: dias[1], concepto: 'desayuno' })
  assert.deepEqual(siguienteConcepto('desayuno', dias[1], dias, { ...ocupados, [dias[1]]: ['desayuno', 'almuerzo'] }), { fecha: dias[1], concepto: 'cena' })
  assert.deepEqual(siguienteConcepto('pasaje_terrestre', dias[0], dias, ocupados), { fecha: dias[0], concepto: 'pasaje_terrestre' })
  assert.deepEqual(Object.fromEntries(Object.entries(conceptosPorDia(todos)).map(([k, v]) => [k, [...v].sort()])), ocupados)
  // Un comprobante nuevo empieza en el primer día con una comida por registrar.
  assert.deepEqual(dondeEmpezar(dias, ocupados), { fecha: dias[0], concepto: 'almuerzo' })
  assert.deepEqual(dondeEmpezar(dias, { [dias[0]]: ['desayuno', 'almuerzo', 'cena'] }), { fecha: dias[1], concepto: 'desayuno' })
})

test('revisión: comparar a los comisionados resalta lo que difiere', () => {
  const dia = (almuerzo: number, saldo: number, cuantos = 1) => ({
    fecha: '2026-08-24', por_concepto: { desayuno: 0, almuerzo, cena: 0, otros_alimentacion: 0, hospedaje: 80 }, subtotal_a: almuerzo + 80,
    movilidad: 96, otros_dj: 0, dj: 96, reconocido: 320 - saldo, exceso: 0, saldo, cuantos: { almuerzo: cuantos, hospedaje: 1 },
  })
  const persona = (id: number, almuerzo: number, saldo: number, recibido: number): PersonaComparar => ({
    id, codigo: `R-00${id}`, estado: 'borrador', etiqueta_estado: 'Borrador', comisionado: `P${id}`, nombre: `Persona ${id}`, propia: id === 1,
    dias: [dia(almuerzo, saldo)],
    totales: { rendido: 1, reconocido: 320 - saldo, recibido, saldo: recibido - 320 + saldo, con_comprobante: almuerzo + 80, dj: 96, exceso: 0, pct_dj: 30, pct_dj_max: 30, pct_dj_ok: true, comprobantes: 2, errores: 0, pasajes: 0, otros: 0 },
  })
  const c = compararComision([persona(1, 25, 119), persona(2, 30, 114, 320)].map((p, i) => (i === 0 ? { ...p, totales: { ...p.totales, recibido: 320 } } : p)))
  const filas = Object.fromEntries(c.dias[0].filas.map((f) => [f.clave, f]))
  assert.equal(filas.almuerzo.difiere, true)
  assert.equal(filas.hospedaje.difiere, false)
  assert.equal(filas.movilidad.difiere, false)
  assert.equal(filas.desayuno, undefined)   // en cero para todos: no sale
  assert.equal(filas.saldo.difiere, true)
  assert.ok(c.diferencias >= 3)
})

test('la línea de los topes del ajuste', () => {
  assert.equal(lineaTopes({ tope_dj: 96, tope_diario: 320, pct_dj_max: 30 }), 'Nunca pasa los topes: S/ 96 por día, S/ 320 de viático, 30 % de lo recibido. Solo cambia los montos de los tramos.')
})
