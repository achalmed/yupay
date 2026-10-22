/**
 * ANTES DE EMPEZAR (2026-10-18, Edison: «una ventana cuando entren por primera vez a su rendición para que
 * actualicen los montos que recibieron; que comiencen por lo más importante y después llenen lo demás»).
 * Sale una sola vez por rendición en borrador: pide lo que cambia de una Semana a otra (cuánto se
 * recibió de viáticos, pasajes terrestres y otros recursos) y muestra en una línea lo que el sistema ya
 * trae solo (fechas, días y memorando). «Guardar y empezar» deja la marca `inicio_confirmado` y lleva a
 * Comprobantes; «Más tarde» la cierra solo por esta vez.
 */
import { useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Checkbox from '@mui/material/Checkbox'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import FormControlLabel from '@mui/material/FormControlLabel'
import InputAdornment from '@mui/material/InputAdornment'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import { api } from '@qillqa/tiqsi'
import { PALETA } from '@qillqa/tiqsi'
import { diaCorto, type Rendicion } from './modelo'

const clavePosponer = (id: number) => `qillqa_rend_inicio_${id}`

/** ¿Hay que mostrarla? Borrador, no confirmada y no pospuesta en esta sesión. */
export function tocaInicio(r: Rendicion, soloLectura: boolean): boolean {
  if (soloLectura || r.estado !== 'borrador') return false
  if (String((r.datos_propios as Record<string, unknown>).inicio_confirmado ?? '') === 'si') return false
  try { return sessionStorage.getItem(clavePosponer(r.id)) !== '1' } catch { return true }
}

const numero = (v: string) => v.replace(',', '.').replace(/[^\d.]/g, '')

export default function InicioRendicion({ r, abierta, alCerrar, alGuardado }: {
  r: Rendicion
  abierta: boolean
  alCerrar: () => void
  /** Con la rendición ya guardada: el padre la recarga y lleva a Comprobantes. */
  alGuardado: (nueva: Rendicion) => void
}) {
  const rec = r.parametros.recibido_viaticos
  const [viaticos, setViaticos] = useState('')
  const [pasajes, setPasajes] = useState('')
  const [otros, setOtros] = useState('')
  const [paraTodos, setParaTodos] = useState(true)
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState('')
  const variasPersonas = (r.comision?.miembros?.length ?? 0) > 1

  useEffect(() => {
    if (!abierta) return
    // Lo que ya consta se propone; lo supuesto (viático × días) también, pero marcado como por confirmar.
    setViaticos(rec?.valor != null ? String(rec.valor) : '')
    setPasajes(r.parametros.recibido_pasajes?.valor ? String(r.parametros.recibido_pasajes.valor) : '')
    setOtros(r.parametros.recibido_otros?.valor ? String(r.parametros.recibido_otros.valor) : '')
    setParaTodos(rec?.origen === 'comision' || (variasPersonas && rec?.origen !== 'rendicion'))
    setError('')
  }, [abierta]) // eslint-disable-line react-hooks/exhaustive-deps

  const posponer = () => {
    try { sessionStorage.setItem(clavePosponer(r.id), '1') } catch { /* sin almacenamiento: sale otra vez */ }
    alCerrar()
  }

  const guardar = async () => {
    const v = numero(viaticos)
    if (!v || Number(v) <= 0) { setError('Escriba cuánto recibió de viáticos.'); return }
    setOcupado(true); setError('')
    try {
      let nueva: Rendicion
      if (paraTodos && variasPersonas) {
        nueva = await api<Rendicion>(`/api/rendiciones/${r.id}/comision`, { method: 'PUT', body: JSON.stringify({ recibido_viaticos: v }) })
        if (nueva.parametros_propios.recibido_viaticos !== undefined)
          nueva = await api<Rendicion>(`/api/rendiciones/${r.id}`, { method: 'PUT', body: JSON.stringify({ parametros: { recibido_viaticos: null } }) })
      } else {
        nueva = await api<Rendicion>(`/api/rendiciones/${r.id}`, { method: 'PUT', body: JSON.stringify({ parametros: { recibido_viaticos: v } }) })
      }
      nueva = await api<Rendicion>(`/api/rendiciones/${r.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          parametros: { recibido_pasajes: numero(pasajes) || null, recibido_otros: numero(otros) || null },
          datos: { inicio_confirmado: 'si' },
        }),
      })
      alGuardado(nueva)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar.')
    } finally {
      setOcupado(false)
    }
  }

  const dias = r.dias ?? []
  const lineaFechas = dias.length ? `${diaCorto(dias[0])} al ${diaCorto(dias[dias.length - 1])} · ${dias.length} día(s)` : 'Sin fechas: se corrigen en Datos.'
  const supuesto = rec && !['rendicion', 'comision', 'memorando'].includes(rec.origen)
  const soles = { startAdornment: <InputAdornment position="start">S/</InputAdornment> }

  return (
    <Dialog open={abierta} onClose={posponer} fullWidth maxWidth="xs">
      <DialogTitle sx={{ pb: 0.5 }}>Antes de empezar</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        <Typography variant="body2" color="text.secondary">
          Primero lo que cambia en cada Semana: cuánto recibió. Lo demás se llena después.
        </Typography>
        <Box sx={{ p: 1.25, borderRadius: 1.5, bgcolor: PALETA.superficieTenue, fontSize: 13, lineHeight: 1.6 }}>
          <Box><b>{r.semana?.codigo ?? 'Comisión'}</b> · {lineaFechas}</Box>
          <Box color="text.secondary">{r.memorando ? `${r.memorando.numero} · ${r.memorando.fecha ? diaCorto(r.memorando.fecha) : ''}` : 'Sin memorando vinculado: se elige en Datos.'}</Box>
        </Box>
        <TextField label="Recibido de viáticos" value={viaticos} onChange={(e) => setViaticos(e.target.value)} autoFocus
          inputProps={{ inputMode: 'decimal' }} InputProps={soles}
          helperText={supuesto ? 'Propuesto: viático por día × días. Confírmelo con lo que le depositaron.' : 'Lo que le depositaron o entregaron para viáticos.'} />
        {variasPersonas && (
          <FormControlLabel sx={{ mt: -1 }} control={<Checkbox size="small" checked={paraTodos} onChange={(e) => setParaTodos(e.target.checked)} />}
            label={<Typography variant="body2">Es el mismo monto para todos los de esta comisión</Typography>} />
        )}
        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
          <TextField size="small" label="Pasajes terrestres" value={pasajes} onChange={(e) => setPasajes(e.target.value)} inputProps={{ inputMode: 'decimal' }} InputProps={soles} helperText="Si recibió" />
          <TextField size="small" label="Otros recursos" value={otros} onChange={(e) => setOtros(e.target.value)} inputProps={{ inputMode: 'decimal' }} InputProps={soles} helperText="Si recibió" />
        </Box>
        {error && <Typography variant="body2" sx={{ color: PALETA.error }}>{error}</Typography>}
      </DialogContent>
      <DialogActions>
        <Button color="inherit" onClick={posponer}>Más tarde</Button>
        <Button variant="contained" onClick={() => void guardar()} disabled={ocupado}>Guardar y empezar</Button>
      </DialogActions>
    </Dialog>
  )
}
