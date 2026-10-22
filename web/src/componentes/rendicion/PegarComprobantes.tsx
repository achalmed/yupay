/**
 * Pegar el resultado del prompt de comprobantes (2026-10-18; formato `comprobantes-gasto`, prompt 19 de
 * `06 legislativo`). La IA lee las fotos de las boletas y facturas; aquí se pega su respuesta, el sistema
 * dice de cada comprobante si es nuevo, repetido o de fuera de la comisión, y se agregan los marcados.
 * Si hay fotos subidas sin datos, se llenan primero, en el mismo orden.
 */
import { useEffect, useState } from 'react'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Checkbox from '@mui/material/Checkbox'
import Chip from '@mui/material/Chip'
import LinearProgress from '@mui/material/LinearProgress'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import { api } from '@qillqa/tiqsi'
import { PALETA } from '@qillqa/tiqsi'
import { mensajePegado } from './apoyo'
import { conceptoDe, diaCorto, numeroCorto, soles, type Rendicion } from './modelo'

interface Leido {
  n: number
  estado: 'nuevo' | 'repetido' | 'fuera' | 'dudoso'
  motivo: string
  datos: Record<string, string | number | boolean> & { documento: string; importe: number; fecha: string; concepto: string }
}
interface Lectura { comprobantes: Leido[]; tramos: Record<string, unknown>[]; fotos_sin_datos: number; lectura: { avisos: string[] } }

const ROTULO = { nuevo: 'nuevo', repetido: 'repetido', fuera: 'fuera de fecha', dudoso: 'revisar' } as const
const COLOR = { nuevo: PALETA.exito, repetido: PALETA.error, fuera: PALETA.error, dudoso: PALETA.aviso } as const

export default function PegarComprobantes({ r, abierto, textoInicial, alCerrar, alAplicar }: {
  r: Rendicion
  abierto: boolean
  textoInicial?: string
  alCerrar: () => void
  alAplicar: (nueva: Rendicion, texto: string) => void
}) {
  const [texto, setTexto] = useState('')
  const [lectura, setLectura] = useState<Lectura | null>(null)
  const [marcados, setMarcados] = useState<Set<number>>(new Set())
  const [conTramos, setConTramos] = useState(true)
  const [error, setError] = useState('')
  const [ocupado, setOcupado] = useState(false)

  const leer = async (t: string) => {
    setOcupado(true)
    setError('')
    try {
      const l = await api<Lectura>(`/api/rendiciones/${r.id}/pegar`, { method: 'POST', body: JSON.stringify({ texto: t }) })
      setLectura(l)
      setMarcados(new Set(l.comprobantes.filter((c) => c.estado === 'nuevo' || c.estado === 'dudoso').map((c) => c.n)))
    } catch (e) {
      setLectura(null)
      setError(mensajePegado(e))
    } finally {
      setOcupado(false)
    }
  }
  useEffect(() => {
    if (!abierto) return
    setLectura(null)
    setError('')
    setTexto(textoInicial ?? '')
    if (textoInicial) void leer(textoInicial)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [abierto, textoInicial])

  const agregar = async () => {
    if (!lectura) return
    setOcupado(true)
    try {
      const comprobantes = lectura.comprobantes.filter((c) => marcados.has(c.n)).map(({ datos }) => ({
        fecha: datos.fecha, tipo: datos.tipo ?? 'boleta_electronica', serie: datos.serie ?? '', numero: String(datos.numero ?? ''),
        ruc: datos.ruc ?? '', proveedor: datos.proveedor ?? '', concepto: datos.concepto, importe: datos.importe, nota: datos.detalle ?? '',
      }))
      const tramos = conTramos ? lectura.tramos : []
      const res = await api<{ rendicion: Rendicion; agregados: number }>(`/api/rendiciones/${r.id}/lote`, {
        method: 'POST', body: JSON.stringify({ comprobantes, tramos, emparejar: true, texto }),
      })
      alAplicar(res.rendicion, `${res.agregados} comprobante(s) agregados${tramos.length ? ` y ${tramos.length} tramo(s)` : ''}.`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo agregar.')
    } finally {
      setOcupado(false)
    }
  }

  return (
    <Dialog open={abierto} onClose={alCerrar} fullWidth maxWidth="sm">
      <DialogTitle>Pegar lo que leyó la IA</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, pt: '8px !important' }}>
        {!lectura && (
          <TextField multiline minRows={6} maxRows={14} fullWidth value={texto} onChange={(e) => setTexto(e.target.value)}
            placeholder="Pegue aquí la respuesta completa de la IA (el bloque que empieza con «tipo: comprobantes-gasto»)." />
        )}
        {ocupado && <LinearProgress />}
        {error && <Alert severity="error">{error}</Alert>}
        {lectura && (
          <>
            {lectura.fotos_sin_datos > 0 && <Alert severity="info" sx={{ py: 0 }}>Se llenarán primero las {lectura.fotos_sin_datos} foto(s) subidas sin datos, en orden.</Alert>}
            {lectura.lectura.avisos.slice(0, 3).map((a) => <Alert key={a} severity="warning" sx={{ py: 0 }}>{a}</Alert>)}
            {lectura.comprobantes.map((c) => (
              <Box key={c.n} onClick={() => { const s = new Set(marcados); if (s.has(c.n)) s.delete(c.n); else s.add(c.n); setMarcados(s) }}
                sx={{ display: 'flex', gap: 1, alignItems: 'flex-start', p: 1, borderRadius: 1.5, border: '1px solid', borderColor: marcados.has(c.n) ? 'primary.main' : 'divider', cursor: 'pointer' }}>
                <Checkbox size="small" checked={marcados.has(c.n)} sx={{ p: 0.25 }} />
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'baseline' }}>
                    <Typography variant="body2" sx={{ fontWeight: 600, flex: 1, minWidth: 0 }} noWrap>{numeroCorto({ tipo: String(c.datos.tipo ?? ''), serie: String(c.datos.serie ?? ''), numero: String(c.datos.numero ?? '') })}</Typography>
                    <Typography variant="body2" sx={{ fontWeight: 700 }}>{soles(c.datos.importe)}</Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary" component="div">
                    {diaCorto(c.datos.fecha)} · {conceptoDe(c.datos.concepto)}{c.datos.proveedor ? ` · ${c.datos.proveedor}` : ''}
                  </Typography>
                  {c.estado !== 'nuevo' && (
                    <Box sx={{ display: 'flex', gap: 0.75, alignItems: 'center', mt: 0.25 }}>
                      <Chip size="small" variant="outlined" label={ROTULO[c.estado]} sx={{ height: 20, color: COLOR[c.estado], borderColor: COLOR[c.estado] }} />
                      <Typography variant="caption" color="text.secondary">{c.motivo}</Typography>
                    </Box>
                  )}
                </Box>
              </Box>
            ))}
            {lectura.tramos.length > 0 && (
              <Box onClick={() => setConTramos(!conTramos)} sx={{ display: 'flex', alignItems: 'center', gap: 1, cursor: 'pointer' }}>
                <Checkbox size="small" checked={conTramos} sx={{ p: 0.25 }} />
                <Typography variant="body2">Agregar también {lectura.tramos.length} tramo(s) de movilidad</Typography>
              </Box>
            )}
          </>
        )}
      </DialogContent>
      <DialogActions>
        {lectura && <Button onClick={() => setLectura(null)}>Volver a pegar</Button>}
        <Box sx={{ flex: 1 }} />
        <Button onClick={alCerrar}>Cancelar</Button>
        {lectura
          ? <Button variant="contained" disabled={ocupado || marcados.size === 0} onClick={() => void agregar()}>Agregar {marcados.size}</Button>
          : <Button variant="contained" disabled={ocupado || !texto.trim()} onClick={() => void leer(texto)}>Leer</Button>}
      </DialogActions>
    </Dialog>
  )
}
