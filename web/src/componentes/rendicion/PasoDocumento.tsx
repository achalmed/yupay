/**
 * Paso «Documento» (2026-10-18): los Anexos 3 y 4 compuestos por el marco (tipo `rendicion-viaticos`,
 * LuaLaTeX con build.sh) desde la rendición, para revisar, descargar, imprimir y firmar; y la liquidación
 * en Excel con sus fórmulas. Lo que falta sale como renglón para llenar a mano.
 *
 * 2026-10-18: si algo cambió después de generarlo, el PDF se marca DESACTUALIZADO (huella del contenido)
 * para no imprimir uno viejo; y «Otros sustentos» guarda lo que acompaña y no se rinde —el boleto aéreo
 * (DI 37-2025-DF-DGA-CR, 7.9.1.1.5) y el recibo de devolución del saldo (7.9.4.2)—.
 *
 * 2026-10-18: en escritorio (≥ 900 px) el visor va a la DERECHA, a toda la altura, como el editor de
 * documentos; los botones y la información, a la izquierda.
 */
import { useRef, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import LinearProgress from '@mui/material/LinearProgress'
import Typography from '@mui/material/Typography'
import PictureAsPdfOutlinedIcon from '@mui/icons-material/PictureAsPdfOutlined'
import DownloadOutlinedIcon from '@mui/icons-material/DownloadOutlined'
import TableChartOutlinedIcon from '@mui/icons-material/TableChartOutlined'
import { api, descargarArchivo, subirArchivo } from '@qillqa/tiqsi'
import Alert from '@mui/material/Alert'
import IconButton from '@mui/material/IconButton'
import MenuItem from '@mui/material/MenuItem'
import TextField from '@mui/material/TextField'
import AttachFileIcon from '@mui/icons-material/AttachFile'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import { PALETA } from '@qillqa/tiqsi'
import { VisorPdf } from '@qillqa/tiqsi'
import { Seccion, type PropsPaso } from './paso'
import { soles, type Rendicion } from './modelo'

export default function PasoDocumento({ r, setR, recargar, avisar, soloLectura }: PropsPaso) {
  const [generando, setGenerando] = useState(false)
  const [clase, setClase] = useState<'boleto' | 'devolucion' | 'otro'>('boleto')
  const entrada = useRef<HTMLInputElement | null>(null)
  const subirAnexo = async (archivo: File | undefined) => {
    if (!archivo) return
    try {
      const datos = new FormData()
      datos.append('clase', clase)
      datos.append('archivo', archivo)
      await subirArchivo(`/api/rendiciones/${r.id}/anexos`, datos)
      await recargar()
      avisar('success', 'Sustento adjunto.')
    } catch (e) { avisar('error', e instanceof Error ? e.message : 'No se pudo adjuntar.') } finally { if (entrada.current) entrada.current.value = '' }
  }
  const quitarAnexo = async (id: number) => {
    try { await api(`/api/rendiciones/${r.id}/anexos/${id}`, { method: 'DELETE' }); await recargar() } catch (e) { avisar('error', e instanceof Error ? e.message : 'No se pudo quitar.') }
  }
  const generar = async () => {
    setGenerando(true)
    try {
      setR(await api<Rendicion>(`/api/rendiciones/${r.id}/documento`, { method: 'POST' }))
      avisar('success', 'Documento generado.')
    } catch (e) {
      avisar('error', e instanceof Error ? e.message : 'No se pudo generar.')
    } finally {
      setGenerando(false)
    }
  }
  const bajar = async (ruta: string, nombre: string) => {
    try { await descargarArchivo(ruta, nombre) } catch (e) { avisar('error', e instanceof Error ? e.message : 'No se pudo descargar.') }
  }
  const liq = r.liquidacion
  const generado = r.documento.generado_en ? new Date(r.documento.generado_en).toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' }) : ''
  const visor = r.documento.pdf ? (
    <VisorPdf ruta={`/api/rendiciones/${r.id}/documento.pdf`} version={r.documento.generado_en ?? ''} nombre={r.documento.nombre} alto="100%" />
  ) : (
    <Box sx={{ height: '100%', display: 'grid', placeItems: 'center', textAlign: 'center', color: 'text.secondary', p: 3 }}>
      <Box>
        <PictureAsPdfOutlinedIcon sx={{ fontSize: 44, color: PALETA.apagado }} />
        <Typography variant="body2">Genere los anexos para verlos aquí.</Typography>
      </Box>
    </Box>
  )
  return (
    // El documento a la DERECHA en escritorio (2026-10-18, Edison: «como las vistas previas de otros
    // módulos»; el editor de documentos): botones e información a la izquierda, el visor a toda la altura y
    // fijo al bajar. En el celular, el visor debajo, solo si ya hay PDF.
    <Box sx={{ display: { xs: 'block', md: 'grid' }, gridTemplateColumns: { md: 'minmax(320px, 400px) minmax(0, 1fr)' }, gap: 2, alignItems: 'start' }}>
    <Box sx={{ minWidth: 0 }}>
      <Seccion>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1 }}>
          <Button variant="contained" startIcon={<PictureAsPdfOutlinedIcon />} disabled={generando} onClick={() => void generar()}>
            {r.documento.pdf ? 'Volver a generar' : 'Generar los anexos'}
          </Button>
          {r.documento.pdf && (
            <Button variant="outlined" startIcon={<DownloadOutlinedIcon />} onClick={() => void bajar(`/api/rendiciones/${r.id}/documento.pdf`, r.documento.nombre)}>PDF</Button>
          )}
          <Button variant="outlined" startIcon={<TableChartOutlinedIcon />} onClick={() => void bajar(`/api/rendiciones/${r.id}/liquidacion.xlsx`, '')}>Excel</Button>
        </Box>
        {generando && <LinearProgress sx={{ mb: 1 }} />}
        <Typography variant="body2" color="text.secondary">
          Anexo 3 (declaración jurada): <b>{soles(liq.dj)}</b> — {liq.dj_en_letras}. Anexo 4: rendido {soles(liq.reconocido)}, saldo {soles(liq.saldo)}.
        </Typography>
        {generado && <Typography variant="caption" color="text.secondary">Generado: {generado}</Typography>}
        {r.errores > 0 && <Typography variant="caption" sx={{ display: 'block', color: PALETA.avisoOscuro }}>Hay {r.errores} control(es) por corregir: el documento sale igual, para revisar.</Typography>}
        {r.documento.pdf && !r.documento.al_dia && <Alert severity="warning" sx={{ mt: 1 }}>Hubo cambios después de generarlo: vuelva a generar antes de imprimir.</Alert>}
      </Seccion>
      <Seccion titulo="Otros sustentos">
        {!soloLectura && (
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 1 }}>
            <TextField select size="small" value={clase} onChange={(e) => setClase(e.target.value as typeof clase)} sx={{ minWidth: 150, flex: 1 }} inputProps={{ 'aria-label': 'Qué sustento' }}>
              <MenuItem value="boleto">Boleto aéreo</MenuItem>
              <MenuItem value="devolucion">Recibo de devolución</MenuItem>
              <MenuItem value="otro">Otro</MenuItem>
            </TextField>
            <Button size="small" variant="outlined" startIcon={<AttachFileIcon />} onClick={() => entrada.current?.click()}>Adjuntar</Button>
            <input ref={entrada} hidden type="file" accept="image/*,application/pdf" onChange={(e) => void subirAnexo(e.target.files?.[0])} />
          </Box>
        )}
        {r.anexos.length === 0 && <Typography variant="body2" color="text.secondary">Lo que acompaña y no se rinde: el boleto aéreo y, si devolvió saldo, su recibo.</Typography>}
        {r.anexos.map((a) => (
          <Box key={a.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.5, borderTop: '1px solid', borderColor: 'divider' }}>
            <Typography variant="body2" sx={{ flex: 1, minWidth: 0 }} noWrap>{a.descripcion}</Typography>
            <Button size="small" onClick={() => void bajar(`/api/rendiciones/${r.id}/anexos/${a.id}/archivo`, a.archivo.split('/').pop() ?? '')}>Ver</Button>
            {!soloLectura && <IconButton size="small" aria-label="Quitar el sustento" onClick={() => void quitarAnexo(a.id)}><DeleteOutlineIcon fontSize="small" /></IconButton>}
          </Box>
        ))}
      </Seccion>
    </Box>
      <Box sx={{ display: { xs: r.documento.pdf ? 'block' : 'none', md: 'block' }, position: { md: 'sticky' }, top: { md: 8 },
        height: { xs: '70dvh', md: 'calc(100dvh - 150px)' }, minHeight: { md: 520 }, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', borderRadius: 2, overflow: 'hidden' }}>
        {visor}
      </Box>
    </Box>
  )
}
