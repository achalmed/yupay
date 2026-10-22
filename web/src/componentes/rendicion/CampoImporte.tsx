/**
 * Un campo de importe en soles con su CALCULADORA (2026-10-18): el ícono de la derecha abre la hoja inferior
 * con lo que ya tenía el campo, y «Usar S/ …» pone el resultado aquí. Se usa en el comprobante, el tramo,
 * los otros gastos, el importe recibido y la DJ del día.
 */
import { useState } from 'react'
import IconButton from '@mui/material/IconButton'
import InputAdornment from '@mui/material/InputAdornment'
import TextField, { type TextFieldProps } from '@mui/material/TextField'
import Tooltip from '@mui/material/Tooltip'
import CalculateOutlinedIcon from '@mui/icons-material/CalculateOutlined'
import Calculadora from './Calculadora'

export default function CampoImporte({ value, alCambiar, disabled, ...resto }: Omit<TextFieldProps, 'onChange' | 'value'> & {
  value: string
  alCambiar: (v: string) => void
}) {
  const [calc, setCalc] = useState(false)
  return (
    <>
      <TextField
        {...resto}
        value={value}
        disabled={disabled}
        onChange={(e) => alCambiar(e.target.value)}
        inputProps={{ inputMode: 'decimal', ...(resto.inputProps ?? {}) }}
        InputProps={{
          ...(resto.InputProps ?? {}),
          startAdornment: <InputAdornment position="start">S/</InputAdornment>,
          endAdornment: !disabled && (
            <InputAdornment position="end">
              <Tooltip title="Calculadora">
                <IconButton size="small" edge="end" aria-label="Abrir la calculadora" onClick={() => setCalc(true)}>
                  <CalculateOutlinedIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </InputAdornment>
          ),
        }}
      />
      <Calculadora abierta={calc} alCerrar={() => setCalc(false)} inicial={value} titulo={typeof resto.label === 'string' ? resto.label : undefined}
        alUsar={(v) => alCambiar(v.toFixed(2))} />
    </>
  )
}
