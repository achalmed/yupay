/**
 * Paso «Datos» (2026-10-18): lo vinculado y la cabecera del Formato 03-VN. El comisionado (nombre, cargo,
 * DNI), la semana y el memorando se muestran VIGENTES (§27): se cambian en su sitio (Mi perfil, la
 * semana, el documento). Fechas, lugar y motivo salen de la semana mientras nadie los cambie aquí. Cada
 * campo se guarda al salir de él.
 *
 * «Importe y topes» (2026-10-18, Edison: «parámetros más fáciles de entender»): arriba, el IMPORTE
 * RECIBIDO con de dónde sale (esta rendición, toda la comisión, el memorando o «no consta», que queda
 * pendiente); debajo, lo que rige en una línea cada cosa, con su norma y un ejemplo; lo raro (pasajes,
 * otros recursos, cambiar un tope para esta rendición), en «Ver más».
 *
 * «Vínculos» (2026-10-18, Edison: «al modo Obsidian, como en otros módulos»): debajo de la semana y el
 * memorando, el mapa local de la rendición (el del anfitrión, por el contrato de Tiqsi: en Qillqa, el mismo del
 * editor, los recibidos y los proyectos; `GET /api/grafo?foco=rend:N`). Sola, sin mapa, no se muestra.
 */
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import Autocomplete from '@mui/material/Autocomplete'
import Chip from '@mui/material/Chip'
import Collapse from '@mui/material/Collapse'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import OpenInNewIcon from '@mui/icons-material/OpenInNew'
import LinkIcon from '@mui/icons-material/Link'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import { api } from '@qillqa/tiqsi'
import { PALETA } from '@qillqa/tiqsi'
import { Dato, Seccion, Siguiente, type PropsPaso } from './paso'
import CampoImporte from './CampoImporte'
import DialogoCopiar from './DialogoCopiar'
import { MapaLocal, avisarRelaciones, hay } from '@qillqa/tiqsi'
import { ejemploMovilidad, fechaCorta, lineasParametros, soles, textoRecibido, type Memorando, type Rendicion } from './modelo'

const CAMPOS_CABECERA: [string, string, 'date' | 'text'][] = [
  ['fecha_inicio', 'Desde', 'date'], ['fecha_fin', 'Hasta', 'date'], ['lugar', 'Lugar', 'text'], ['motivo', 'Motivo del viaje', 'text'],
]
const CAMPOS_PAGO: [string, string, 'date' | 'text'][] = [
  ['siaf', 'SIAF', 'text'], ['comprobante_pago', 'Comprobante de pago N.°', 'text'], ['comprobante_pago_fecha', 'Fecha del comprobante de pago', 'date'],
  ['solicitud_efectivo', 'Solicitud de dinero en efectivo N.°', 'text'], ['solicitud_efectivo_fecha', 'Fecha de la solicitud', 'date'],
]
const CAMPOS_FIRMA: [string, string, 'date' | 'text'][] = [
  ['fecha_rendicion', 'Fecha de rendición', 'date'], ['lugar_firma', 'Lugar de la firma', 'text'], ['unidad_organica', 'Unidad orgánica', 'text'],
]
/** Lo raro, en «Ver más»: lo que casi nunca cambia y solo se ajusta para ESTA rendición. */
const PARAMETROS: [string, string][] = [
  ['recibido_pasajes', 'Recibido para pasajes terrestres (S/)'], ['recibido_otros', 'Recibido para otros recursos (S/)'],
  ['tope_diario', 'Viático por día (S/)'], ['pct_dj', 'Declaración jurada (%)'], ['plazo_dias_habiles', 'Plazo (días hábiles)'],
]

export default function PasoDatos({ r, setR, avisar, ir, soloLectura }: PropsPaso) {
  const navegar = useNavigate()
  const [valores, setValores] = useState<Record<string, string>>({})
  const [param, setParam] = useState<Record<string, string>>({})
  const [busqueda, setBusqueda] = useState<Memorando[]>([])
  const [recibido, setRecibido] = useState('')
  const [para, setPara] = useState<'rendicion' | 'comision'>('rendicion')
  const [verMas, setVerMas] = useState(false)
  const [copiar, setCopiar] = useState(false)
  const otros = r.comision.miembros.filter((m) => m.id !== r.id)
  // Lo que cambia los vínculos (el memorando, los comprobantes, los sustentos, el PDF) refresca el mapa local
  // sin parpadear: los puntos que ya estaban conservan su lugar (como el editor al guardar).
  const huellaVinculos = `${r.memorando?.id ?? 0}|${r.semana?.id ?? 0}|${r.comprobantes.length}|${r.anexos.length}|${r.documento.generado_en ?? ''}`
  const primera = useRef(true)
  useEffect(() => {
    if (primera.current) { primera.current = false; return }
    avisarRelaciones(`rend:${r.id}`)
  }, [huellaVinculos, r.id])

  // Lo propio de la rendición (lo vigente que vino de la semana se muestra como sugerencia).
  useEffect(() => {
    const propios = r.datos_propios as Record<string, string>
    setValores(Object.fromEntries([...CAMPOS_CABECERA, ...CAMPOS_PAGO, ...CAMPOS_FIRMA].map(([k]) => [k, typeof propios[k] === 'string' ? propios[k] : ''])))
    setParam(Object.fromEntries(PARAMETROS.map(([k]) => [k, r.parametros_propios[k] !== undefined ? String(r.parametros_propios[k]) : ''])))
    const rec = r.parametros.recibido_viaticos
    setRecibido(rec && ['rendicion', 'comision'].includes(rec.origen) ? String(rec.valor ?? '') : '')
    setPara(rec?.origen === 'comision' ? 'comision' : 'rendicion')
  }, [r])

  // El importe recibido: para esta rendición (manda) o para toda la comisión (lo mismo para todos).
  const guardarRecibido = async () => {
    const v = recibido.trim()
    try {
      if (para === 'comision') {
        let nueva = await api<Rendicion>(`/api/rendiciones/${r.id}/comision`, { method: 'PUT', body: JSON.stringify(v ? { recibido_viaticos: v } : { quitar_recibido: true }) })
        if (nueva.parametros_propios.recibido_viaticos !== undefined)
          nueva = await api<Rendicion>(`/api/rendiciones/${r.id}`, { method: 'PUT', body: JSON.stringify({ parametros: { recibido_viaticos: null } }) })
        setR(nueva)
      } else {
        await guardar({ parametros: { recibido_viaticos: v || null } })
      }
      avisar('success', v ? 'Importe recibido guardado.' : 'Importe recibido quitado.')
    } catch (e) { avisar('error', e instanceof Error ? e.message : 'No se pudo guardar.') }
  }

  // Se guarda campo por campo (el servidor FUSIONA solo las claves que llegan): dos campos guardados
  // seguidos no chocan, así que aquí no viaja `version_base`.
  const guardar = async (cuerpo: Record<string, unknown>) => {
    try {
      setR(await api<Rendicion>(`/api/rendiciones/${r.id}`, { method: 'PUT', body: JSON.stringify(cuerpo) }))
    } catch (e) {
      avisar('error', e instanceof Error ? e.message : 'No se pudo guardar.')
    }
  }
  const alSalir = (k: string) => {
    const antes = (r.datos_propios as Record<string, string>)[k] ?? ''
    if ((valores[k] ?? '') !== antes) void guardar({ datos: { [k]: valores[k] ?? '' } })
  }
  const alSalirParam = (k: string) => {
    const antes = r.parametros_propios[k] !== undefined ? String(r.parametros_propios[k]) : ''
    if ((param[k] ?? '') !== antes) void guardar({ parametros: { [k]: param[k] || null } })
  }

  const campo = ([k, rotulo, tipo]: [string, string, 'date' | 'text']) => {
    const vigente = String(r.datos[k] ?? '')
    const origen = r.origen_datos[k]
    const ayuda = !valores[k] && origen === 'semana' ? 'De la semana' : !valores[k] && origen === 'fin' ? 'El último día' : k === 'unidad_organica' && !valores[k] ? 'Vacío: la del perfil del despacho' : ' '
    return (
      <TextField
        key={k} label={rotulo} type={tipo} size="small" fullWidth disabled={soloLectura}
        value={valores[k] || (tipo === 'date' ? vigente : '')}
        placeholder={tipo === 'text' ? vigente : undefined}
        InputLabelProps={tipo === 'date' || vigente ? { shrink: true } : undefined}
        onChange={(e) => setValores({ ...valores, [k]: e.target.value })}
        onBlur={() => alSalir(k)}
        helperText={ayuda}
      />
    )
  }

  const buscar = async (q: string) => {
    try { setBusqueda(await api<Memorando[]>(`/api/rendiciones/buscar/memorandos?q=${encodeURIComponent(q)}`)) } catch { setBusqueda([]) }
  }
  const c = r.comisionado
  const rejilla = { display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }

  return (
    <>
      <Seccion titulo="Comisionado" acciones={<Button size="small" onClick={() => navegar('/perfil')}>Mi perfil</Button>}>
        <Box sx={{ display: 'grid', gap: 1.25, gridTemplateColumns: { xs: '1fr 1fr', sm: '2fr 1fr 1fr' } }}>
          <Dato rotulo="Nombre">{c.nombre}</Dato>
          <Dato rotulo="Cargo">{c.cargo || <Box component="span" sx={{ color: PALETA.error }}>Falta</Box>}</Dato>
          <Dato rotulo="DNI">{c.dni || <Box component="span" sx={{ color: PALETA.error }}>Falta</Box>}</Dato>
        </Box>
      </Seccion>

      <Seccion titulo="Vínculos">
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
            <Typography variant="body2" sx={{ minWidth: 90, color: 'text.secondary' }}>Semana</Typography>
            {r.semana ? (
              <>
                <Chip label={`${r.semana.codigo} · ${r.semana.tema}`} sx={{ maxWidth: '100%' }} />
                <Button size="small" endIcon={<OpenInNewIcon fontSize="small" />} onClick={() => navegar(`/informes/${r.semana!.id}`)}>Abrir</Button>
              </>
            ) : <Typography variant="body2">Sin semana (otra comisión de servicio)</Typography>}
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
            <Typography variant="body2" sx={{ minWidth: 90, color: 'text.secondary' }}>Memorando</Typography>
            {r.memorando ? (
              <>
                <Chip label={`${r.memorando.numero}${r.memorando.fecha ? ` · ${fechaCorta(r.memorando.fecha)}` : ''}`} sx={{ maxWidth: '100%' }} />
                <Button size="small" endIcon={<OpenInNewIcon fontSize="small" />} onClick={() => navegar(`/documentos/${r.memorando!.id}`)}>Abrir</Button>
                {!soloLectura && <Button size="small" color="inherit" onClick={() => void guardar({ quitar_memorando: true })}>Quitar</Button>}
              </>
            ) : (
              <Typography variant="body2" sx={{ color: PALETA.avisoOscuro }}>Sin vincular</Typography>
            )}
          </Box>
          {!r.memorando && !soloLectura && (
            <>
              {r.memorandos_sugeridos.map((m) => (
                <Box key={m.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, pl: { sm: '98px' } }}>
                  <Typography variant="body2" sx={{ flex: 1, minWidth: 0 }} noWrap>{m.numero} — {m.asunto}</Typography>
                  <Button size="small" variant="outlined" startIcon={<LinkIcon fontSize="small" />} onClick={() => void guardar({ documento_id: m.id })}>Vincular</Button>
                </Box>
              ))}
              <Autocomplete
                size="small" options={busqueda} filterOptions={(x) => x}
                getOptionLabel={(m) => `${m.numero} — ${m.asunto}`}
                onInputChange={(_, q) => void buscar(q)}
                onOpen={() => void buscar('')}
                onChange={(_, m) => m && void guardar({ documento_id: m.id })}
                renderInput={(p) => <TextField {...p} label="Buscar el memorando de viáticos" />}
                sx={{ pl: { sm: '98px' } }}
              />
            </>
          )}
        </Box>
      </Seccion>

      {/* Los vínculos al modo Obsidian (2026-10-18), como el editor, los recibidos y los proyectos: la semana,
          el memorando, el comisionado, la otra rendición de la comisión, los comprobantes, otros sustentos
          y el PDF; un toque abre cada uno y «Ampliar» lleva al mapa completo. */}
      {hay('MapaLocal') && (
        <Box sx={{ mb: 1.5 }}>
          <MapaLocal foco={`rend:${r.id}`} alto={220} titulo="Relaciones de esta rendición" />
        </Box>
      )}

      <Seccion titulo="Comisión de servicio">
        <Box sx={rejilla}>{CAMPOS_CABECERA.map(campo)}</Box>
      </Seccion>
      <Seccion titulo="Pago y SIAF">
        <Box sx={rejilla}>{CAMPOS_PAGO.map(campo)}</Box>
      </Seccion>
      <Seccion titulo="Firma">
        <Box sx={rejilla}>{CAMPOS_FIRMA.map(campo)}</Box>
      </Seccion>

      <Seccion titulo="Importe y topes">
        {(() => {
          const rec = r.parametros.recibido_viaticos
          const supuesto = rec?.origen === 'supuesto'
          return (
            <Box sx={{ p: 1.25, mb: 1.5, borderRadius: 1.5, border: '1px solid', borderColor: supuesto ? PALETA.avisoOscuro : 'divider', bgcolor: PALETA.superficieTenue }}>
              <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, flexWrap: 'wrap' }}>
                <Typography variant="body2" sx={{ fontWeight: 650, flex: 1, minWidth: 160 }}>Importe recibido de viáticos</Typography>
                <Typography sx={{ fontWeight: 700, fontSize: 17, color: supuesto ? 'text.secondary' : 'text.primary' }}>{supuesto ? 'Pendiente' : soles(rec?.valor ?? 0)}</Typography>
              </Box>
              <Typography variant="caption" component="div" sx={{ color: supuesto ? PALETA.avisoOscuro : 'text.secondary', mb: soloLectura ? 0 : 1 }}>
                {textoRecibido(rec)}{supuesto && rec?.valor ? ` (${soles(rec.valor)})` : ''}
              </Typography>
              {!soloLectura && (
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                  <CampoImporte size="small" label="Recibido" value={recibido} alCambiar={setRecibido} sx={{ width: { xs: '100%', sm: 200 } }}
                    onKeyDown={(e) => { if (e.key === 'Enter') void guardarRecibido() }} />
                  {otros.length > 0 && (
                    <ToggleButtonGroup size="small" exclusive value={para} onChange={(_, v) => v && setPara(v)}>
                      <ToggleButton value="rendicion">Solo {r.comisionado.corto || 'esta rendición'}</ToggleButton>
                      <ToggleButton value="comision">Toda la comisión</ToggleButton>
                    </ToggleButtonGroup>
                  )}
                  <Button size="small" variant="outlined" onClick={() => void guardarRecibido()}>Guardar</Button>
                </Box>
              )}
            </Box>
          )
        })()}
        <Box component="dl" sx={{ m: 0, display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'auto 1fr' }, columnGap: 2, rowGap: { xs: 0.25, sm: 0.75 } }}>
          {lineasParametros(r.parametros, r.dias.length, r.limite).map((l) => (
            <Box key={l.rotulo} sx={{ display: 'contents' }}>
              <Typography component="dt" variant="body2" color="text.secondary" sx={{ mt: { xs: 0.75, sm: 0 } }}>{l.rotulo}</Typography>
              <Typography component="dd" variant="body2" sx={{ m: 0 }}>
                <b>{l.valor}</b>{l.nota && <Box component="span" sx={{ color: 'text.secondary' }}> · {l.nota}</Box>}
              </Typography>
            </Box>
          ))}
        </Box>
        <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 1 }}>
          {ejemploMovilidad(Number(r.parametros.tope_diario?.valor ?? 0), Number(r.parametros.tope_dj?.valor ?? 0))}
        </Typography>
        <Button size="small" endIcon={<ExpandMoreIcon sx={{ transform: verMas ? 'rotate(180deg)' : 'none', transition: '.2s' }} />} onClick={() => setVerMas(!verMas)} sx={{ mt: 0.5, px: 0.5 }}>
          {verMas ? 'Ver menos' : 'Ver más'}
        </Button>
        <Collapse in={verMas} unmountOnExit>
          <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 1 }}>
            Solo si esta rendición es distinta: vacío = rige lo de arriba.
          </Typography>
          <Box sx={{ ...rejilla, gridTemplateColumns: { xs: '1fr 1fr', sm: '1fr 1fr 1fr' } }}>
            {PARAMETROS.map(([k, rotulo]) => {
              const p = r.parametros[k]
              return (
                <TextField
                  key={k} label={rotulo} size="small" disabled={soloLectura} value={param[k] ?? ''}
                  placeholder={p?.valor !== null && p?.valor !== undefined ? String(p.valor) : ''}
                  InputLabelProps={{ shrink: true }} inputProps={{ inputMode: 'decimal' }}
                  onChange={(e) => setParam({ ...param, [k]: e.target.value })} onBlur={() => alSalirParam(k)}
                  helperText={param[k] ? 'De esta rendición' : p?.simple ?? ' '}
                />
              )
            })}
          </Box>
          <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 1, lineHeight: 1.5 }}>
            <b>De dónde sale.</b> {r.parametros.tope_diario?.fuente}. {r.parametros.pct_dj?.fuente}. {r.parametros.plazo_dias_habiles?.fuente}.
            {r.institucion && <> Los comprobantes van a nombre de: {r.institucion.a_nombre_de}{r.institucion.ruc_a_nombre ? ` (RUC ${r.institucion.ruc_a_nombre})` : ''}.</>}
          </Typography>
        </Collapse>
      </Seccion>
      {otros.length > 0 && !soloLectura && (
        <Box sx={{ display: 'flex', justifyContent: 'flex-start', mb: 1 }}>
          <Button size="small" onClick={() => setCopiar(true)}>Copiar de {otros[0].comisionado}{otros.length > 1 ? ' u otro' : ''}: lugar de la firma, memorando…</Button>
        </Box>
      )}
      <DialogoCopiar r={r} abierto={copiar} alCerrar={() => setCopiar(false)} alCopiar={(nueva, t) => { setCopiar(false); setR(nueva); avisar('success', t) }} />
      <Siguiente ir={ir} a="comprobantes" texto="Comprobantes" />
    </>
  )
}
