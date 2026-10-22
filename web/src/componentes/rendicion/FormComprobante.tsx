/**
 * Un comprobante, a mano (2026-10-18): fecha (los días de la comisión a un toque), tipo, serie y número,
 * RUC y proveedor (opcionales), concepto e importe, y su foto o PDF —en el celular abre la cámara—.
 * Guardar crea o cambia el comprobante y, si se eligió foto, la sube.
 *
 * Ensayo con las rendiciones reales (2026-10-18): «Guardar y otro» (hoy «Guardar y siguiente») deja el
 * formulario abierto con el mismo tipo (los comprobantes se registran día por día); el número se puede escribir de
 * una pieza («EB01-1586») y se parte solo en serie y número; lo escrito en un comprobante nuevo no se
 * pierde si el diálogo se cierra sin guardar (queda como borrador en esta pestaña hasta guardarlo).
 *
 * Sin repetir (2026-10-18, Edison): bajo la fecha se ve, sutil, lo ya registrado ese día (concepto e importe)
 * y cada concepto ya registrado lleva un puntito; un desayuno, un almuerzo o una cena por día —si ya hay uno,
 * no se guarda otro—; el hospedaje y «otros» pueden ser más de uno y solo se avisa. «Guardar y siguiente» es
 * el botón PRINCIPAL (también con Enter en el importe): pasa al siguiente concepto del día en orden —desayuno,
 * almuerzo, cena, otros de alimentación, hospedaje— y, al acabar, al día siguiente (`siguienteConcepto`).
 * «Guardar» queda como secundario, para cuando se termina.
 *
 * La VISTA del comprobante (2026-10-18, Edison: «debajo no se ve bonito ni completo») va a la DERECHA en
 * escritorio, entera y a toda la altura, como el visor del editor de documentos y el detalle de un recibido:
 * la foto se ajusta al panel (un toque la amplía) y el PDF se ve con el visor del sistema. En el celular va
 * debajo del formulario y un toque la abre a pantalla completa.
 */
import { useEffect, useRef, useState } from 'react'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import IconButton from '@mui/material/IconButton'
import MenuItem from '@mui/material/MenuItem'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import useMediaQuery from '@mui/material/useMediaQuery'
import { useTheme } from '@mui/material/styles'
import PhotoCameraOutlinedIcon from '@mui/icons-material/PhotoCameraOutlined'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import OpenInFullIcon from '@mui/icons-material/OpenInFull'
import { api, descargarBlob, subirArchivo } from '@qillqa/tiqsi'
import { PALETA } from '@qillqa/tiqsi'
import { VisorPdf } from '@qillqa/tiqsi'
import CampoImporte from './CampoImporte'
import { useImagen } from './paso'
import { CONCEPTOS, TIPOS, conceptoDe, conceptosPorDia, dondeEmpezar, diaCorto, numeroCorto, partirNumero, registradosDelDia, revisarConcepto, rucValido, siguienteConcepto, solesCorto, unConcepto, type Comprobante, type Rendicion } from './modelo'

const VACIO = { fecha: '', tipo: 'boleta_electronica', serie: '', numero: '', ruc: '', proveedor: '', concepto: 'almuerzo', importe: '', nota: '' }
type Datos = typeof VACIO
/** El borrador de un comprobante NUEVO, por rendición (sessionStorage: puede no estar; nunca rompe). */
const claveBorrador = (rid: number) => `qillqa_rendicion_borrador_${rid}`
function leerBorrador(rid: number): Datos | null {
  try { const t = sessionStorage.getItem(claveBorrador(rid)); return t ? { ...VACIO, ...JSON.parse(t) } : null } catch { return null }
}
function guardarBorrador(rid: number, f: Datos | null) {
  try {
    const vacio = !f || (!f.importe && !f.numero && !f.serie && !f.ruc && !f.proveedor && !f.nota)
    if (vacio) sessionStorage.removeItem(claveBorrador(rid))
    else sessionStorage.setItem(claveBorrador(rid), JSON.stringify(f))
  } catch { /* sin sessionStorage */ }
}

export default function FormComprobante({ r, comprobante, abierto, alCerrar, alGuardar, alSerie, soloLectura }: {
  r: Rendicion
  comprobante: Comprobante | null      // null = nuevo
  abierto: boolean
  alCerrar: () => void
  alGuardar: (texto: string) => void
  /** Se guardó uno con «Guardar y otro»: refrescar la lista sin cerrar. */
  alSerie?: () => void
  soloLectura: boolean
}) {
  const [f, setF] = useState(VACIO)
  const [archivo, setArchivo] = useState<File | null>(null)
  const [error, setError] = useState('')
  const [ocupado, setOcupado] = useState(false)
  const entrada = useRef<HTMLInputElement | null>(null)
  const guardada = useImagen(abierto && comprobante?.archivo && !comprobante.archivo.endsWith('.pdf') ? `/api/rendiciones/${r.id}/comprobantes/${comprobante.id}/archivo` : null)
  const [local, setLocal] = useState('')
  const [enSerie, setEnSerie] = useState(0)   // cuántos se agregaron seguidos con «Guardar y siguiente»
  // Lo guardado en esta ventana mientras la rendición se recarga (para lo «ya registrado» y el siguiente concepto).
  const [guardadosAqui, setGuardadosAqui] = useState<Comprobante[]>([])
  const importeRef = useRef<HTMLInputElement | null>(null)
  const ancha = useMediaQuery(useTheme().breakpoints.up('md'))
  const [zoom, setZoom] = useState(false)

  useEffect(() => {
    if (!abierto) return
    setError('')
    setArchivo(null)
    setLocal('')
    setEnSerie(0)
    setGuardadosAqui([])
    setF(comprobante
      ? { fecha: comprobante.fecha, tipo: comprobante.tipo, serie: comprobante.serie, numero: comprobante.numero, ruc: comprobante.ruc,
          proveedor: comprobante.proveedor, concepto: comprobante.concepto, importe: comprobante.importe ? String(comprobante.importe) : '', nota: comprobante.nota }
      : leerBorrador(r.id) ?? { ...VACIO, ...dondeEmpezar(r.dias, conceptosPorDia(r.comprobantes)) })
    // Solo al abrir o al cambiar de comprobante: NO cuando la rendición se recarga (cada «Guardar y otro»
    // la recarga y `r.dias` es otro arreglo; el ensayo del 2026-10-18 vio volver la fecha al primer día).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [abierto, comprobante?.id, r.id])
  // Lo escrito en un comprobante nuevo se guarda como borrador mientras se escribe.
  useEffect(() => { if (abierto && !comprobante) guardarBorrador(r.id, f) }, [f, abierto, comprobante, r.id])
  useEffect(() => {
    if (!archivo) { setLocal(''); return }
    const u = URL.createObjectURL(archivo)
    setLocal(u)
    return () => URL.revokeObjectURL(u)
  }, [archivo])

  const guardar = async (otro = false) => {
    setOcupado(true)
    setError('')
    try {
      const cuerpo = JSON.stringify({ ...f, ...partirNumero(f.serie, f.numero), importe: f.importe || 0 })
      const c = comprobante
        ? await api<Comprobante>(`/api/rendiciones/${r.id}/comprobantes/${comprobante.id}`, { method: 'PUT', body: cuerpo })
        : await api<Comprobante>(`/api/rendiciones/${r.id}/comprobantes`, { method: 'POST', body: cuerpo })
      if (archivo) {
        const datos = new FormData()
        datos.append('archivo', archivo)
        await subirArchivo(`/api/rendiciones/${r.id}/comprobantes/${c.id}/archivo`, datos)
      }
      if (!comprobante) guardarBorrador(r.id, null)
      if (otro && !comprobante) {
        // «Guardar y siguiente» (2026-10-18): el próximo concepto del día en orden —desayuno, almuerzo, cena,
        // otros de alimentación, hospedaje— saltando las comidas ya registradas; al acabar, el día siguiente.
        // Hereda el tipo; lo demás, en blanco.
        const hechos = [...todos, c]
        const sig = siguienteConcepto(f.concepto, f.fecha, r.dias, conceptosPorDia(hechos))
        setGuardadosAqui((g) => [...g, c])
        setF({ ...VACIO, fecha: sig.fecha, tipo: f.tipo, concepto: sig.concepto })
        setArchivo(null)
        setEnSerie((n) => n + 1)
        alSerie?.()
        setTimeout(() => importeRef.current?.focus(), 50)
        return
      }
      alGuardar(comprobante ? 'Comprobante guardado.' : enSerie ? `${enSerie + 1} comprobantes agregados.` : 'Comprobante agregado.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar.')
    } finally {
      setOcupado(false)
    }
  }
  const quitar = async () => {
    if (!comprobante) return
    setOcupado(true)
    try {
      await api(`/api/rendiciones/${r.id}/comprobantes/${comprobante.id}`, { method: 'DELETE' })
      alGuardar('Comprobante quitado.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo quitar.')
    } finally {
      setOcupado(false)
    }
  }

  // Ver el archivo guardado en grande (en el celular la miniatura no deja leer el comprobante; un PDF no
  // tiene miniatura): se abre en otra pestaña con la sesión (blob).
  const verArchivo = async () => {
    if (!comprobante?.archivo) return
    try {
      const b = await descargarBlob(`/api/rendiciones/${r.id}/comprobantes/${comprobante.id}/archivo`)
      window.open(URL.createObjectURL(b), '_blank', 'noopener')
    } catch (e) { setError(e instanceof Error ? e.message : 'No se pudo abrir el archivo.') }
  }
  const poner = (k: keyof typeof VACIO) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value })
  const esPdfLocal = Boolean(archivo && archivo.type === 'application/pdf')
  const esPdfGuardado = Boolean(!archivo && comprobante?.archivo?.endsWith('.pdf'))
  const imagen = archivo ? (esPdfLocal ? '' : local) : guardada
  const hayArchivo = Boolean(archivo || comprobante?.archivo)
  const rucMal = f.ruc.length > 0 && !rucValido(f.ruc)
  const elegir = () => !soloLectura && entrada.current?.click()
  // Lo ya registrado del día elegido (sin este comprobante): se ve sutilmente y marca los conceptos con un
  // puntito; un desayuno, un almuerzo o una cena ya registrados no se repiten (2026-10-18).
  const todos = [...r.comprobantes.filter((x) => !guardadosAqui.some((g) => g.id === x.id)), ...guardadosAqui]
  const registrados = registradosDelDia(todos, f.fecha, comprobante?.id)
  const conConcepto = new Set(registrados.map((x) => x.concepto))
  let revision = revisarConcepto(f.concepto, registrados)
  // Al corregir uno que ya estaba repetido (mismo día y concepto) no se bloquea: el control lo avisa.
  if (revision.nivel === 'bloquea' && comprobante && comprobante.concepto === f.concepto && comprobante.fecha === f.fecha) revision = { ...revision, nivel: 'aviso' }
  const bloqueado = revision.nivel === 'bloquea'
  const puedeGuardar = !ocupado && Boolean(f.fecha) && Boolean(f.importe) && !rucMal && !bloqueado

  // La vista del comprobante: foto ajustada al panel, PDF en el visor, o el lugar para tomarla.
  const vista = (
    <Box sx={{ height: ancha ? '100%' : 300, minHeight: ancha ? 420 : 0, borderRadius: 2, overflow: 'hidden', bgcolor: PALETA.superficieMedia,
      border: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      {esPdfGuardado ? (
        <Box sx={{ width: '100%', height: '100%' }}>
          <VisorPdf ruta={`/api/rendiciones/${r.id}/comprobantes/${comprobante!.id}/archivo`} alto="100%" nombre={comprobante!.archivo.split('/').pop()} />
        </Box>
      ) : esPdfLocal ? (
        <Box component="object" data={local} type="application/pdf" sx={{ width: '100%', height: '100%' }}>
          <Typography variant="body2" sx={{ p: 2 }}>{archivo?.name}</Typography>
        </Box>
      ) : imagen ? (
        <Box component="img" src={imagen} alt="Comprobante" onClick={() => (ancha ? setZoom(!zoom) : void verArchivo())}
          sx={{ maxWidth: zoom ? 'none' : '100%', maxHeight: zoom ? 'none' : '100%', width: zoom ? '160%' : 'auto', objectFit: 'contain', cursor: zoom ? 'zoom-out' : 'zoom-in',
            ...(zoom ? { alignSelf: 'flex-start' } : {}) }} />
      ) : (
        <Box onClick={elegir} sx={{ textAlign: 'center', color: 'text.secondary', cursor: soloLectura ? 'default' : 'pointer', p: 3 }}>
          <PhotoCameraOutlinedIcon sx={{ fontSize: 44, color: PALETA.apagado }} />
          <Typography variant="body2" sx={{ mt: 0.5 }}>{soloLectura ? 'Sin foto' : 'Toque para tomar o elegir la foto o el PDF'}</Typography>
        </Box>
      )}
    </Box>
  )

  return (
    <Dialog open={abierto} onClose={alCerrar} fullWidth maxWidth={ancha ? 'lg' : 'sm'} PaperProps={{ sx: ancha ? { height: 'min(860px, 92vh)' } : undefined }}>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center' }}>
        <Box sx={{ flex: 1 }}>{comprobante ? 'Comprobante' : 'Nuevo comprobante'}{enSerie > 0 && <Typography component="span" variant="body2" sx={{ ml: 1, color: PALETA.exito }}>{enSerie} agregado(s)</Typography>}</Box>
        {comprobante && !soloLectura && <IconButton aria-label="Quitar el comprobante" onClick={() => void quitar()} disabled={ocupado}><DeleteOutlineIcon /></IconButton>}
        {!comprobante && !soloLectura && (f.importe || f.numero || f.serie) && (
          <Button size="small" color="inherit" onClick={() => { guardarBorrador(r.id, null); setF({ ...VACIO, fecha: f.fecha, tipo: f.tipo }) }}>Vaciar</Button>
        )}
      </DialogTitle>
      <DialogContent sx={{ pt: '8px !important', display: ancha ? 'grid' : 'flex', flexDirection: 'column', gridTemplateColumns: 'minmax(360px, 1fr) minmax(0, 1.15fr)', gap: 2.5, overflow: ancha ? 'hidden' : 'auto' }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.75, overflowY: ancha ? 'auto' : 'visible', pr: ancha ? 0.5 : 0, pt: ancha ? 0.5 : 0 }}>
          <input ref={entrada} hidden type="file" accept="image/*,application/pdf" onChange={(e) => { setArchivo(e.target.files?.[0] ?? null); setZoom(false) }} />
          <Box>
            <Typography variant="caption" color="text.secondary">Fecha</Typography>
            <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', mt: 0.5 }}>
              {r.dias.map((d) => <Chip key={d} label={diaCorto(d)} color={f.fecha === d ? 'primary' : 'default'} variant={f.fecha === d ? 'filled' : 'outlined'} onClick={() => !soloLectura && setF({ ...f, fecha: d })} />)}
              <TextField type="date" size="small" value={f.fecha} onChange={poner('fecha')} disabled={soloLectura} sx={{ width: 160 }} inputProps={{ 'aria-label': 'Otra fecha' }} />
            </Box>
            {f.fecha && (
              <Typography variant="caption" component="div" sx={{ mt: 0.75, color: 'text.secondary', lineHeight: 1.45 }}>
                {registrados.length
                  ? <>Ya registrado el {diaCorto(f.fecha)}: {registrados.map((x, i) => (
                      <Box component="span" key={x.id} sx={{ whiteSpace: 'nowrap' }}>{i ? ' · ' : ''}{conceptoDe(x.concepto)} {solesCorto(x.importe)}</Box>
                    ))}</>
                  : `Nada registrado aún el ${diaCorto(f.fecha)}.`}
              </Typography>
            )}
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Concepto</Typography>
            <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', mt: 0.5 }}>
              {CONCEPTOS.map((c) => (
                <Chip key={c.v} color={f.concepto === c.v ? 'primary' : 'default'} variant={f.concepto === c.v ? 'filled' : 'outlined'} onClick={() => !soloLectura && setF({ ...f, concepto: c.v })}
                  // Ya registrado ese día: contorno verde además del puntito (Edison, 2026-10-18).
                  sx={conConcepto.has(c.v) && f.concepto !== c.v ? { borderColor: PALETA.exito, borderWidth: 1.5, color: PALETA.exito } : undefined}
                  label={
                    <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.6 }}>
                      {conConcepto.has(c.v) && <Box component="span" title="Ya registrado ese día" sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: f.concepto === c.v ? PALETA.sobrePrimario : PALETA.exito, flexShrink: 0 }} />}
                      {c.t}
                    </Box>
                  } />
              ))}
            </Box>
            {revision.ya && (
              <Typography variant="caption" component="div" sx={{ mt: 0.75, color: bloqueado ? PALETA.error : PALETA.avisoOscuro, lineHeight: 1.4 }}>
                {bloqueado
                  ? `Ya hay ${unConcepto(f.concepto)} el ${diaCorto(f.fecha)} (${numeroCorto(revision.ya)}, ${solesCorto(revision.ya.importe)}): va uno por día. Elija otro concepto o corrija el que ya está.`
                  : `Ya hay ${unConcepto(f.concepto)} el ${diaCorto(f.fecha)} (${numeroCorto(revision.ya)}, ${solesCorto(revision.ya.importe)}): revise que no sea el mismo.`}
              </Typography>
            )}
          </Box>
          <CampoImporte label="Importe" value={f.importe} alCambiar={(v) => setF({ ...f, importe: v })} disabled={soloLectura} inputRef={importeRef} placeholder="0.00"
            onKeyDown={(e) => { if (e.key === 'Enter' && puedeGuardar && !soloLectura) { e.preventDefault(); void guardar(!comprobante) } }} />
          <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr', sm: '1.3fr 0.7fr 1fr' } }}>
            <TextField select label="Tipo" value={f.tipo} onChange={poner('tipo')} disabled={soloLectura} size="small">
              {TIPOS.map((t) => <MenuItem key={t.v} value={t.v}>{t.t}</MenuItem>)}
            </TextField>
            <TextField label="Serie" value={f.serie} onChange={poner('serie')} disabled={soloLectura} size="small" placeholder="EB01" />
            <TextField label="Número" value={f.numero} onChange={poner('numero')} disabled={soloLectura} size="small" placeholder="1586 o EB01-1586"
              onBlur={() => { const x = partirNumero(f.serie, f.numero); if (x.serie !== f.serie || x.numero !== f.numero) setF({ ...f, ...x }) }}
              helperText="Puede escribirlo entero: EB01-1586" />
          </Box>
          <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr', sm: '0.8fr 1.2fr' } }}>
            <TextField label="RUC (opcional)" value={f.ruc} onChange={poner('ruc')} disabled={soloLectura} size="small" inputProps={{ inputMode: 'numeric', maxLength: 11 }}
              error={rucMal} helperText={rucMal ? 'Revise el RUC' : 'El del proveedor, 11 dígitos'} />
            <TextField label="Proveedor (opcional)" value={f.proveedor} onChange={poner('proveedor')} disabled={soloLectura} size="small" helperText="Ej.: Restaurante El Ejemplo" />
          </Box>
          <TextField label="Detalle (opcional)" value={f.nota} onChange={poner('nota')} disabled={soloLectura} size="small" />
          {r.institucion?.a_nombre_de && (
            <Typography variant="caption" color="text.secondary">
              El comprobante va a nombre de {r.institucion.a_nombre_de}{r.institucion.ruc_a_nombre ? ` (RUC ${r.institucion.ruc_a_nombre})` : ''}.
            </Typography>
          )}
          {error && <Typography variant="body2" sx={{ color: PALETA.error }}>{error}</Typography>}
        </Box>
        <Box sx={{ minHeight: 0, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minHeight: 30 }}>
            <Typography variant="caption" color="text.secondary" noWrap sx={{ flex: 1, minWidth: 0 }}>
              {archivo ? archivo.name : comprobante?.archivo ? (ancha ? 'Foto o PDF guardado' : 'Foto o PDF guardado (toque para verlo completo)') : 'Foto o PDF del comprobante'}
            </Typography>
            {comprobante?.archivo && !archivo && !esPdfGuardado && (
              <IconButton size="small" aria-label="Ver en grande" onClick={() => void verArchivo()}><OpenInFullIcon fontSize="small" /></IconButton>
            )}
            {hayArchivo && !soloLectura && <Button size="small" variant="outlined" startIcon={<PhotoCameraOutlinedIcon />} onClick={elegir}>Cambiar</Button>}
          </Box>
          <Box sx={{ flex: 1, minHeight: 0, overflow: zoom ? 'auto' : 'hidden', borderRadius: 2 }}>{vista}</Box>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={alCerrar}>{soloLectura ? 'Cerrar' : 'Cancelar'}</Button>
        {/* «Guardar y siguiente» es lo PRINCIPAL al registrar (2026-10-18); «Guardar», para cuando se termina. */}
        {!soloLectura && !comprobante && <Button variant="outlined" disabled={!puedeGuardar} onClick={() => void guardar()}>Guardar</Button>}
        {!soloLectura && !comprobante && <Button variant="contained" disabled={!puedeGuardar} onClick={() => void guardar(true)}>Guardar y siguiente</Button>}
        {!soloLectura && comprobante && <Button variant="contained" disabled={!puedeGuardar} onClick={() => void guardar()}>Guardar</Button>}
      </DialogActions>
    </Dialog>
  )
}
