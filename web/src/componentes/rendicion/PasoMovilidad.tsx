/**
 * Paso «Movilidad» (2026-10-18): la declaración jurada (Anexo 3).
 *
 * La movilidad es de la COMISIÓN, no de cada rendición (Edison: «los dos trabajadores tienen los MISMOS
 * tramos, porque viajan juntos con el diputado»): lo que uno registra o corrige aparece en la rendición del
 * otro, y queda quién cambió qué («Quién cambió qué»). La línea de cada día dice cuánto alcanza A TODOS y
 * por qué («S/ 90: Ana ya gastó S/ 230 con comprobante ese día»): el menor entre el tope de declaración
 * jurada y lo que le falta a cada uno para completar su viático.
 *
 * «Ajustar a lo sugerido» dice primero, en una línea, qué hará (lo simula el servidor) y después ofrece
 * «Deshacer»; el último cambio de la movilidad, sea de quien sea, se puede deshacer desde la barra. Nunca
 * pasa los topes (2026-10-18; `rendicion.plan_ajuste`): el tope diario de declaración jurada y el viático
 * del día de cada comisionado, ni el 30 % de lo recibido de cada uno; la DJ fijada rige solo si es menor.
 * Solo cambia los montos de los tramos; la línea `lineaTopes` lo dice.
 * Abajo, los otros gastos sin comprobante de esta rendición (la declaración jurada vale solo para movilidad).
 */
import { useEffect, useState } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import ButtonBase from '@mui/material/ButtonBase'
import Chip from '@mui/material/Chip'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import IconButton from '@mui/material/IconButton'
import LinearProgress from '@mui/material/LinearProgress'
import Menu from '@mui/material/Menu'
import MenuItem from '@mui/material/MenuItem'
import Snackbar from '@mui/material/Snackbar'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import AutoFixHighOutlinedIcon from '@mui/icons-material/AutoFixHighOutlined'
import AddIcon from '@mui/icons-material/Add'
import MoreVertIcon from '@mui/icons-material/MoreVert'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import UndoIcon from '@mui/icons-material/Undo'
import PeopleOutlineIcon from '@mui/icons-material/PeopleOutline'
import { api } from '@qillqa/tiqsi'
import { PALETA } from '@qillqa/tiqsi'
import { BarraModulo } from '@qillqa/tiqsi'
import CampoImporte from './CampoImporte'
import { Seccion, Siguiente, type PropsPaso } from './paso'
import { diaCorto, lineaTopes, siguienteTramo, soles, solesCorto, textoPlan, type Declarado, type PasoPlan, type Rendicion } from './modelo'

type Edicion = { clase: 'movilidad' | 'otro'; x: Declarado | null; fecha: string; desde?: string }
interface Lote { lote: string; texto: string; usuario: string; en: string | null; deshecho: boolean; es_deshacer: boolean; detalle: string[] }

function FormDeclarado({ r, e, alCerrar, alGuardar, alSerie }: { r: Rendicion; e: Edicion | null; alCerrar: () => void; alGuardar: (t: string) => void; alSerie: () => void }) {
  const [f, setF] = useState({ fecha: '', hora: '', desde: '', hasta: '', concepto: '', monto: '' })
  const [error, setError] = useState('')
  const [enSerie, setEnSerie] = useState(0)
  const [ocupado, setOcupado] = useState(false)
  useEffect(() => {
    if (!e) return
    setError('')
    setEnSerie(0)
    setF(e.x ? { fecha: e.x.fecha, hora: e.x.hora, desde: e.x.desde, hasta: e.x.hasta, concepto: e.x.concepto, monto: e.x.monto ? String(e.x.monto) : '' }
      : { fecha: e.fecha, hora: '', desde: e.desde ?? '', hasta: '', concepto: '', monto: '' })
  }, [e])
  if (!e) return null
  // Los tramos son de la comisión (/tramos); los otros gastos, de la rendición (/declarados).
  const base = `/api/rendiciones/${r.id}/${e.clase === 'movilidad' ? 'tramos' : 'declarados'}`
  const guardar = async (otro = false) => {
    setOcupado(true)
    try {
      const cuerpo = JSON.stringify({ clase: e.clase, ...f, monto: f.monto || 0 })
      if (e.x) await api(`${base}/${e.x.id}`, { method: 'PUT', body: cuerpo })
      else await api(base, { method: 'POST', body: cuerpo })
      if (otro && !e.x) {
        // El siguiente tramo: mismo día, sale de donde llegó este; hora, destino y monto en blanco.
        setF(e.clase === 'movilidad' ? siguienteTramo(f) : { ...f, concepto: '', monto: '' })
        setEnSerie((n) => n + 1)
        setError('')
        alSerie()
        return
      }
      alGuardar(e.x ? 'Guardado.' : enSerie ? `${enSerie + 1} agregados.` : 'Agregado.')
    } catch (er) { setError(er instanceof Error ? er.message : 'No se pudo guardar.') } finally { setOcupado(false) }
  }
  const quitar = async () => {
    try { await api(`${base}/${e.x!.id}`, { method: 'DELETE' }); alGuardar('Quitado.') } catch (er) { setError(er instanceof Error ? er.message : 'No se pudo quitar.') }
  }
  const poner = (k: keyof typeof f) => (ev: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: ev.target.value })
  const otros = r.comision.miembros.filter((m) => m.id !== r.id)
  return (
    <Dialog open onClose={alCerrar} fullWidth maxWidth="xs">
      <DialogTitle sx={{ display: 'flex', alignItems: 'center' }}>
        <Box sx={{ flex: 1 }}>{e.clase === 'movilidad' ? 'Tramo de movilidad' : 'Gasto sin comprobante'}{enSerie > 0 && <Typography component="span" variant="body2" sx={{ ml: 1, color: PALETA.exito }}>{enSerie} agregado(s)</Typography>}</Box>
        {e.x && <IconButton aria-label="Quitar" onClick={() => void quitar()}><DeleteOutlineIcon /></IconButton>}
      </DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, pt: '8px !important' }}>
        {e.clase === 'movilidad' && otros.length > 0 && (
          <Typography variant="caption" color="text.secondary">Se guarda para toda la comisión: lo verá también {otros.map((m) => m.comisionado).join(' y ')}.</Typography>
        )}
        {e.clase === 'otro' && (
          <Typography variant="caption" color="text.secondary">La declaración jurada vale solo para la movilidad; lo demás va con comprobante.</Typography>
        )}
        <Box sx={{ display: 'flex', gap: 1.5 }}>
          <TextField select label="Día" value={f.fecha} onChange={poner('fecha')} size="small" sx={{ flex: 1, minWidth: 0 }}>
            {r.dias.map((d) => <MenuItem key={d} value={d}>{diaCorto(d)}</MenuItem>)}
          </TextField>
          {e.clase === 'movilidad' && <TextField type="time" label="Hora" value={f.hora} onChange={poner('hora')} size="small" InputLabelProps={{ shrink: true }} sx={{ minWidth: 132, flexShrink: 0 }} />}
        </Box>
        {e.clase === 'movilidad' ? (
          <>
            <TextField label="Del" value={f.desde} onChange={poner('desde')} size="small" placeholder="Ej.: Hospedaje" />
            <TextField label="Al" value={f.hasta} onChange={poner('hasta')} size="small" placeholder="Ej.: Terminal terrestre" autoFocus={enSerie > 0} />
          </>
        ) : <TextField label="Concepto" value={f.concepto} onChange={poner('concepto')} size="small" placeholder="Ej.: Fotocopias del material" />}
        <CampoImporte label="Monto" value={f.monto} alCambiar={(v) => setF({ ...f, monto: v })} size="small" />
        {e.x?.actualizado_por && <Typography variant="caption" color="text.secondary">Último cambio: {e.x.actualizado_por}.</Typography>}
        {error && <Typography variant="body2" sx={{ color: PALETA.error }}>{error}</Typography>}
      </DialogContent>
      <DialogActions>
        <Button onClick={alCerrar}>{enSerie ? 'Cerrar' : 'Cancelar'}</Button>
        {!e.x && <Button disabled={!f.fecha || ocupado} onClick={() => void guardar(true)}>Guardar y otro</Button>}
        <Button variant="contained" disabled={!f.fecha || ocupado} onClick={() => void guardar()}>Guardar</Button>
      </DialogActions>
    </Dialog>
  )
}

/** Quién cambió qué en la movilidad de la comisión. */
function Historial({ r, abierto, alCerrar }: { r: Rendicion; abierto: boolean; alCerrar: () => void }) {
  const [lotes, setLotes] = useState<Lote[] | null>(null)
  useEffect(() => {
    if (!abierto) return
    setLotes(null)
    api<Lote[]>(`/api/rendiciones/${r.id}/movilidad/cambios`).then(setLotes).catch(() => setLotes([]))
  }, [abierto, r.id])
  const cuando = (iso: string | null) => (iso ? new Date(iso).toLocaleString('es-PE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '')
  return (
    <Dialog open={abierto} onClose={alCerrar} fullWidth maxWidth="sm">
      <DialogTitle>Quién cambió qué</DialogTitle>
      <DialogContent sx={{ pt: '4px !important' }}>
        {lotes === null && <LinearProgress />}
        {lotes?.length === 0 && <Typography variant="body2" color="text.secondary">Aún no hay cambios registrados.</Typography>}
        {lotes?.map((l) => (
          <Box key={l.lote} sx={{ py: 1, borderTop: '1px solid', borderColor: 'divider', opacity: l.deshecho ? 0.55 : 1 }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {l.texto}{l.deshecho && <Box component="span" sx={{ fontWeight: 400, color: 'text.secondary' }}> · deshecho</Box>}
            </Typography>
            <Typography variant="caption" color="text.secondary" component="div">{l.usuario || 'El sistema'} · {cuando(l.en)}</Typography>
            {l.detalle.slice(0, 4).map((d, i) => <Typography key={i} variant="caption" component="div" sx={{ color: 'text.secondary', pl: 1 }}>{d}</Typography>)}
            {l.detalle.length > 4 && <Typography variant="caption" component="div" sx={{ color: 'text.secondary', pl: 1 }}>y {l.detalle.length - 4} más</Typography>}
          </Box>
        ))}
      </DialogContent>
      <DialogActions><Button onClick={alCerrar}>Cerrar</Button></DialogActions>
    </Dialog>
  )
}

export default function PasoMovilidad({ r, setR, recargar, avisar, ir, soloLectura }: PropsPaso) {
  const [editar, setEditar] = useState<Edicion | null>(null)
  const [menuDia, setMenuDia] = useState<{ ancla: HTMLElement; fecha: string } | null>(null)
  const [fijar, setFijar] = useState<{ fecha: string; monto: string } | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [vaciar, setVaciar] = useState<{ fecha: string | null } | null>(null)
  const [plan, setPlan] = useState<{ fecha: string | null; pasos: PasoPlan[] } | null>(null)
  const [hecho, setHecho] = useState<string | null>(null)   // snackbar con «Deshacer»
  const [historial, setHistorial] = useState(false)
  const liq = r.liquidacion
  const fija = Boolean(r.comision.bloqueada_por) && !r.puede_administrar
  const editable = !soloLectura && !fija
  const otros = r.comision.miembros.filter((m) => m.id !== r.id)

  const accion = async (ruta: string, cuerpo: object, texto: (x: Record<string, number>) => string, conDeshacer = true) => {
    setOcupado(true)
    try {
      const res = await api<{ rendicion: Rendicion } & Record<string, number>>(`/api/rendiciones/${r.id}/${ruta}`, { method: 'POST', body: JSON.stringify(cuerpo) })
      setR(res.rendicion)
      if (conDeshacer) setHecho(texto(res))
      else avisar('success', texto(res))
    } catch (e) {
      avisar('error', e instanceof Error ? e.message : 'No se pudo completar.')
    } finally {
      setOcupado(false)
    }
  }
  const deshacer = () => accion('movilidad/deshacer', {}, (x) => `Deshecho.${x.saltados ? ` ${x.saltados} tramo(s) ya se habían cambiado después y quedaron.` : ''}`, false)
  // «Ajustar a lo sugerido»: primero se pide el plan (simulado) y se muestra en una línea.
  const pedirPlan = async (fecha: string | null) => {
    try {
      const res = await api<{ plan: PasoPlan[] }>(`/api/rendiciones/${r.id}/movilidad/ajustar`, { method: 'POST', body: JSON.stringify({ simular: true, ...(fecha ? { fecha } : {}) }) })
      setPlan({ fecha, pasos: res.plan })
    } catch (e) { avisar('error', e instanceof Error ? e.message : 'No se pudo calcular.') }
  }
  const guardarObjetivo = async (fecha: string, monto: string | null) => {
    const actuales = { ...(r.comision.dj_objetivo ?? {}) }
    if (monto === null || monto === '') delete actuales[fecha]
    else actuales[fecha] = Number(monto.replace(',', '.'))
    try {
      setR(await api<Rendicion>(`/api/rendiciones/${r.id}`, { method: 'PUT', body: JSON.stringify({ datos: { dj_objetivo: Object.keys(actuales).length ? actuales : null } }) }))
      setHecho(monto ? `DJ del ${diaCorto(fecha)} fijada en ${solesCorto(Number(monto))} para toda la comisión.` : 'Vuelve a regir lo sugerido.')
    } catch (e) { avisar('error', e instanceof Error ? e.message : 'No se pudo guardar.') }
  }

  const tramos = r.declarados.filter((x) => x.clase === 'movilidad')
  const otrosGastos = r.declarados.filter((x) => x.clase === 'otro')
  const ultimo = r.comision.ultimo_cambio
  return (
    <>
      <BarraModulo
        principal={editable && (
          <Button variant="contained" startIcon={<AutoFixHighOutlinedIcon />} disabled={ocupado || tramos.length === 0} onClick={() => void pedirPlan(null)}>
            Ajustar a lo sugerido
          </Button>
        )}
        mas={[
          editable && ultimo && { etiqueta: `Deshacer: ${ultimo.texto}`, icono: <UndoIcon fontSize="small" />, alPulsar: () => void deshacer() },
          { etiqueta: 'Quién cambió qué', icono: <PeopleOutlineIcon fontSize="small" />, alPulsar: () => setHistorial(true) },
          editable && r.semana && { etiqueta: 'Proponer tramos de los días sin tramos', alPulsar: () => void accion('movilidad/proponer', {}, (x) => `${x.creados} tramo(s) propuestos desde las actividades.`) },
          editable && r.semana && { etiqueta: 'Volver a proponer todos los tramos', alPulsar: () => void accion('movilidad/proponer', { reemplazar: true }, (x) => `${x.creados} tramo(s) propuestos de nuevo.`) },
          editable && { etiqueta: 'Quitar todos los tramos…', alPulsar: () => setVaciar({ fecha: null }) },
        ]}
      >
        <Typography variant="body2" color="text.secondary">Hasta {solesCorto(liq.tope_dj)} por día · total {soles(liq.dj)} ({liq.pct_dj.toFixed(1)} % de lo recibido)</Typography>
      </BarraModulo>
      {editable && tramos.length > 0 && (
        <Typography variant="caption" color="text.secondary" component="div" sx={{ px: 0.5, mt: -0.5, mb: 1 }}>{lineaTopes(liq)}</Typography>
      )}

      {fija ? (
        <Alert severity="info" sx={{ mb: 1.5 }}>La movilidad es compartida y {r.comision.bloqueada_por} ya presentó su rendición: quedó fija.</Alert>
      ) : otros.length > 0 ? (
        <Alert severity="info" icon={<PeopleOutlineIcon fontSize="small" />} sx={{ mb: 1.5, py: 0.25 }}>
          Movilidad compartida con {otros.map((m) => m.comisionado).join(' y ')}: lo que registre o corrija aquí se ve en las dos rendiciones.
        </Alert>
      ) : null}
      {editable && ultimo && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, px: 0.5 }}>
          <Typography variant="caption" color="text.secondary" sx={{ flex: 1, minWidth: 0 }} noWrap>Último cambio: {ultimo.texto}{ultimo.usuario ? ` (${ultimo.usuario})` : ''}</Typography>
          <Button size="small" startIcon={<UndoIcon fontSize="small" />} disabled={ocupado} onClick={() => void deshacer()}>Deshacer</Button>
        </Box>
      )}

      {liq.dias.map((d) => {
        const del = tramos.filter((t) => t.fecha === d.fecha).sort((x, y) => (x.hora || '99:99').localeCompare(y.hora || '99:99') || x.orden - y.orden)
        // Lo que «Ajustar» pondría: la DJ fijada si es menor que lo que alcanza a todos; si no, lo que alcanza.
        const alcanza = d.compartida ?? d.sugerida
        const meta = d.objetivo !== null ? Math.min(d.objetivo, alcanza) : alcanza
        const distinta = Math.round(d.movilidad * 100) !== Math.round(meta * 100)
        return (
          <Seccion key={d.fecha} titulo={diaCorto(d.fecha)}
            acciones={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                {!d.dj_ok && <Chip size="small" variant="outlined" label="Pasa el tope" sx={{ height: 22, color: PALETA.error, borderColor: PALETA.error }} />}
                {!d.total_ok && d.dj_ok && <Chip size="small" variant="outlined" label="Pasa el viático" sx={{ height: 22, color: PALETA.error, borderColor: PALETA.error }} />}
                <Typography variant="body2" sx={{ fontWeight: 700 }}>{soles(d.movilidad)}</Typography>
                {editable && <IconButton size="small" aria-label="Opciones del día" onClick={(e) => setMenuDia({ ancla: e.currentTarget, fecha: d.fecha })}><MoreVertIcon fontSize="small" /></IconButton>}
              </Box>
            }>
            <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, mb: 0.5, flexWrap: 'wrap' }}>
              <Typography variant="caption" sx={{ color: distinta ? PALETA.avisoOscuro : 'text.secondary', flex: 1, minWidth: 0 }}>
                {d.objetivo !== null ? `DJ del día fijada: ${solesCorto(d.objetivo)}.` : (d.explicacion || `Sugerida: ${solesCorto(d.sugerida)}.`)}
                {distinta && ` Hoy suman ${solesCorto(d.movilidad)}.`}
              </Typography>
              {distinta && editable && del.length > 0 && (
                <Button size="small" sx={{ py: 0, minHeight: 0 }} disabled={ocupado} onClick={() => void pedirPlan(d.fecha)}>Ajustar</Button>
              )}
            </Box>
            {del.map((t) => (
              <ButtonBase key={t.id} disabled={!editable} onClick={() => setEditar({ clase: 'movilidad', x: t, fecha: d.fecha })}
                sx={{ display: 'flex', width: '100%', gap: 1, alignItems: 'center', textAlign: 'left', py: 0.75, borderTop: '1px solid', borderColor: 'divider' }}>
                <Typography variant="caption" sx={{ width: 42, flexShrink: 0, color: 'text.secondary' }}>{t.hora || '—'}</Typography>
                <Typography variant="body2" sx={{ flex: 1, minWidth: 0 }}>{t.desde || '¿?'} → {t.hasta || '¿?'}</Typography>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>{soles(t.monto)}</Typography>
              </ButtonBase>
            ))}
            {del.length === 0 && <Typography variant="body2" color="text.secondary">Sin tramos.</Typography>}
            {editable && <Button size="small" startIcon={<AddIcon />} onClick={() => setEditar({ clase: 'movilidad', x: null, fecha: d.fecha, desde: del.length ? del[del.length - 1].hasta : '' })} sx={{ mt: 0.5 }}>Tramo</Button>}
          </Seccion>
        )
      })}

      <Seccion titulo="Otros gastos sin comprobante" acciones={!soloLectura && <Button size="small" startIcon={<AddIcon />} onClick={() => setEditar({ clase: 'otro', x: null, fecha: r.dias[0] ?? '' })}>Agregar</Button>}>
        {otrosGastos.length === 0 && <Typography variant="body2" color="text.secondary">Ninguno. La declaración jurada vale solo para la movilidad; lo demás va con comprobante.</Typography>}
        {otrosGastos.map((x) => (
          <ButtonBase key={x.id} disabled={soloLectura} onClick={() => setEditar({ clase: 'otro', x, fecha: x.fecha })}
            sx={{ display: 'flex', width: '100%', gap: 1, textAlign: 'left', py: 0.75, borderTop: '1px solid', borderColor: 'divider' }}>
            <Typography variant="caption" sx={{ width: 70, flexShrink: 0, color: 'text.secondary' }}>{diaCorto(x.fecha)}</Typography>
            <Typography variant="body2" sx={{ flex: 1, minWidth: 0 }}>{x.concepto}</Typography>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>{soles(x.monto)}</Typography>
          </ButtonBase>
        ))}
      </Seccion>
      <Typography variant="body2" sx={{ px: 0.5, mb: 1 }}>Declaración jurada: <b>{soles(liq.dj)}</b> ({liq.dj_en_letras}).</Typography>
      <Siguiente ir={ir} a="revision" texto="Revisión" />

      <Menu anchorEl={menuDia?.ancla} open={Boolean(menuDia)} onClose={() => setMenuDia(null)}>
        <MenuItem onClick={() => { const f = menuDia!.fecha; setMenuDia(null); void pedirPlan(f) }}>Ajustar el día a lo sugerido</MenuItem>
        <MenuItem onClick={() => { const f = menuDia!.fecha; const d = liq.dias.find((x) => x.fecha === f); setMenuDia(null); setFijar({ fecha: f, monto: d?.objetivo !== null && d?.objetivo !== undefined ? String(d.objetivo) : String(d?.compartida ?? d?.sugerida ?? '') }) }}>Fijar la DJ del día…</MenuItem>
        <MenuItem onClick={() => { const f = menuDia!.fecha; setMenuDia(null); setVaciar({ fecha: f }) }}>Quitar los tramos del día…</MenuItem>
      </Menu>

      <Dialog open={Boolean(plan)} onClose={() => setPlan(null)} fullWidth maxWidth="xs">
        <DialogTitle>{plan?.fecha ? `Ajustar el ${diaCorto(plan.fecha)}` : 'Ajustar a lo sugerido'}</DialogTitle>
        <DialogContent sx={{ pt: '4px !important' }}>
          <Typography variant="body2">{plan ? textoPlan(plan.pasos) : ''}</Typography>
          {plan?.pasos.filter((p) => p.cambia).slice(0, 5).map((p) => (
            <Typography key={p.fecha} variant="caption" color="text.secondary" component="div" sx={{ mt: 0.5 }}>{diaCorto(p.fecha)}: {p.explicacion}</Typography>
          ))}
          <Typography variant="caption" component="div" sx={{ mt: 1, color: PALETA.exito }}>{lineaTopes(liq)}</Typography>
          {otros.length > 0 && plan?.pasos.some((p) => p.cambia) && (
            <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 1 }}>Cambia también en la rendición de {otros.map((m) => m.comisionado).join(' y ')}. Se puede deshacer.</Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPlan(null)}>Cancelar</Button>
          <Button variant="contained" disabled={!plan?.pasos.some((p) => p.cambia) || ocupado}
            onClick={() => { const f = plan?.fecha; setPlan(null); void accion('movilidad/ajustar', f ? { fecha: f } : {}, (x) => `Ajustado: ${x.dias} día(s).`) }}>Ajustar</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(fijar)} onClose={() => setFijar(null)} fullWidth maxWidth="xs">
        <DialogTitle>DJ del {fijar ? diaCorto(fijar.fecha) : ''}</DialogTitle>
        <DialogContent sx={{ pt: '8px !important' }}>
          <CampoImporte autoFocus fullWidth label="Monto del día" value={fijar?.monto ?? ''} alCambiar={(v) => fijar && setFijar({ ...fijar, monto: v })}
            helperText="Rige para toda la comisión; «Ajustar» lo reparte entre los tramos." />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { if (fijar) void guardarObjetivo(fijar.fecha, null); setFijar(null) }}>Usar lo sugerido</Button>
          <Box sx={{ flex: 1 }} />
          <Button variant="contained" onClick={() => { if (fijar) void guardarObjetivo(fijar.fecha, fijar.monto); setFijar(null) }}>Fijar</Button>
        </DialogActions>
      </Dialog>
      <FormDeclarado r={r} e={editar} alCerrar={() => { setEditar(null); void recargar() }} alGuardar={(t) => { setEditar(null); void recargar(); avisar('success', t) }} alSerie={() => void recargar()} />
      <Dialog open={Boolean(vaciar)} onClose={() => setVaciar(null)} fullWidth maxWidth="xs">
        <DialogTitle>{vaciar?.fecha ? `Quitar los tramos del ${diaCorto(vaciar.fecha)}` : 'Quitar todos los tramos'}</DialogTitle>
        <DialogContent><Typography variant="body2">Para escribir la ruta real desde cero{otros.length ? ', para toda la comisión' : ''}. Se puede deshacer.</Typography></DialogContent>
        <DialogActions>
          <Button onClick={() => setVaciar(null)}>Cancelar</Button>
          <Button variant="contained" onClick={() => { const f = vaciar?.fecha ?? null; setVaciar(null); void accion('movilidad/vaciar', f ? { fecha: f } : {}, (x) => `${x.quitados} tramo(s) quitados.`) }}>Quitar</Button>
        </DialogActions>
      </Dialog>
      <Historial r={r} abierto={historial} alCerrar={() => setHistorial(false)} />
      <Snackbar open={hecho !== null} autoHideDuration={8000} onClose={() => setHecho(null)} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        {hecho !== null ? (
          <Alert severity="success" variant="filled" onClose={() => setHecho(null)} sx={{ maxWidth: 'calc(100vw - 32px)', alignItems: 'center' }}
            action={<Button color="inherit" size="small" startIcon={<UndoIcon fontSize="small" />} onClick={() => { setHecho(null); void deshacer() }}>Deshacer</Button>}>
            {hecho}
          </Alert>
        ) : undefined}
      </Snackbar>
    </>
  )
}
