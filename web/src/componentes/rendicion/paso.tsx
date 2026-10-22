/**
 * Lo común de los pasos de una rendición (2026-10-18): sus props, la tarjeta de sección, el botón
 * «Siguiente» y la imagen autenticada de un comprobante.
 */
import { useEffect, useState, type ReactNode } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Typography from '@mui/material/Typography'
import ArrowForwardIcon from '@mui/icons-material/ArrowForward'
import { descargarBlob } from '@qillqa/tiqsi'
import type { Rendicion } from './modelo'

export type Paso = 'datos' | 'comprobantes' | 'movilidad' | 'revision' | 'documento'
export interface PropsPaso {
  r: Rendicion
  setR: (r: Rendicion) => void
  recargar: () => Promise<void>
  avisar: (tipo: 'success' | 'error' | 'info', texto: string) => void
  ir: (p: Paso) => void
  soloLectura: boolean
}

/** Una sección del paso: papel con borde, título breve y, a la derecha, sus acciones. */
export function Seccion({ titulo, acciones, children, sx }: { titulo?: ReactNode; acciones?: ReactNode; children: ReactNode; sx?: object }) {
  return (
    <Box sx={{ bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', borderRadius: 2, p: { xs: 1.5, sm: 2 }, mb: 1.5, ...sx }}>
      {(titulo || acciones) && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.25, flexWrap: 'wrap' }}>
          {titulo && <Typography sx={{ fontWeight: 650, fontSize: 15, flex: 1, minWidth: 0 }}>{titulo}</Typography>}
          {acciones}
        </Box>
      )}
      {children}
    </Box>
  )
}

export function Siguiente({ ir, a, texto }: { ir: (p: Paso) => void; a: Paso; texto: string }) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 1 }}>
      <Button variant="outlined" endIcon={<ArrowForwardIcon />} onClick={() => { ir(a); window.scrollTo({ top: 0 }) }}>{texto}</Button>
    </Box>
  )
}

/** La foto de un comprobante (con sesión): URL local del blob, liberada al desmontar. */
export function useImagen(ruta: string | null): string {
  const [url, setUrl] = useState('')
  useEffect(() => {
    if (!ruta) { setUrl(''); return }
    let vivo = true
    let creada = ''
    descargarBlob(ruta).then((b) => {
      if (!vivo) return
      creada = URL.createObjectURL(b)
      setUrl(creada)
    }).catch(() => setUrl(''))
    return () => { vivo = false; if (creada) URL.revokeObjectURL(creada) }
  }, [ruta])
  return url
}

/** Un dato con su rótulo, en dos renglones (fichas del celular). */
export function Dato({ rotulo, children, fuerte }: { rotulo: string; children: ReactNode; fuerte?: boolean }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary" component="div" sx={{ lineHeight: 1.2 }}>{rotulo}</Typography>
      <Typography variant="body2" sx={{ fontWeight: fuerte ? 700 : 500, wordBreak: 'break-word' }}>{children}</Typography>
    </Box>
  )
}
