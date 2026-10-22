/**
 * CALCULADORA — la parte pura (2026-10-18, pedido de Edison: «una calculadora dentro del módulo, práctica,
 * funcional y fácil de usar»). Evalúa una expresión con + − × ÷, paréntesis, porcentaje y decimales con
 * punto o coma, SIN `eval`: un analizador de descenso recursivo. Redondea a céntimos para no mostrar
 * 0.30000000000000004. La interfaz está en `componentes/Calculadora.tsx`; pruebas en `pruebas/calculadora.test.ts`.
 */

/** «12,5 + 3» → «12.5+3»; «×» y «x» → «*»; «÷» → «/»; «−» → «-». */
export function normalizar(expr: string): string {
  return (expr ?? '')
    .replace(/[×xX]/g, '*')
    .replace(/÷/g, '/')
    .replace(/[−–]/g, '-')
    .replace(/(\d),(\d)/g, '$1.$2')
    .replace(/S\/\s*/gi, '')
    .replace(/\s+/g, '')
}

/**
 * El valor de la expresión, o `null` si no se puede calcular (vacía, incompleta o dividida entre cero).
 * `50%` es 0.5; `200+10%` es 220 y `200-10%` es 180 (como en una calculadora de bolsillo).
 */
export function evaluar(expr: string): number | null {
  const s = normalizar(expr)
  if (!s) return null
  let i = 0
  const ver = () => s[i]
  const numero = (): number | null => {
    const m = /^\d*\.?\d+|^\d+\./.exec(s.slice(i))
    if (!m) return null
    i += m[0].length
    return Number(m[0])
  }
  // factor := ('-'|'+') factor | numero | '(' suma ')'
  const factor = (): number | null => {
    if (ver() === '-') { i++; const f = factor(); return f === null ? null : -f }
    if (ver() === '+') { i++; return factor() }
    if (ver() === '(') {
      i++
      const v = suma()
      if (v === null) return null
      if (ver() === ')') i++
      return v
    }
    return numero()
  }
  // con porcentaje: «50%» = 0.5
  const postfijo = (): { v: number; pct: boolean } | null => {
    const v = factor()
    if (v === null) return null
    if (ver() === '%') { i++; return { v: v / 100, pct: true } }
    return { v, pct: false }
  }
  const producto = (): number | null => {
    const a = postfijo()
    if (a === null) return null
    let v = a.v
    while (ver() === '*' || ver() === '/') {
      const op = s[i++]
      const b = postfijo()
      if (b === null) return null
      if (op === '/' && b.v === 0) return null
      v = op === '*' ? v * b.v : v / b.v
    }
    return v
  }
  const suma = (): number | null => {
    const primero = producto()
    if (primero === null) return null
    let v = primero
    while (ver() === '+' || ver() === '-') {
      const op = s[i++]
      const inicio = i
      const b = producto()
      if (b === null) return null
      // «200+10%»: el porcentaje es DE lo que va antes.
      const esPct = s.slice(inicio, i).endsWith('%') && !/[*/]/.test(s.slice(inicio, i))
      const cuanto = esPct ? v * b : b
      v = op === '+' ? v + cuanto : v - cuanto
    }
    return v
  }
  const v = suma()
  if (v === null || i !== s.length || !Number.isFinite(v)) return null
  return Math.round(v * 100) / 100
}

/** 1234.5 → «1,234.50» (como los importes del módulo). */
export function formatear(n: number): string {
  const signo = n < 0 ? '-' : ''
  const c = Math.round(Math.abs(n) * 100)
  return `${signo}${Math.floor(c / 100).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${String(c % 100).padStart(2, '0')}`
}
