/**
 * Paso «Comprobantes» (2026-10-18): boletas y facturas por día, con su foto. Entrada doble
 * (`ElegirEntrada`): con ayuda de la IA (pegar lo que leyó de las fotos) o a mano; y «Subir comprobantes»
 * (2026-10-18; antes «Subir fotos») para tomar todas las fotos o PDF primero desde el celular y completarlos
 * después (el pegado los llena en orden).
 * Cada día dice cuánto lleva de su viático; lo que tiene un control pendiente lleva su marca.
 */
import { useEffect, useRef, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import ButtonBase from '@mui/material/ButtonBase'
import Chip from '@mui/material/Chip'
import Typography from '@mui/material/Typography'
import FormControlLabel from '@mui/material/FormControlLabel'
import Switch from '@mui/material/Switch'
import AddIcon from '@mui/icons-material/Add'
import AddAPhotoOutlinedIcon from '@mui/icons-material/AddAPhotoOutlined'
import ReceiptOutlinedIcon from '@mui/icons-material/ReceiptOutlined'
import PictureAsPdfOutlinedIcon from '@mui/icons-material/PictureAsPdfOutlined'
import { api, subirArchivo } from '@qillqa/tiqsi'
import { PALETA } from '@qillqa/tiqsi'
import { ElegirEntrada, hay } from '@qillqa/tiqsi'
import FormComprobante from './FormComprobante'
import PegarComprobantes from './PegarComprobantes'
import { colorNivel } from './estilo'
import { Seccion, Siguiente, useImagen, type PropsPaso } from './paso'
import { conceptoDe, diaCorto, numeroCorto, porDia, soles, type Comprobante, type Control, type Rendicion } from './modelo'

/** El texto del control sin el nombre del comprobante (ya está en la fila): «Está dos veces.». */
function sinNombre(texto: string, nombre: string): string {
  if (!texto.startsWith(nombre)) return texto
  const resto = texto.slice(nombre.length).replace(/^[:\s]+/, '')
  return resto.charAt(0).toUpperCase() + resto.slice(1)
}

function Miniatura({ rid, c }: { rid: number; c: Comprobante }) {
  const esPdf = c.archivo.endsWith('.pdf')
  const url = useImagen(c.archivo && !esPdf ? `/api/rendiciones/${rid}/comprobantes/${c.id}/archivo` : null)
  return (
    <Box sx={{ width: 44, height: 56, borderRadius: 1, flexShrink: 0, overflow: 'hidden', bgcolor: PALETA.superficieMedia, display: 'grid', placeItems: 'center' }}>
      {url ? <Box component="img" src={url} alt="" sx={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        : esPdf ? <PictureAsPdfOutlinedIcon sx={{ color: PALETA.textoTenue }} /> : <ReceiptOutlinedIcon sx={{ color: PALETA.apagado }} />}
    </Box>
  )
}

function Fila({ rid, c, controles, alAbrir }: { rid: number; c: Comprobante; controles: Control[]; alAbrir: () => void }) {
  const peor = controles.find((x) => x.nivel === 'error') ?? controles[0]
  const sinDatos = !c.numero && !c.importe
  return (
    <ButtonBase onClick={alAbrir} sx={{ display: 'flex', width: '100%', gap: 1.25, alignItems: 'center', textAlign: 'left', py: 1, px: 0.5, borderTop: '1px solid', borderColor: 'divider' }}>
      <Miniatura rid={rid} c={c} />
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography variant="body2" sx={{ fontWeight: 600 }} noWrap>{sinDatos ? 'Foto por completar' : numeroCorto(c)}</Typography>
        <Typography variant="caption" color="text.secondary" component="div" noWrap>
          {sinDatos && c.nota ? c.nota.replace(/^Archivo:\s*/, '') : <>{conceptoDe(c.concepto)}{c.proveedor ? ` · ${c.proveedor}` : ''}</>}
        </Typography>
        {peor && <Typography variant="caption" sx={{ color: colorNivel(peor.nivel), display: 'block', lineHeight: 1.3 }}>{sinNombre(peor.texto, c.documento)}</Typography>}
      </Box>
      <Typography variant="body2" sx={{ fontWeight: 700, flexShrink: 0 }}>{soles(c.importe)}</Typography>
    </ButtonBase>
  )
}

export default function PasoComprobantes({ r, setR, recargar, avisar, ir, soloLectura, textoPegar, alConsumirPegar }: PropsPaso & { textoPegar?: string; alConsumirPegar?: () => void }) {
  const [ancla, setAncla] = useState<HTMLElement | null>(null)
  const [editando, setEditando] = useState<Comprobante | null | undefined>(undefined)   // undefined = cerrado; null = nuevo
  const [pegando, setPegando] = useState(false)
  const [textoInicial, setTextoInicial] = useState('')
  const fotos = useRef<HTMLInputElement | null>(null)
  const [subiendo, setSubiendo] = useState(false)

  useEffect(() => {
    if (!textoPegar) return
    setTextoInicial(textoPegar)
    setPegando(true)
    alConsumirPegar?.()
  }, [textoPegar, alConsumirPegar])

  const subirFotos = async (archivos: FileList | null) => {
    if (!archivos?.length) return
    setSubiendo(true)
    try {
      const datos = new FormData()
      Array.from(archivos).forEach((a) => datos.append('archivos', a))
      await subirArchivo(`/api/rendiciones/${r.id}/fotos`, datos)
      await recargar()
      avisar('success', `${archivos.length} comprobante(s) subidos. Complételos a mano o pegue lo que leyó la IA.`)
    } catch (e) {
      avisar('error', e instanceof Error ? e.message : 'No se pudieron subir.')
    } finally {
      setSubiendo(false)
      if (fotos.current) fotos.current.value = ''
    }
  }

  const porRef = (id: number) => r.controles.filter((x) => x.ref === `comprobante:${id}`)
  const dia = new Map(r.liquidacion.dias.map((d) => [d.fecha, d]))
  const sinDatos = r.comprobantes.filter((c) => !c.numero && !c.importe)
  const conDatos = r.comprobantes.filter((c) => c.numero || c.importe)
  const deViatico = conDatos.filter((c) => !['pasaje_terrestre', 'otro_recurso'].includes(c.concepto))
  const otrasSecciones = conDatos.filter((c) => ['pasaje_terrestre', 'otro_recurso'].includes(c.concepto))
  const liq = r.liquidacion
  // «Se entregaron en físico» (2026-10-18): la foto deja de faltar en los controles.
  const enFisico = ['si', 'sí'].includes(String(r.datos_propios.en_fisico ?? '').toLowerCase())
  const cambiarFisico = async (v: boolean) => {
    try {
      setR(await api<Rendicion>(`/api/rendiciones/${r.id}`, { method: 'PUT', body: JSON.stringify({ datos: { en_fisico: v ? 'si' : '' } }) }))
    } catch (e) { avisar('error', e instanceof Error ? e.message : 'No se pudo guardar.') }
  }

  return (
    <>
      {!soloLectura && (
        <Box sx={{ display: 'flex', gap: 1, mb: 1.5, flexWrap: 'wrap' }}>
          <Button variant="contained" startIcon={<AddIcon />} onClick={(e) => (hay('ElegirEntrada') ? setAncla(e.currentTarget) : setEditando(null))}>Agregar</Button>
          <Button variant="outlined" startIcon={<AddAPhotoOutlinedIcon />} disabled={subiendo} onClick={() => fotos.current?.click()}>{subiendo ? 'Subiendo…' : 'Subir comprobantes'}</Button>
          <input ref={fotos} hidden type="file" multiple accept="image/*,application/pdf" onChange={(e) => void subirFotos(e.target.files)} />
        </Box>
      )}
      <Box sx={{ display: 'flex', gap: 2, mb: 1.5, flexWrap: 'wrap', px: 0.5 }}>
        <Typography variant="body2"><b>{soles(liq.con_comprobante)}</b> <Box component="span" sx={{ color: 'text.secondary' }}>con comprobante</Box></Typography>
        {liq.pasajes.rendido > 0 && <Typography variant="body2"><b>{soles(liq.pasajes.rendido)}</b> <Box component="span" sx={{ color: 'text.secondary' }}>pasajes</Box></Typography>}
        {liq.otros.rendido > 0 && <Typography variant="body2"><b>{soles(liq.otros.rendido)}</b> <Box component="span" sx={{ color: 'text.secondary' }}>otros recursos</Box></Typography>}
        <Box sx={{ flex: 1 }} />
        <FormControlLabel sx={{ mr: 0, '& .MuiFormControlLabel-label': { fontSize: 13, color: 'text.secondary' } }}
          control={<Switch size="small" checked={enFisico} disabled={soloLectura} onChange={(e) => void cambiarFisico(e.target.checked)} />}
          label="Entregados en físico (sin foto)" />
      </Box>

      {sinDatos.length > 0 && (
        <Seccion titulo={`Fotos por completar (${sinDatos.length})`} acciones={!soloLectura && <Button size="small" onClick={() => setPegando(true)}>Pegar lo que leyó la IA</Button>}>
          {sinDatos.map((c) => <Fila key={c.id} rid={r.id} c={c} controles={[]} alAbrir={() => setEditando(c)} />)}
        </Seccion>
      )}

      {porDia(deViatico, r.dias).map((g) => {
        const d = dia.get(g.fecha)
        return (
          <Seccion key={g.fecha || 'sin'} titulo={g.fecha ? diaCorto(g.fecha) : 'Sin fecha'}
            acciones={g.fuera
              ? <Chip size="small" variant="outlined" label="Fuera de la comisión" sx={{ color: PALETA.error, borderColor: PALETA.error }} />
              : d && (
                <Typography variant="caption" sx={{ color: d.exceso > 0 ? PALETA.error : 'text.secondary', fontWeight: d.exceso > 0 ? 600 : 400 }}>
                  {soles(d.subtotal_a)} de {soles(d.asignado)}{d.exceso > 0 ? ` · ${soles(d.exceso)} lo asume` : ''}
                </Typography>
              )}>
            {g.filas.map((c) => <Fila key={c.id} rid={r.id} c={c} controles={porRef(c.id)} alAbrir={() => setEditando(c)} />)}
          </Seccion>
        )
      })}

      {otrasSecciones.length > 0 && (
        <Seccion titulo="Pasajes terrestres y otros recursos">
          {otrasSecciones.map((c) => <Fila key={c.id} rid={r.id} c={c} controles={porRef(c.id)} alAbrir={() => setEditando(c)} />)}
        </Seccion>
      )}

      {r.comprobantes.length === 0 && (
        <Box sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
          <ReceiptOutlinedIcon sx={{ fontSize: 40, color: PALETA.apagado }} />
          <Typography variant="body2">Aún no hay comprobantes. Tome las fotos o agréguelos.</Typography>
        </Box>
      )}
      <Siguiente ir={ir} a="movilidad" texto="Movilidad" />

      <ElegirEntrada
        ancla={ancla}
        alCerrar={() => setAncla(null)}
        tipo="comprobantes-gasto"
        etiquetaManual="Uno por uno"
        ayudaManual="Escriba los datos de cada comprobante y tome su foto."
        ayudaPrompt="Su IA lee las fotos de los comprobantes; pegue lo que responda y se agregan todos."
        alManual={() => setEditando(null)}
        alPrompt={() => { setTextoInicial(''); setPegando(true) }}
      />
      <FormComprobante
        r={r} comprobante={editando ?? null} abierto={editando !== undefined} soloLectura={soloLectura}
        alCerrar={() => setEditando(undefined)}
        alGuardar={(t) => { setEditando(undefined); void recargar(); avisar('success', t) }}
        alSerie={() => void recargar()}
      />
      <PegarComprobantes
        r={r} abierto={pegando} textoInicial={textoInicial}
        alCerrar={() => setPegando(false)}
        alAplicar={(nueva, t) => { setPegando(false); setR(nueva); avisar('success', t) }}
      />
    </>
  )
}
