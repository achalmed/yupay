/**
 * Paso «Revisión» (2026-10-18): el resumen (recibido, rendido, saldo, % de DJ), los controles —breves,
 * cada uno lleva a donde se corrige— y la liquidación por día con su «CONFORME / REVISAR», como el libro
 * de referencia. Aquí cambia el estado: lista → presentada; Administración observa o cierra.
 * «Pendientes» (2026-10-18): lo que falta y no es un dato del sistema —«falta el comprobante del
 * desayuno del 24», «confirmar el importe recibido»—, un renglón por pendiente; sale como aviso arriba
 * y en la lista hasta que se borra. Nada se inventa: lo que no consta se anota aquí.
 * «Comparar con la comisión» (2026-10-18): los comisionados de la misma comisión lado a lado, con las
 * diferencias resaltadas (`CompararComision.tsx`), para la última revisión y para levantar observaciones.
 */
import { useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import useMediaQuery from '@mui/material/useMediaQuery'
import { useTheme } from '@mui/material/styles'
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import { api } from '@qillqa/tiqsi'
import { PALETA } from '@qillqa/tiqsi'
import { COLOR_ESTADO, colorNivel } from './estilo'
import { Dato, Seccion, Siguiente, type PropsPaso } from './paso'
import CompararComision from './CompararComision'
import { diaCorto, pasoDeControl, soles, textoPlazo, type Estado, type Rendicion } from './modelo'
import { hoyIso } from './apoyo'

export default function PasoRevision({ r, setR, avisar, ir, soloLectura }: PropsPaso) {
  const ancha = useMediaQuery(useTheme().breakpoints.up('md'))
  const [observar, setObservar] = useState<string | null>(null)
  const [pendientes, setPendientes] = useState('')
  const liq = r.liquidacion
  const pendientesGuardados = String(r.datos_propios.pendientes ?? '')
  useEffect(() => setPendientes(pendientesGuardados), [pendientesGuardados])
  const guardarPendientes = async () => {
    if (pendientes.trim() === pendientesGuardados.trim()) return
    try {
      setR(await api<Rendicion>(`/api/rendiciones/${r.id}`, { method: 'PUT', body: JSON.stringify({ datos: { pendientes } }) }))
    } catch (e) { avisar('error', e instanceof Error ? e.message : 'No se pudo guardar.') }
  }

  const estado = async (nuevo: Estado, observacion = '') => {
    try {
      setR(await api<Rendicion>(`/api/rendiciones/${r.id}/estado`, { method: 'POST', body: JSON.stringify({ estado: nuevo, observacion }) }))
      avisar('success', nuevo === 'lista' ? 'Lista para presentar.' : nuevo === 'presentada' ? 'Marcada como presentada.' : 'Estado cambiado.')
    } catch (e) {
      avisar('error', e instanceof Error ? e.message : 'No se pudo cambiar el estado.')
    }
  }

  const plazo = textoPlazo(r.limite, hoyIso(), r.estado)
  const conforme = (ok: boolean) => <Box component="span" sx={{ color: ok ? PALETA.exito : PALETA.error, fontWeight: 600, fontSize: 12 }}>{ok ? 'OK' : 'REVISAR'}</Box>

  return (
    <>
      <Seccion>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.25, flexWrap: 'wrap' }}>
          <Chip label={r.etiqueta_estado} sx={{ bgcolor: `${COLOR_ESTADO[r.estado]}1A`, color: COLOR_ESTADO[r.estado], fontWeight: 600 }} />
          {plazo && <Typography variant="body2" sx={{ color: plazo.startsWith('Vencida') ? PALETA.error : 'text.secondary' }}>{plazo}</Typography>}
        </Box>
        <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr 1fr', sm: 'repeat(4, 1fr)' } }}>
          <Dato rotulo={r.parametros.recibido_viaticos?.origen === 'supuesto' ? 'Recibido (pendiente: supuesto)' : 'Recibido'}>{soles(liq.recibido)}</Dato>
          <Dato rotulo="Rendido">{soles(liq.reconocido)}</Dato>
          <Dato rotulo="Saldo a devolver" fuerte>{soles(liq.saldo)}</Dato>
          <Dato rotulo={`DJ (máx. ${liq.pct_dj_max.toFixed(0)} %)`}>
            <Box component="span" sx={{ color: liq.pct_dj_ok ? 'inherit' : PALETA.error }}>{liq.pct_dj.toFixed(2)} %</Box>
          </Dato>
        </Box>
        {liq.exceso > 0 && <Typography variant="caption" sx={{ display: 'block', mt: 1, color: PALETA.avisoOscuro }}>Gasto sobre el viático que asume el comisionado: {soles(liq.exceso)}.</Typography>}
        {!soloLectura && (
          <Box sx={{ display: 'flex', gap: 1, mt: 1.5, flexWrap: 'wrap' }}>
            {(r.estado === 'borrador' || r.estado === 'observada') && (
              <Button variant="contained" disabled={r.errores > 0} onClick={() => void estado('lista')}>Marcar como lista</Button>
            )}
            {(r.estado === 'lista' || (r.estado === 'observada' && r.errores === 0)) && (
              <Button variant={r.estado === 'lista' ? 'contained' : 'outlined'} onClick={() => void estado('presentada')}>Presentada</Button>
            )}
            {r.puede_administrar && r.estado === 'presentada' && <Button variant="outlined" onClick={() => setObservar('')}>Observar</Button>}
            {r.puede_administrar && r.estado === 'presentada' && <Button variant="contained" onClick={() => void estado('cerrada')}>Cerrar</Button>}
            {r.estado !== 'borrador' && (!['presentada', 'cerrada'].includes(r.estado) || r.puede_administrar) && (
              <Button color="inherit" onClick={() => void estado('borrador')}>Volver a borrador</Button>
            )}
          </Box>
        )}
        {r.errores > 0 && !soloLectura && <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.75 }}>Corrija lo marcado en rojo para marcarla como lista.</Typography>}
      </Seccion>

      <Seccion titulo="Pendientes">
        <TextField multiline minRows={2} fullWidth size="small" disabled={soloLectura} value={pendientes}
          onChange={(e) => setPendientes(e.target.value)} onBlur={() => void guardarPendientes()}
          placeholder={'Un renglón por pendiente. Ej.:\nFalta el comprobante del desayuno del 24/08\nConfirmar el importe recibido'}
          helperText="Lo que falta y no consta en ningún documento. Se guarda al salir." />
      </Seccion>

      <Seccion titulo="Controles">
        {r.controles.length === 0 && (
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', color: PALETA.exito }}>
            <CheckCircleOutlineIcon fontSize="small" /> <Typography variant="body2">Todo conforme.</Typography>
          </Box>
        )}
        {r.controles.map((c, i) => {
          const a = pasoDeControl(c)
          return (
            <Box key={i} sx={{ display: 'flex', gap: 1, alignItems: 'center', py: 0.75, borderTop: i ? '1px solid' : 'none', borderColor: 'divider' }}>
              <Box sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: colorNivel(c.nivel), flexShrink: 0 }} />
              <Typography variant="body2" sx={{ flex: 1, minWidth: 0 }}>{c.texto}</Typography>
              {a !== 'revision' && <Button size="small" onClick={() => ir(a)}>Ver</Button>}
            </Box>
          )
        })}
      </Seccion>

      <CompararComision r={r} />

      <Seccion titulo="Liquidación por día">
        {ancha ? (
          <Box component="table" sx={{ width: '100%', borderCollapse: 'collapse', fontSize: 13.5, '& td, & th': { borderBottom: '1px solid', borderColor: 'divider', px: 1, py: 0.6, textAlign: 'right' }, '& th': { color: 'text.secondary', fontWeight: 600 }, '& td:first-of-type, & th:first-of-type': { textAlign: 'left' } }}>
            <thead><tr><th>Día</th><th>Con comprobante</th><th>Decl. jurada</th><th>Asignado</th><th>Reconocido</th><th>Lo asume</th><th>Saldo</th><th>DJ ≤ tope</th><th>Día ≤ tope</th></tr></thead>
            <tbody>
              {liq.dias.map((d) => (
                <tr key={d.fecha}>
                  <td>{diaCorto(d.fecha)}</td><td>{soles(d.subtotal_a)}</td><td>{soles(d.dj)}</td><td>{soles(d.asignado)}</td><td>{soles(d.reconocido)}</td>
                  <td>{d.exceso ? soles(d.exceso) : '—'}</td><td>{soles(d.saldo)}</td><td>{conforme(d.dj_ok)}</td><td>{conforme(d.total_ok)}</td>
                </tr>
              ))}
              <tr>
                <td><b>Total</b></td><td><b>{soles(liq.con_comprobante)}</b></td><td><b>{soles(liq.dj)}</b></td><td><b>{soles(liq.asignado)}</b></td>
                <td><b>{soles(liq.reconocido)}</b></td><td><b>{liq.exceso ? soles(liq.exceso) : '—'}</b></td><td><b>{soles(liq.saldo_por_dias ?? liq.saldo)}</b></td>
                <td><b style={{ fontSize: 12 }}>{liq.conforme.dj}</b></td><td><b style={{ fontSize: 12 }}>{liq.conforme.total}</b></td>
              </tr>
            </tbody>
          </Box>
        ) : (
          <Box sx={{ display: 'grid', gap: 1 }}>
            {liq.dias.map((d) => (
              <Box key={d.fecha} sx={{ p: 1, borderRadius: 1.5, bgcolor: PALETA.superficieTenue }}>
                <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600, flex: 1 }}>{diaCorto(d.fecha)}</Typography>
                  {d.dj_ok && d.total_ok ? conforme(true) : conforme(false)}
                </Box>
                <Typography variant="caption" color="text.secondary" component="div">
                  Comprobantes {soles(d.subtotal_a)} · DJ {soles(d.dj)} · Reconocido {soles(d.reconocido)} · Saldo {soles(d.saldo)}{d.exceso ? ` · asume ${soles(d.exceso)}` : ''}
                </Typography>
              </Box>
            ))}
          </Box>
        )}
      </Seccion>
      <Siguiente ir={ir} a="documento" texto="Documento" />

      <Dialog open={observar !== null} onClose={() => setObservar(null)} fullWidth maxWidth="xs">
        <DialogTitle>Observar la rendición</DialogTitle>
        <DialogContent sx={{ pt: '8px !important' }}>
          <TextField autoFocus multiline minRows={3} fullWidth label="Qué hay que corregir" value={observar ?? ''} onChange={(e) => setObservar(e.target.value)} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setObservar(null)}>Cancelar</Button>
          <Button variant="contained" disabled={!observar?.trim()} onClick={() => { void estado('observada', observar ?? ''); setObservar(null) }}>Observar</Button>
        </DialogActions>
      </Dialog>
    </>
  )
}
