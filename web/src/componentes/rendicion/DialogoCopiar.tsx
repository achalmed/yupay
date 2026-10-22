/**
 * Copiar de un compañero de la MISMA comisión (2026-10-18): los otros gastos sin comprobante, los importes y
 * topes ajustados, el lugar de la firma y el memorando (si aún no tiene). La movilidad ya no se copia: es
 * de la comisión y la ven todos (`servicios/rendicion_comision.py`); los comprobantes tampoco (cada quien
 * rinde los suyos). El servidor solo deja copiar de la misma comisión (`POST /api/rendiciones/{id}/copiar`).
 */
import { useEffect, useState } from 'react'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import Button from '@mui/material/Button'
import Checkbox from '@mui/material/Checkbox'
import FormControlLabel from '@mui/material/FormControlLabel'
import MenuItem from '@mui/material/MenuItem'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import LinearProgress from '@mui/material/LinearProgress'
import { api } from '@qillqa/tiqsi'
import type { Companero, Rendicion } from './modelo'

export default function DialogoCopiar({ r, abierto, alCerrar, alCopiar }: {
  r: Rendicion
  abierto: boolean
  alCerrar: () => void
  alCopiar: (nueva: Rendicion, texto: string) => void
}) {
  const [lista, setLista] = useState<Companero[] | null>(null)
  const [desde, setDesde] = useState<number | ''>('')
  const [que, setQue] = useState({ otros: true, parametros: true, lugar_firma: true, memorando: true })
  const [error, setError] = useState('')
  const [ocupado, setOcupado] = useState(false)

  useEffect(() => {
    if (!abierto) return
    setLista(null)
    setError('')
    api<Companero[]>(`/api/rendiciones/${r.id}/companeros`).then((l) => {
      setLista(l)
      setDesde(l[0]?.id ?? '')
    }).catch((e) => { setLista([]); setError(e instanceof Error ? e.message : 'No se pudo leer.') })
  }, [abierto, r.id])

  const elegido = lista?.find((c) => c.id === desde)
  const copiar = async () => {
    if (!desde) return
    setOcupado(true)
    try {
      const res = await api<{ copiados: number; rendicion: Rendicion }>(`/api/rendiciones/${r.id}/copiar`, {
        method: 'POST', body: JSON.stringify({ desde, ...que, memorando: que.memorando && Boolean(elegido?.memorando) && !r.memorando, reemplazar: true }),
      })
      alCopiar(res.rendicion, `Copiado de ${elegido?.comisionado ?? 'su compañero'}${res.copiados ? `: ${res.copiados} gasto(s)` : ''}.`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo copiar.')
    } finally {
      setOcupado(false)
    }
  }
  const marca = (k: keyof typeof que, texto: string, n?: number) => (
    <FormControlLabel control={<Checkbox checked={que[k]} onChange={(e) => setQue({ ...que, [k]: e.target.checked })} />}
      label={<Typography variant="body2">{texto}{n !== undefined ? ` (${n})` : ''}</Typography>} />
  )
  return (
    <Dialog open={abierto} onClose={alCerrar} fullWidth maxWidth="xs">
      <DialogTitle>Copiar de un compañero</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 1, pt: '8px !important' }}>
        {lista === null && <LinearProgress />}
        {lista?.length === 0 && !error && <Typography variant="body2" color="text.secondary">Nadie más rindió esta comisión todavía.</Typography>}
        {lista && lista.length > 0 && (
          <>
            <TextField select size="small" label="De" value={desde} onChange={(e) => setDesde(Number(e.target.value))}>
              {lista.map((c) => <MenuItem key={c.id} value={c.id}>{c.comisionado} · {c.codigo}</MenuItem>)}
            </TextField>
            {marca('otros', 'Otros gastos sin comprobante', elegido?.otros)}
            {marca('parametros', 'Importes y topes ajustados', elegido?.parametros)}
            {marca('lugar_firma', 'Lugar de la firma')}
            {elegido?.memorando && !r.memorando && marca('memorando', 'El mismo memorando de viáticos')}
            <Typography variant="caption" color="text.secondary">Reemplaza lo suyo de esas partes. La movilidad ya es compartida; los comprobantes no se copian.</Typography>
          </>
        )}
        {error && <Typography variant="body2" color="error">{error}</Typography>}
      </DialogContent>
      <DialogActions>
        <Button onClick={alCerrar}>Cancelar</Button>
        <Button variant="contained" disabled={!desde || ocupado || !Object.values(que).some(Boolean)} onClick={() => void copiar()}>Copiar</Button>
      </DialogActions>
    </Dialog>
  )
}
