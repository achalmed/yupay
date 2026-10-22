/**
 * El AVANCE de una rendición (2026-10-18, pedido de Edison: «estados por sección: pendiente, registrado,
 * validado, y un avance visible»). Cuatro tramos de una barra —Datos, Comprobantes, Movilidad,
 * Documento—, cada uno con el color de su estado y lo que le falta en dos palabras; un toque lleva a la
 * sección. El estado lo decide el servidor (`servicios/rendicion.py::avance`). En el celular cabe en un
 * renglón: el rótulo y, debajo, el estado.
 */
import Box from '@mui/material/Box'
import ButtonBase from '@mui/material/ButtonBase'
import Typography from '@mui/material/Typography'
import { COLOR_SECCION, ETIQUETA_SECCION } from './estilo'
import type { Paso } from './paso'
import type { Avance as TAvance } from './modelo'

export default function Avance({ avance, actual, ir }: { avance: TAvance; actual?: Paso; ir?: (p: Paso) => void }) {
  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: `repeat(${avance.secciones.length}, 1fr)`, gap: 0.5, mb: 1.5 }} aria-label="Avance de la rendición">
      {avance.secciones.map((s) => (
        <ButtonBase key={s.clave} disabled={!ir} onClick={() => ir?.(s.clave)} title={s.texto}
          sx={{ display: 'block', textAlign: 'left', borderRadius: 1, px: 0.5, py: 0.25, minWidth: 0,
            bgcolor: actual === s.clave ? 'action.selected' : 'transparent' }}>
          <Box sx={{ height: 4, borderRadius: 2, bgcolor: COLOR_SECCION[s.estado], mb: 0.5, opacity: s.estado === 'pendiente' ? 0.45 : 1 }} />
          <Typography variant="caption" component="div" noWrap sx={{ fontWeight: 600, lineHeight: 1.2 }}>{s.etiqueta}</Typography>
          <Typography variant="caption" component="div" noWrap sx={{ color: COLOR_SECCION[s.estado], lineHeight: 1.2, fontSize: 11 }}>
            {s.estado === 'validado' ? ETIQUETA_SECCION.validado : s.texto}
          </Typography>
        </ButtonBase>
      ))}
    </Box>
  )
}
