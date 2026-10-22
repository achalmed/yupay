/**
 * Alta de una rendición (2026-10-18). Con la semana de representación basta: fechas, lugar, motivo y
 * tramos de movilidad salen solos de ella. Sin semana (otra comisión de servicio), se piden las fechas.
 * Cualquiera del equipo puede crearla a nombre de un compañero (modo ENCARGADO, 2026-10-18: «un encargado
 * hace las rendiciones de los dos, o cada uno hace la suya»); quien la crea la ve y la edita. En el celular el diálogo es hoja inferior
 * (tema). Sin semana elegida, propone la que terminó más recientemente (2026-10-18: proponía la de
 * id mayor, que podía ser una semana futura).
 */
import { useEffect, useState } from 'react'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import MenuItem from '@mui/material/MenuItem'
import Typography from '@mui/material/Typography'
import Box from '@mui/material/Box'
import { api, ErrorApi } from '@qillqa/tiqsi'
import type { MiembroEquipo } from './apoyo'
import { hoyIso } from './apoyo'
import { semanaPorDefecto } from './modelo'

interface SemanaLista { id: number; codigo: string; tema: string; inicio: string; fin: string }

export default function NuevaRendicion({ abierto, semanaInicial, usuarioInicial, alCerrar, alCrear, alExiste, alError }: {
  abierto: boolean
  semanaInicial?: number
  usuarioInicial?: number
  /** Sin uso desde el 2026-10-18 (todos pueden ser encargados); se conserva para no romper a quien lo pasa. */
  admin?: boolean
  alCerrar: () => void
  alCrear: (id: number) => void
  alExiste: (id: number) => void
  alError: (e: unknown) => void
}) {
  const [semanas, setSemanas] = useState<SemanaLista[]>([])
  const [equipo, setEquipo] = useState<MiembroEquipo[]>([])
  const [semana, setSemana] = useState<number | ''>('')
  const [usuario, setUsuario] = useState<number | ''>('')
  const [inicio, setInicio] = useState('')
  const [fin, setFin] = useState('')
  const [lugar, setLugar] = useState('')
  const [motivo, setMotivo] = useState('')
  const [ocupado, setOcupado] = useState(false)

  useEffect(() => {
    if (!abierto) return
    setSemana(semanaInicial ?? '')
    setUsuario(usuarioInicial ?? '')
    api<{ semanas: SemanaLista[] }>('/api/semanas').then((r) => {
      setSemanas(r.semanas)
      // Sin semana elegida, la que terminó más recientemente (la que toca rendir).
      if (!semanaInicial && r.semanas.length) setSemana(semanaPorDefecto(r.semanas, hoyIso()))
    }).catch(() => setSemanas([]))
    api<MiembroEquipo[]>('/api/rendiciones/equipo').then((l) => setEquipo(l.filter((m) => m.rol !== 'invitado'))).catch(() => setEquipo([]))
  }, [abierto, semanaInicial, usuarioInicial])

  const crear = async () => {
    setOcupado(true)
    try {
      const datos = semana ? {} : { fecha_inicio: inicio, fecha_fin: fin, lugar, motivo }
      const r = await api<{ id: number }>('/api/rendiciones', {
        method: 'POST',
        body: JSON.stringify({ semana_id: semana || null, usuario_id: usuario || null, datos }),
      })
      alCrear(r.id)
    } catch (e) {
      const d = e instanceof ErrorApi ? (e.detalle as { codigo?: string; id?: number } | undefined) : undefined
      if (d?.codigo === 'ya_existe' && d.id) alExiste(d.id)
      else alError(e)
    } finally {
      setOcupado(false)
    }
  }

  const listo = semana ? true : Boolean(inicio && fin && fin >= inicio)
  return (
    <Dialog open={abierto} onClose={alCerrar} fullWidth maxWidth="xs">
      <DialogTitle>Nueva rendición</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '8px !important' }}>
        <TextField select label="Semana de representación" value={semana} onChange={(e) => setSemana(e.target.value === '' ? '' : Number(e.target.value))} fullWidth>
          {semanas.map((s) => <MenuItem key={s.id} value={s.id}>{s.codigo} · {s.tema}</MenuItem>)}
          <MenuItem value="">Otra comisión de servicio</MenuItem>
        </TextField>
        {semana ? (
          <Typography variant="body2" color="text.secondary">Las fechas, el lugar y la movilidad salen de la semana.</Typography>
        ) : (
          <>
            <Box sx={{ display: 'flex', gap: 1.5 }}>
              <TextField type="date" label="Desde" value={inicio} onChange={(e) => setInicio(e.target.value)} InputLabelProps={{ shrink: true }} fullWidth />
              <TextField type="date" label="Hasta" value={fin} onChange={(e) => setFin(e.target.value)} InputLabelProps={{ shrink: true }} fullWidth />
            </Box>
            <TextField label="Lugar" value={lugar} onChange={(e) => setLugar(e.target.value)} fullWidth />
            <TextField label="Motivo del viaje" value={motivo} onChange={(e) => setMotivo(e.target.value)} fullWidth />
          </>
        )}
        <TextField select label="Comisionado" value={usuario} onChange={(e) => setUsuario(e.target.value === '' ? '' : Number(e.target.value))} fullWidth
          helperText={usuario ? 'Usted la hace como encargado; la movilidad es la misma de la comisión.' : 'A nombre de quién va.'}>
          <MenuItem value="">Yo</MenuItem>
          {equipo.map((m) => <MenuItem key={m.id} value={m.id}>{m.nombre_completo}</MenuItem>)}
        </TextField>
      </DialogContent>
      <DialogActions>
        <Button onClick={alCerrar}>Cancelar</Button>
        <Button variant="contained" disabled={!listo || ocupado} onClick={() => void crear()}>Crear</Button>
      </DialogActions>
    </Dialog>
  )
}
