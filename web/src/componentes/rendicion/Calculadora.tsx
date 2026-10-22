/**
 * CALCULADORA en hoja inferior (2026-10-18, pedido de Edison: «práctica, funcional y fácil de usar; que
 * permita usar un resultado en el campo de importe que se está llenando»). Teclado grande para el pulgar y,
 * en escritorio, también se escribe con el teclado (Enter = resultado). Con `alUsar`, el botón «Usar S/ …»
 * pone el resultado en el campo que la abrió; sin él, «Copiar». La cuenta la hace `calculadora.ts` (sin
 * `eval`). Las últimas cuentas quedan a mano mientras la hoja esté abierta.
 */
import { useEffect, useRef, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import ButtonBase from '@mui/material/ButtonBase'
import Drawer from '@mui/material/Drawer'
import IconButton from '@mui/material/IconButton'
import InputBase from '@mui/material/InputBase'
import Typography from '@mui/material/Typography'
import BackspaceOutlinedIcon from '@mui/icons-material/BackspaceOutlined'
import CloseIcon from '@mui/icons-material/Close'
import { evaluar, formatear } from './calculadora'
import { copiarTexto } from './apoyo'
import { PALETA } from '@qillqa/tiqsi'

const TECLAS = ['C', '(', ')', '÷', '7', '8', '9', '×', '4', '5', '6', '−', '1', '2', '3', '+', '0', '.', '%', '⌫']

// La hoja que sube desde abajo, como las de Qillqa (componentes/HojaInferior.tsx): Rendición la trae consigo.
const PAPEL_HOJA = { borderTopLeftRadius: 16, borderTopRightRadius: 16, pb: 'env(safe-area-inset-bottom)', maxHeight: '85dvh', mx: 'auto' } as const
const Asa = () => <Box sx={{ width: 36, height: 4, borderRadius: 2, bgcolor: 'divider', mx: 'auto', mt: 1, flexShrink: 0 }} />

export default function Calculadora({ abierta, alCerrar, inicial = '', alUsar, titulo }: {
  abierta: boolean
  alCerrar: () => void
  /** Lo que ya tenía el campo (se puede seguir la cuenta desde ahí). */
  inicial?: string
  /** Si se pasa, «Usar» pone el resultado en el campo que abrió la calculadora. */
  alUsar?: (valor: number) => void
  titulo?: string
}) {
  const [expr, setExpr] = useState('')
  const [historia, setHistoria] = useState<{ expr: string; v: number }[]>([])
  const [copiado, setCopiado] = useState(false)
  const entrada = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    if (!abierta) return
    setExpr(inicial && Number(String(inicial).replace(',', '.')) ? String(inicial) : '')
    setCopiado(false)
    setTimeout(() => entrada.current?.focus(), 80)
  }, [abierta, inicial])

  const valor = evaluar(expr)
  const tocar = (t: string) => {
    if (t === 'C') setExpr('')
    else if (t === '⌫') setExpr((e) => e.slice(0, -1))
    else setExpr((e) => e + t)
  }
  const igual = () => {
    if (valor === null) return
    setHistoria((h) => [{ expr, v: valor }, ...h].slice(0, 3))
    setExpr(String(valor))
  }
  const usar = () => {
    if (valor === null) return
    if (alUsar) { alUsar(valor); alCerrar() } else {
      void copiarTexto(valor.toFixed(2)).then(() => setCopiado(true))
    }
  }

  const tecla = (t: string) => {
    const operador = ['÷', '×', '−', '+', '%', '(', ')'].includes(t)
    const accion = t === 'C' || t === '⌫'
    return (
      <ButtonBase key={t} focusRipple onClick={() => tocar(t)} aria-label={t === '⌫' ? 'Borrar' : t === 'C' ? 'Limpiar' : t}
        sx={{
          height: { xs: 52, sm: 46 }, borderRadius: 2, fontSize: 20, fontWeight: operador || accion ? 600 : 500,
          bgcolor: operador ? PALETA.superficieMedia : accion ? 'transparent' : PALETA.superficieTenue,
          color: accion ? PALETA.guinda : 'text.primary', border: accion ? '1px solid' : 'none', borderColor: 'divider',
          '&:hover': { bgcolor: PALETA.superficieMedia },
        }}>
        {t === '⌫' ? <BackspaceOutlinedIcon fontSize="small" /> : t}
      </ButtonBase>
    )
  }

  return (
    // Por encima de los diálogos (se abre desde el campo de un comprobante, que es un diálogo).
    <Drawer anchor="bottom" open={abierta} onClose={alCerrar} sx={{ zIndex: (t) => t.zIndex.modal + 2 }} PaperProps={{ sx: { ...PAPEL_HOJA, width: '100%', maxWidth: 420 } }}>
      <Asa />
      <Box sx={{ px: 2, pt: 1, pb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
          <Typography sx={{ fontWeight: 700, fontSize: 15.5, flex: 1 }}>{titulo ?? 'Calculadora'}</Typography>
          <IconButton size="small" aria-label="Cerrar" onClick={alCerrar}><CloseIcon fontSize="small" /></IconButton>
        </Box>
        <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2, px: 1.5, py: 1, mb: 1.25, bgcolor: 'background.paper' }}>
          {historia.length > 0 && (
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 0.5 }}>
              {historia.map((h, i) => (
                <ButtonBase key={i} onClick={() => setExpr((e) => e + String(h.v))} sx={{ fontSize: 12, color: 'text.secondary', borderRadius: 1, px: 0.5 }}>
                  {h.expr} = <b>&nbsp;{formatear(h.v)}</b>
                </ButtonBase>
              ))}
            </Box>
          )}
          <InputBase inputRef={entrada} fullWidth value={expr} placeholder="Escriba o toque: 320 − 230"
            onChange={(e) => setExpr(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); if (alUsar && expr === String(valor)) usar(); else igual() } }}
            inputProps={{ inputMode: 'none', 'aria-label': 'Cuenta', style: { textAlign: 'right', fontSize: 20 } }} />
          <Typography sx={{ textAlign: 'right', fontSize: 26, fontWeight: 700, color: valor === null ? 'text.disabled' : PALETA.guinda, lineHeight: 1.3 }}>
            {valor === null ? (expr ? '…' : '0.00') : `S/ ${formatear(valor)}`}
          </Typography>
        </Box>
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 0.75 }}>
          {TECLAS.map(tecla)}
        </Box>
        <Box sx={{ display: 'flex', gap: 1, mt: 1.25 }}>
          <Button variant="outlined" sx={{ flex: 1, height: 46 }} disabled={valor === null} onClick={igual}>=</Button>
          <Button variant="contained" sx={{ flex: 2, height: 46 }} disabled={valor === null} onClick={usar}>
            {alUsar ? (valor === null ? 'Usar' : `Usar S/ ${formatear(valor)}`) : copiado ? 'Copiado' : 'Copiar el resultado'}
          </Button>
        </Box>
      </Box>
    </Drawer>
  )
}
