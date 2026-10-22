// Pruebas de la calculadora del módulo de rendición (2026-10-18). Correr desde frontend/:
//   node --test pruebas/*.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { evaluar, formatear, normalizar } from '../src/componentes/rendicion/calculadora.ts'

test('operaciones con prioridad, paréntesis y signos', () => {
  assert.equal(evaluar('12.5 + 3'), 15.5)
  assert.equal(evaluar('2+3×4'), 14)
  assert.equal(evaluar('(2+3)*4'), 20)
  assert.equal(evaluar('320 − 230'), 90)
  assert.equal(evaluar('-5+10'), 5)
  assert.equal(evaluar('96 ÷ 8'), 12)
  assert.equal(evaluar('0.1+0.2'), 0.3)
})

test('coma decimal, «S/» y porcentaje como en una calculadora de bolsillo', () => {
  assert.equal(normalizar('S/ 12,50 x 2'), '12.50*2')
  assert.equal(evaluar('S/ 12,50 x 2'), 25)
  assert.equal(evaluar('30%'), 0.3)
  assert.equal(evaluar('1600*30%'), 480)
  assert.equal(evaluar('200+10%'), 220)
  assert.equal(evaluar('200-10%'), 180)
})

test('lo incompleto o imposible no da número', () => {
  assert.equal(evaluar(''), null)
  assert.equal(evaluar('5+'), null)
  assert.equal(evaluar('5/0'), null)
  assert.equal(evaluar('abc'), null)
})

test('formato con miles y céntimos', () => {
  assert.equal(formatear(1234.5), '1,234.50')
  assert.equal(formatear(-3), '-3.00')
})
