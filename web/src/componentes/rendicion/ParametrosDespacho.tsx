/**
 * Parámetros del despacho para la rendición (2026-10-18; Administración). En lenguaje simple (Edison: «hoy
 * son difíciles de entender»): cada uno con lo que significa en una línea, su norma y el valor que rige;
 * vacío = el de fábrica. A nombre de quién van los comprobantes (y su RUC) es un dato del despacho: la
 * directiva dice «Congreso de la República» y en 2026 salen con el RUC de la Cámara. Lo raro —de dónde sale
 * cada valor, para cambiarlo— va en «Ver más». Cada rendición puede ajustar los suyos en su paso «Datos».
 */
import { useEffect, useState } from 'react'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Collapse from '@mui/material/Collapse'
import InputAdornment from '@mui/material/InputAdornment'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import Alert from '@mui/material/Alert'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import { api } from '@qillqa/tiqsi'
import { ejemploMovilidad, type Parametro } from './modelo'

const EDITABLES: { k: string; prefijo?: string; sufijo?: string }[] = [
  { k: 'tope_diario', prefijo: 'S/', sufijo: 'por día' },
  { k: 'pct_dj', sufijo: '% de lo recibido' },
  { k: 'plazo_dias_habiles', sufijo: 'días hábiles' },
]
interface Institucion { a_nombre_de: string; ruc_a_nombre: string }

export default function ParametrosDespacho({ abierto, alCerrar, alGuardar }: { abierto: boolean; alCerrar: () => void; alGuardar: () => void }) {
  const [vigentes, setVigentes] = useState<Record<string, Parametro> | null>(null)
  const [valores, setValores] = useState<Record<string, string>>({})
  const [fuentes, setFuentes] = useState<Record<string, string>>({})
  const [inst, setInst] = useState<Institucion>({ a_nombre_de: '', ruc_a_nombre: '' })
  const [verMas, setVerMas] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!abierto) return
    setError('')
    api<{ parametros: Record<string, Parametro>; institucion: Institucion }>('/api/rendiciones/parametros').then((r) => {
      setVigentes(r.parametros)
      setValores(Object.fromEntries(EDITABLES.map(({ k }) => [k, r.parametros[k].origen === 'despacho' ? String(r.parametros[k].valor ?? '') : ''])))
      setFuentes(Object.fromEntries(EDITABLES.map(({ k }) => [k, r.parametros[k].origen === 'despacho' ? r.parametros[k].fuente : ''])))
      setInst(r.institucion)
    }).catch((e) => setError(e instanceof Error ? e.message : 'No se pudo leer.'))
  }, [abierto])

  const guardar = async () => {
    try {
      await api('/api/rendiciones/parametros', {
        method: 'PUT',
        body: JSON.stringify({ valores: Object.fromEntries(EDITABLES.map(({ k }) => [k, valores[k] || null])), fuentes, textos: inst }),
      })
      alGuardar()
      alCerrar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar.')
    }
  }
  const tope = Number(valores.tope_diario || vigentes?.tope_diario.valor || 0)
  const pct = Number(valores.pct_dj || vigentes?.pct_dj.valor || 0)

  return (
    <Dialog open={abierto} onClose={alCerrar} fullWidth maxWidth="sm">
      <DialogTitle>Parámetros del despacho</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '8px !important' }}>
        {error && <Alert severity="error">{error}</Alert>}
        {vigentes && EDITABLES.map(({ k, prefijo, sufijo }) => (
          <Box key={k}>
            <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, flexWrap: 'wrap' }}>
              <Typography variant="body2" sx={{ fontWeight: 650 }}>{vigentes[k].etiqueta}</Typography>
              <Typography variant="caption" color="text.secondary">{vigentes[k].norma}</Typography>
            </Box>
            <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 0.75 }}>{vigentes[k].simple}</Typography>
            <TextField
              value={valores[k] ?? ''} onChange={(e) => setValores({ ...valores, [k]: e.target.value })} size="small" sx={{ width: { xs: '100%', sm: 260 } }}
              placeholder={vigentes[k].origen === 'fabrica' ? String(vigentes[k].valor ?? '') : ''} inputProps={{ inputMode: 'decimal', 'aria-label': vigentes[k].etiqueta }}
              InputProps={{
                startAdornment: prefijo ? <InputAdornment position="start">{prefijo}</InputAdornment> : undefined,
                endAdornment: sufijo ? <InputAdornment position="end">{sufijo}</InputAdornment> : undefined,
              }}
              helperText={valores[k] ? 'Del despacho' : 'Vacío: rige el de fábrica'}
            />
          </Box>
        ))}
        {vigentes && (
          <Typography variant="caption" color="text.secondary">
            Con esto, la movilidad de un día llega hasta S/ {Math.round(tope * pct) / 100}. {ejemploMovilidad(tope, Math.round(tope * pct) / 100)}
          </Typography>
        )}
        <Box>
          <Typography variant="body2" sx={{ fontWeight: 650 }}>A nombre de quién van los comprobantes</Typography>
          <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 0.75 }}>Lo que debe decir la factura o boleta (DI 37-2025-DF-DGA-CR). Sale en la ayuda del comprobante.</Typography>
          <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr', sm: '1.6fr 1fr' } }}>
            <TextField size="small" label="Razón social" value={inst.a_nombre_de} onChange={(e) => setInst({ ...inst, a_nombre_de: e.target.value })} />
            <TextField size="small" label="RUC" value={inst.ruc_a_nombre} onChange={(e) => setInst({ ...inst, ruc_a_nombre: e.target.value.replace(/\D/g, '').slice(0, 11) })}
              inputProps={{ inputMode: 'numeric' }} helperText="11 dígitos" />
          </Box>
        </Box>
        <Button size="small" endIcon={<ExpandMoreIcon sx={{ transform: verMas ? 'rotate(180deg)' : 'none', transition: '.2s' }} />} onClick={() => setVerMas(!verMas)} sx={{ alignSelf: 'flex-start', px: 0.5 }}>
          {verMas ? 'Ver menos' : 'Ver más: de dónde sale cada valor'}
        </Button>
        <Collapse in={verMas} unmountOnExit>
          {vigentes && EDITABLES.map(({ k }) => (
            <Box key={k} sx={{ mb: 1.5 }}>
              <Typography variant="caption" color="text.secondary" component="div">{vigentes[k].etiqueta} — de fábrica: {vigentes[k].origen === 'fabrica' ? vigentes[k].fuente : '(ver la norma)'}</Typography>
              <TextField label="De dónde sale (si lo cambia)" value={fuentes[k] ?? ''} onChange={(e) => setFuentes({ ...fuentes, [k]: e.target.value })}
                fullWidth size="small" variant="standard" />
            </Box>
          ))}
        </Collapse>
      </DialogContent>
      <DialogActions>
        <Button onClick={alCerrar}>Cancelar</Button>
        <Button variant="contained" onClick={() => void guardar()}>Guardar</Button>
      </DialogActions>
    </Dialog>
  )
}
