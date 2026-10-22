/**
 * El resumen del despacho (2026-10-18): por semana, cada comisionado con lo recibido, lo rendido y el
 * saldo, y los totales. Lo ve el administrador (los demás, solo su fila: lo decide el servidor). En el
 * celular, una tarjeta por persona; desde 900 px, una tabla. Arriba, quién del equipo de la semana aún no
 * tiene rendición (2026-10-18: «pendiente: falta la rendición de X»), con «Crear» para el administrador.
 */
import { useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import ButtonBase from '@mui/material/ButtonBase'
import Chip from '@mui/material/Chip'
import Button from '@mui/material/Button'
import MenuItem from '@mui/material/MenuItem'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import LinearProgress from '@mui/material/LinearProgress'
import useMediaQuery from '@mui/material/useMediaQuery'
import { useTheme } from '@mui/material/styles'
import { api } from '@qillqa/tiqsi'
import { PALETA } from '@qillqa/tiqsi'
import { COLOR_ESTADO } from './estilo'
import { semanaPorDefecto, soles, type Estado } from './modelo'
import { hoyIso } from './apoyo'

interface Fila { id: number; codigo: string; comisionado: string; estado: Estado; etiqueta_estado: string; semana: string | null
  recibido: number; con_comprobante: number; dj: number; reconocido: number; exceso: number; saldo: number; pct_dj: number; errores: number }
type Totales = Record<'recibido' | 'con_comprobante' | 'dj' | 'reconocido' | 'exceso' | 'saldo', number>

interface Falta { nombre: string; rol: string; usuario_id: number | null }

export default function ResumenDespacho({ alAbrir, alCrear }: { alAbrir: (id: number) => void; alCrear?: (semana: number, usuario?: number) => void }) {
  const ancha = useMediaQuery(useTheme().breakpoints.up('md'))
  const [semanas, setSemanas] = useState<{ id: number; codigo: string; tema: string; inicio: string; fin: string }[]>([])
  const [semana, setSemana] = useState<number | ''>('')
  const [datos, setDatos] = useState<{ filas: Fila[]; totales: Totales; faltan?: Falta[] } | null>(null)

  useEffect(() => {
    api<{ semanas: { id: number; codigo: string; tema: string; inicio: string; fin: string }[] }>('/api/semanas').then((r) => {
      setSemanas(r.semanas)
      if (r.semanas.length) setSemana(semanaPorDefecto(r.semanas, hoyIso()))
      setListas(true)
    }).catch(() => { setSemanas([]); setListas(true) })
  }, [])
  const [listas, setListas] = useState(false)   // hasta saber qué semana proponer, no se pide nada
  useEffect(() => {
    if (!listas) return
    // Se descarta la respuesta de una semana anterior (2026-10-18: la de «todas» llegaba después y
    // pisaba la de la semana elegida).
    let vigente = true
    setDatos(null)
    api<{ filas: Fila[]; totales: Totales; faltan?: Falta[] }>(`/api/rendiciones/resumen${semana ? `?semana_id=${semana}` : ''}`)
      .then((d) => { if (vigente) setDatos(d) })
      .catch(() => { if (vigente) setDatos({ filas: [], totales: { recibido: 0, con_comprobante: 0, dj: 0, reconocido: 0, exceso: 0, saldo: 0 } }) })
    return () => { vigente = false }
  }, [semana, listas])

  // «No rinde»: estuvo en la semana sin viáticos (solo dos servidores los reciben por congresista).
  const noRinde = async (nombre: string) => {
    try {
      await api(`/api/rendiciones/semana/${semana}/no-rinde`, { method: 'POST', body: JSON.stringify({ nombre }) })
      setDatos((d) => d && { ...d, faltan: (d.faltan ?? []).filter((x) => x.nombre !== nombre) })
    } catch { /* sin permiso: no cambia nada */ }
  }
  const columnas: [keyof Totales, string][] = [['recibido', 'Recibido'], ['con_comprobante', 'Con comprobante'], ['dj', 'Decl. jurada'], ['reconocido', 'Reconocido'], ['exceso', 'Lo asume'], ['saldo', 'Saldo']]
  return (
    <Box>
      <TextField select size="small" label="Semana" value={semana} onChange={(e) => setSemana(e.target.value === '' ? '' : Number(e.target.value))} sx={{ mb: 1.5, minWidth: 240 }}>
        {semanas.map((s) => <MenuItem key={s.id} value={s.id}>{s.codigo} · {s.tema}</MenuItem>)}
        <MenuItem value="">Todas</MenuItem>
      </TextField>
      {!datos && <LinearProgress />}
      {datos?.faltan && datos.faltan.length > 0 && (
        <Box sx={{ mb: 1.5, p: 1.25, borderRadius: 2, border: '1px solid', borderColor: PALETA.avisoOscuro, bgcolor: 'background.paper' }}>
          {datos.faltan.map((f) => (
            <Box key={f.nombre} sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.25 }}>
              <Typography variant="body2" sx={{ flex: 1, minWidth: 0 }}>
                Pendiente: falta la rendición de <b>{f.nombre}</b>{f.usuario_id ? '' : ' (sin cuenta en el sistema)'}
              </Typography>
              {alCrear && semana !== '' && f.usuario_id && <Button size="small" onClick={() => alCrear(Number(semana), f.usuario_id ?? undefined)}>Crear</Button>}
              {semana !== '' && <Button size="small" color="inherit" onClick={() => void noRinde(f.nombre)}>No rinde</Button>}
            </Box>
          ))}
        </Box>
      )}
      {datos && datos.filas.length === 0 && <Typography variant="body2" color="text.secondary">Nadie ha registrado su rendición de esta semana.</Typography>}
      {datos && datos.filas.length > 0 && (ancha ? (
        <Box component="table" sx={{ width: '100%', borderCollapse: 'collapse', bgcolor: 'background.paper', fontSize: 13.5, '& td, & th': { borderBottom: '1px solid', borderColor: 'divider', px: 1, py: 0.75, textAlign: 'right' }, '& th': { fontWeight: 600, color: 'text.secondary', bgcolor: PALETA.superficieTenue }, '& td:first-of-type, & th:first-of-type': { textAlign: 'left' } }}>
          <thead><tr><th>Comisionado</th><th>Estado</th>{columnas.map(([k, t]) => <th key={k}>{t}</th>)}</tr></thead>
          <tbody>
            {datos.filas.map((f) => (
              <Box component="tr" key={f.id} onClick={() => alAbrir(f.id)} sx={{ cursor: 'pointer', '&:hover': { bgcolor: PALETA.guindaSuave } }}>
                <td>{f.comisionado}{f.errores > 0 && <Typography component="span" variant="caption" sx={{ color: PALETA.error, ml: 1 }}>{f.errores} por corregir</Typography>}</td>
                <td><Chip size="small" label={f.etiqueta_estado} sx={{ height: 20, bgcolor: `${COLOR_ESTADO[f.estado]}1A`, color: COLOR_ESTADO[f.estado], fontWeight: 600 }} /></td>
                {columnas.map(([k]) => <td key={k}>{soles(f[k])}</td>)}
              </Box>
            ))}
            <tr><td><b>Total del despacho</b></td><td />{columnas.map(([k]) => <td key={k}><b>{soles(datos.totales[k])}</b></td>)}</tr>
          </tbody>
        </Box>
      ) : (
        <Box sx={{ display: 'grid', gap: 1 }}>
          {datos.filas.map((f) => (
            <ButtonBase key={f.id} onClick={() => alAbrir(f.id)} sx={{ display: 'block', textAlign: 'left', p: 1.25, borderRadius: 2, border: '1px solid', borderColor: 'divider', bgcolor: 'background.paper' }}>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                <Typography variant="body2" sx={{ fontWeight: 600, flex: 1 }} noWrap>{f.comisionado}</Typography>
                <Chip size="small" label={f.etiqueta_estado} sx={{ height: 20, bgcolor: `${COLOR_ESTADO[f.estado]}1A`, color: COLOR_ESTADO[f.estado], fontWeight: 600 }} />
              </Box>
              <Typography variant="caption" color="text.secondary">Recibido {soles(f.recibido)} · Rendido {soles(f.reconocido)} · Saldo {soles(f.saldo)}</Typography>
            </ButtonBase>
          ))}
          <Box sx={{ p: 1.25, borderRadius: 2, bgcolor: PALETA.superficieTenue }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>Total del despacho</Typography>
            <Typography variant="caption" color="text.secondary">Recibido {soles(datos.totales.recibido)} · Rendido {soles(datos.totales.reconocido)} · Saldo {soles(datos.totales.saldo)}</Typography>
          </Box>
        </Box>
      ))}
    </Box>
  )
}
