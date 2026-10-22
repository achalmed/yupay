/**
 * Revisión: COMPARAR a los comisionados de la misma comisión (2026-10-18, Edison: «una vista que compare lado a
 * lado a los comisionados: día por día, comprobantes por concepto, movilidad (la misma) y saldo; totales; y las
 * diferencias resaltadas. Sirve para la última revisión y ajuste, y para levantar observaciones de la oficina
 * que recibe»). Los datos, de `GET /api/rendiciones/{id}/comparar` (solo las rendiciones que la cuenta puede
 * ver); la comparación, pura, en `modelo.ts::compararComision`.
 *
 * En escritorio (≥ 900 px), una tabla con una columna por persona; en el celular, se alterna entre personas y
 * cada valor que difiere dice, debajo, el de la otra. «Solo lo distinto» deja solo las filas que difieren.
 */
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import Box from '@mui/material/Box'
import ButtonBase from '@mui/material/ButtonBase'
import FormControlLabel from '@mui/material/FormControlLabel'
import Switch from '@mui/material/Switch'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Typography from '@mui/material/Typography'
import LinearProgress from '@mui/material/LinearProgress'
import useMediaQuery from '@mui/material/useMediaQuery'
import { useTheme } from '@mui/material/styles'
import { api } from '@qillqa/tiqsi'
import { PALETA } from '@qillqa/tiqsi'
import { COLOR_ESTADO } from './estilo'
import { Seccion } from './paso'
import { compararComision, diaCorto, valorComparar, type FilaComparar, type PersonaComparar, type Rendicion } from './modelo'

const marca = { bgcolor: PALETA.avisoFondo, color: PALETA.avisoOscuro, fontWeight: 650 }

export default function CompararComision({ r }: { r: Rendicion }) {
  const ancha = useMediaQuery(useTheme().breakpoints.up('md'))
  const navegar = useNavigate()
  const [datos, setDatos] = useState<{ personas: PersonaComparar[]; sin_acceso: string[] } | null>(null)
  const [elegida, setElegida] = useState(0)
  const [soloDistinto, setSoloDistinto] = useState(false)
  const varios = r.comision.miembros.length > 1

  // Se vuelve a pedir cuando cambia esta rendición (cada guardado sube su versión) o la movilidad compartida.
  const huella = `${r.id}|${r.version}|${r.liquidacion.dj}|${r.comision.ultimo_cambio?.lote ?? ''}`
  useEffect(() => {
    if (!varios) return
    let vivo = true
    api<{ personas: PersonaComparar[]; sin_acceso: string[] }>(`/api/rendiciones/${r.id}/comparar`)
      .then((d) => vivo && setDatos(d))
      .catch(() => vivo && setDatos({ personas: [], sin_acceso: [] }))
    return () => { vivo = false }
  }, [huella, varios, r.id])

  const c = useMemo(() => (datos && datos.personas.length > 1 ? compararComision(datos.personas) : null), [datos])
  if (!varios) return null
  if (!datos) return <Seccion titulo="Comparar con la comisión"><LinearProgress /></Seccion>
  if (!c) {
    return datos.sin_acceso.length ? (
      <Seccion titulo="Comparar con la comisión">
        <Typography variant="body2" color="text.secondary">La rendición de {datos.sin_acceso.join(' y ')} la hace esa persona: solo ella, quien la hizo como encargado o Administración pueden compararla.</Typography>
      </Seccion>
    ) : null
  }
  const personas = datos.personas
  const ver = (f: FilaComparar) => !soloDistinto || f.difiere
  const nombres = personas.map((p) => p.comisionado)
  const resumen = c.diferencias
    ? `${c.diferencias} diferencia${c.diferencias === 1 ? '' : 's'} entre ${nombres.join(' y ')}.`
    : `Sin diferencias entre ${nombres.join(' y ')}.`

  const cabecera = (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', mb: 1 }}>
      <Typography variant="body2" sx={{ flex: 1, minWidth: 200, color: c.diferencias ? PALETA.avisoOscuro : 'text.secondary' }}>{resumen}</Typography>
      <FormControlLabel sx={{ mr: 0, '& .MuiFormControlLabel-label': { fontSize: 13, color: 'text.secondary' } }}
        control={<Switch size="small" checked={soloDistinto} onChange={(e) => setSoloDistinto(e.target.checked)} />} label="Solo lo distinto" />
    </Box>
  )

  if (ancha) {
    const celda = (f: FilaComparar, i: number) => (
      <td key={i} style={{ textAlign: 'right' }}>
        <Box component="span" sx={{ px: 0.75, py: 0.25, borderRadius: 1, ...(f.difiere ? marca : {}), fontWeight: f.fuerte ? 700 : f.difiere ? 650 : 400 }}>
          {valorComparar(f.valores[i], f.formato)}
        </Box>
        {f.cuantos && f.cuantos[i] > 1 && <Box component="span" sx={{ fontSize: 11, color: 'text.secondary', ml: 0.5 }}>({f.cuantos[i]})</Box>}
      </td>
    )
    const filas = (fs: FilaComparar[]) => fs.filter(ver).map((f) => (
      <tr key={f.clave}><td style={{ paddingLeft: 16 }}>{f.rotulo}</td>{personas.map((_, i) => celda(f, i))}</tr>
    ))
    return (
      <Seccion titulo="Comparar con la comisión">
        {cabecera}
        <Box component="table" sx={{ width: '100%', borderCollapse: 'collapse', fontSize: 13.5, tableLayout: 'fixed',
          '& td, & th': { borderBottom: '1px solid', borderColor: 'divider', px: 1, py: 0.5 }, '& th': { color: 'text.secondary', fontWeight: 600, textAlign: 'right' } }}>
          <colgroup><col style={{ width: '34%' }} />{personas.map((p) => <col key={p.id} />)}</colgroup>
          <thead>
            <tr>
              <th style={{ textAlign: 'left' }}>Concepto</th>
              {personas.map((p) => (
                <th key={p.id}>
                  <ButtonBase onClick={() => !p.propia && navegar(`/rendiciones/${p.id}?ver=revision`)} disabled={p.propia}
                    sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75, borderRadius: 1, px: 0.5, maxWidth: '100%' }}>
                    <Box component="span" sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: COLOR_ESTADO[p.estado], flexShrink: 0 }} />
                    <Box component="span" sx={{ color: 'text.primary', fontWeight: 650, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.comisionado}</Box>
                    <Box component="span" sx={{ fontWeight: 400 }}>{p.codigo}{p.propia ? ' · esta' : ''}</Box>
                  </ButtonBase>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {c.dias.map((d) => {
              const visibles = d.filas.filter(ver)
              if (!visibles.length) return null
              return [
                <tr key={`t-${d.fecha}`}>
                  <td colSpan={personas.length + 1} style={{ background: PALETA.superficieTenue }}>
                    <b>{diaCorto(d.fecha)}</b>
                    {d.diferencias > 0 && <Box component="span" sx={{ ml: 1, fontSize: 12, color: PALETA.avisoOscuro }}>{d.diferencias} distinto{d.diferencias === 1 ? '' : 's'}</Box>}
                  </td>
                </tr>,
                ...filas(d.filas),
              ]
            })}
            {c.totales.some(ver) && (
              <tr><td colSpan={personas.length + 1} style={{ background: PALETA.superficieTenue }}><b>Totales</b></td></tr>
            )}
            {filas(c.totales)}
          </tbody>
        </Box>
        <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.75 }}>
          Resaltado: lo que no coincide. Entre paréntesis, cuántos comprobantes hay de ese concepto ese día. La movilidad es la misma para todos.
        </Typography>
      </Seccion>
    )
  }

  // Celular: se alterna entre personas; cada valor distinto dice debajo el de los demás.
  const i = Math.min(elegida, personas.length - 1)
  const otrosDe = (f: FilaComparar) => personas.map((p, j) => (j === i ? '' : `${p.comisionado}: ${valorComparar(f.valores[j], f.formato)}`)).filter(Boolean).join(' · ')
  const lista = (fs: FilaComparar[]) => fs.filter(ver).map((f) => (
    <Box key={f.clave} sx={{ display: 'flex', alignItems: 'baseline', gap: 1, py: 0.4, borderTop: '1px solid', borderColor: 'divider' }}>
      <Typography variant="body2" sx={{ flex: 1, minWidth: 0 }}>{f.rotulo}{f.cuantos && f.cuantos[i] > 1 ? ` (${f.cuantos[i]})` : ''}</Typography>
      <Box sx={{ textAlign: 'right' }}>
        <Typography variant="body2" sx={{ fontWeight: f.fuerte ? 700 : 500, ...(f.difiere ? { color: PALETA.avisoOscuro, fontWeight: 650 } : {}) }}>{valorComparar(f.valores[i], f.formato)}</Typography>
        {f.difiere && <Typography variant="caption" sx={{ color: PALETA.avisoOscuro, display: 'block', lineHeight: 1.2 }}>{otrosDe(f)}</Typography>}
      </Box>
    </Box>
  ))
  return (
    <Seccion titulo="Comparar con la comisión">
      <ToggleButtonGroup size="small" exclusive fullWidth value={i} onChange={(_, v) => v !== null && setElegida(v)} sx={{ mb: 1 }}>
        {personas.map((p, j) => (
          <ToggleButton key={p.id} value={j} sx={{ textTransform: 'none', gap: 0.75, minWidth: 0 }}>
            <Box component="span" sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: COLOR_ESTADO[p.estado], flexShrink: 0 }} />
            <Box component="span" sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.comisionado}</Box>
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
      {cabecera}
      {c.dias.map((d) => {
        if (!d.filas.some(ver)) return null
        return (
          <Box key={d.fecha} sx={{ mb: 1, p: 1, borderRadius: 1.5, bgcolor: PALETA.superficieTenue }}>
            <Typography variant="body2" sx={{ fontWeight: 650 }}>
              {diaCorto(d.fecha)}
              {d.diferencias > 0 && <Box component="span" sx={{ ml: 1, fontWeight: 400, fontSize: 12, color: PALETA.avisoOscuro }}>{d.diferencias} distinto{d.diferencias === 1 ? '' : 's'}</Box>}
            </Typography>
            {lista(d.filas)}
          </Box>
        )
      })}
      {c.totales.some(ver) && (
        <Box sx={{ p: 1, borderRadius: 1.5, border: '1px solid', borderColor: 'divider' }}>
          <Typography variant="body2" sx={{ fontWeight: 650 }}>Totales</Typography>
          {lista(c.totales)}
        </Box>
      )}
    </Seccion>
  )
}
