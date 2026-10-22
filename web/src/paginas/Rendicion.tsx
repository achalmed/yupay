/**
 * UNA RENDICIÓN DE CUENTAS por pasos (2026-10-18): Datos → Comprobantes → Movilidad → Revisión →
 * Documento. Cada paso se monta una vez y se oculta (no se desmonta) para no perder lo que se escribe.
 * El cálculo, los controles y lo vinculado vigente (semana, memorando, cuenta) vienen del servidor
 * (`backend/app/api/rendiciones.py`); cada cambio devuelve la rendición entera recalculada.
 *
 * Arriba, el AVANCE por sección (pendiente · registrado · validado), que lleva a cada una.
 *
 * Modo ENCARGADO (2026-10-18, Edison: «un encargado hace las rendiciones de los dos, o cada uno hace la
 * suya»): si la comisión tiene otras rendiciones a su alcance, van en PESTAÑAS por persona (se pasa de una
 * a otra sin salir y sin perder el paso), y quien aún no tiene la suya aparece con «+» para crearla a su
 * nombre. La movilidad es compartida en los dos modos. La calculadora (hoja inferior) está siempre a mano.
 *
 * Consulta: `?ver=<paso>`. Un texto del chat (`state.textoPegar`) abre el pegado en Comprobantes.
 */
import { useCallback, useEffect, useState } from 'react'
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router'
import Box from '@mui/material/Box'
import Alert from '@mui/material/Alert'
import Snackbar from '@mui/material/Snackbar'
import LinearProgress from '@mui/material/LinearProgress'
import BadgeOutlinedIcon from '@mui/icons-material/BadgeOutlined'
import ReceiptOutlinedIcon from '@mui/icons-material/ReceiptOutlined'
import DirectionsBusOutlinedIcon from '@mui/icons-material/DirectionsBusOutlined'
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined'
import PictureAsPdfOutlinedIcon from '@mui/icons-material/PictureAsPdfOutlined'
import CalculateOutlinedIcon from '@mui/icons-material/CalculateOutlined'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import AddIcon from '@mui/icons-material/Add'
import Button from '@mui/material/Button'
import IconButton from '@mui/material/IconButton'
import Tab from '@mui/material/Tab'
import Tabs from '@mui/material/Tabs'
import Tooltip from '@mui/material/Tooltip'
import { api, ErrorApi } from '@qillqa/tiqsi'
import Calculadora from '../componentes/rendicion/Calculadora'
import { confirmar } from '@qillqa/tiqsi'
import { COLOR_ESTADO } from '../componentes/rendicion/estilo'
import { PALETA } from '@qillqa/tiqsi'
import { Marco, type OpcionPagina } from '@qillqa/tiqsi'
import PasoDatos from '../componentes/rendicion/PasoDatos'
import PasoComprobantes from '../componentes/rendicion/PasoComprobantes'
import PasoMovilidad from '../componentes/rendicion/PasoMovilidad'
import PasoRevision from '../componentes/rendicion/PasoRevision'
import PasoDocumento from '../componentes/rendicion/PasoDocumento'
import Avance from '../componentes/rendicion/Avance'
import InicioRendicion, { tocaInicio } from '../componentes/rendicion/InicioRendicion'
import type { PropsPaso, Paso } from '../componentes/rendicion/paso'
import type { Rendicion as TRendicion } from '../componentes/rendicion/modelo'

const PASOS: Paso[] = ['datos', 'comprobantes', 'movilidad', 'revision', 'documento']

export default function Rendicion() {
  const { id } = useParams()
  const [consulta, setConsulta] = useSearchParams()
  const paso: Paso = (PASOS as string[]).includes(consulta.get('ver') ?? '') ? (consulta.get('ver') as Paso) : 'comprobantes'
  const [r, setR] = useState<TRendicion | null>(null)
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState<{ tipo: 'success' | 'error' | 'info'; texto: string } | null>(null)
  const [vistos, setVistos] = useState<Set<Paso>>(new Set([paso]))
  const [textoPegar, setTextoPegar] = useState('')
  const [calc, setCalc] = useState(false)
  const [inicio, setInicio] = useState(false)
  const ubicacion = useLocation()
  const navegar = useNavigate()

  useEffect(() => {
    const t = (ubicacion.state as { textoPegar?: string } | null)?.textoPegar
    if (!t) return
    setTextoPegar(t)
    navegar(`${ubicacion.pathname}?ver=comprobantes`, { replace: true, state: null })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ubicacion.state])

  useEffect(() => { setR(null); setError('') }, [id])
  const recargar = useCallback(async () => {
    try {
      setR(await api<TRendicion>(`/api/rendiciones/${id}`))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo leer la rendición.')
    }
  }, [id])
  useEffect(() => { void recargar() }, [recargar])
  useEffect(() => setVistos((v) => new Set(v).add(paso)), [paso])

  const ir = useCallback((p: Paso) => setConsulta({ ver: p }, { replace: true }), [setConsulta])
  const avisar = useCallback((tipo: 'success' | 'error' | 'info', texto: string) => setAviso({ tipo, texto }), [])

  const etiquetas: [Paso, string, React.ReactNode, number?][] = [
    ['datos', 'Datos', <BadgeOutlinedIcon key="d" />],
    ['comprobantes', 'Comprobantes', <ReceiptOutlinedIcon key="c" />, r?.comprobantes.length],
    ['movilidad', 'Movilidad', <DirectionsBusOutlinedIcon key="m" />],
    ['revision', 'Revisión', <FactCheckOutlinedIcon key="r" />, r?.errores],
    ['documento', 'Documento', <PictureAsPdfOutlinedIcon key="p" />],
  ]
  const eliminar = async () => {
    if (!r) return
    const si = await confirmar(`¿Eliminar ${r.codigo} de ${r.comisionado.nombre}? Sus comprobantes y tramos propios se retiran; la movilidad de la comisión queda.`, { aceptar: 'Eliminar', peligro: true })
    if (!si) return
    try {
      await api(`/api/rendiciones/${r.id}`, { method: 'DELETE' })
      navegar('/rendiciones', { replace: true })
    } catch (e) {
      avisar('error', e instanceof Error ? e.message : 'No se pudo eliminar.')
    }
  }
  const opciones: OpcionPagina[] = etiquetas.map(([clave, etiqueta, icono, contador]) => ({
    clave, etiqueta, icono, contador, activa: paso === clave, alPulsar: () => ir(clave),
  }))
  // Presentada o cerrada: solo lectura para el comisionado (Administración puede observarla).
  const soloLectura = Boolean(r && ['presentada', 'cerrada'].includes(r.estado) && !r.puede_administrar)
  // «Antes de empezar»: la primera vez que se abre cada rendición en borrador (2026-10-18).
  const idInicio = r?.id
  useEffect(() => {
    if (r) setInicio(tocaInicio(r, soloLectura))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idInicio])
  const titulo = r ? `${r.codigo} · ${r.semana?.codigo ?? 'Comisión'}` : 'Rendición'

  // Pestañas por persona de la comisión (modo encargado) y quienes aún no tienen la suya.
  const miembros = r?.comision.miembros ?? []
  const faltan = (r?.comision.faltan ?? []).filter((f) => f.usuario_id)
  const conPestanas = Boolean(r) && (miembros.filter((m) => m.accesible).length > 1 || (faltan.length > 0 && !soloLectura))
  const crearPara = async (usuario: number) => {
    if (!r?.semana) return
    try {
      const n = await api<{ id: number }>('/api/rendiciones', { method: 'POST', body: JSON.stringify({ semana_id: r.semana.id, usuario_id: usuario }) })
      navegar(`/rendiciones/${n.id}?ver=${paso}`)
      avisar('success', 'Rendición creada; la movilidad de la comisión ya está en ella.')
    } catch (e) {
      const d = e instanceof ErrorApi ? (e.detalle as { codigo?: string; id?: number } | undefined) : undefined
      if (d?.codigo === 'ya_existe' && d.id) navegar(`/rendiciones/${d.id}?ver=${paso}`)
      else avisar('error', e instanceof Error ? e.message : 'No se pudo crear.')
    }
  }

  return (
    <Marco modulo="rendicion" titulo={titulo} volver="/rendiciones" opciones={opciones} fondo={PALETA.fondo}>
      {/* Revisión (la comparación) y Documento (el visor a la derecha) usan más ancho en escritorio. */}
      <Box sx={{ px: { xs: 1.5, sm: 2.5 }, py: { xs: 1.5, sm: 2.5 }, maxWidth: paso === 'documento' || paso === 'revision' ? 1400 : 1100, width: '100%', mx: 'auto' }}>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {!r && !error && <LinearProgress />}
        {r && conPestanas && (
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
            <Tabs value={r.id} variant="scrollable" scrollButtons={false} sx={{ flex: 1, minWidth: 0 }}
              onChange={(_, v: number) => navegar(`/rendiciones/${v}?ver=${paso}`)}>
              {miembros.map((m) => (
                <Tab key={m.id} value={m.id} disabled={!m.accesible}
                  label={
                    <Tooltip title={m.accesible ? `${m.codigo} · ${m.etiqueta_estado}` : 'La hace esa persona'}>
                      <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75 }}>
                        <Box component="span" sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: COLOR_ESTADO[m.estado] }} />
                        {m.comisionado}
                      </Box>
                    </Tooltip>
                  } />
              ))}
            </Tabs>
            {!soloLectura && faltan.map((f) => (
              <Tooltip key={f.nombre} title={`Crear la rendición de ${f.nombre} (usted la hace como encargado)`}>
                <Button size="small" startIcon={<AddIcon fontSize="small" />} onClick={() => void crearPara(f.usuario_id!)} sx={{ flexShrink: 0 }}>
                  {f.nombre.split(' ')[0]}
                </Button>
              </Tooltip>
            ))}
          </Box>
        )}
        {r?.estado === 'observada' && r.observacion && <Alert severity="warning" sx={{ mb: 1.5 }}>Observada: {r.observacion}. Subsánela en 72 horas (DI 37-2025-DF-DGA-CR, 7.9.3.2.2).</Alert>}
        {soloLectura && <Alert severity="info" sx={{ mb: 1.5 }}>Presentada: para corregirla, Administración debe observarla.</Alert>}
        {r && (
          <Box sx={{ mb: 0.75, px: 0.5, fontSize: 13, color: 'text.secondary', display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              De <Box component="b" sx={{ color: 'text.primary' }}>{r.comisionado.nombre}</Box>{r.comisionado.cargo ? ` · ${r.comisionado.cargo}` : ''}
              {r.creado_por && <> · la hace {r.creado_por}</>}
            </Box>
            <Tooltip title="Calculadora">
              <IconButton size="small" aria-label="Calculadora" onClick={() => setCalc(true)}><CalculateOutlinedIcon fontSize="small" /></IconButton>
            </Tooltip>
            {/* Eliminar (2026-10-18, Edison: «la abrí para probar y no sé cómo borrarla»): solo un borrador,
                o Administración; la API retira la fila y deja sus archivos en la carpeta. */}
            {(r.estado === 'borrador' || r.puede_administrar) && (
              <Tooltip title="Eliminar esta rendición">
                <IconButton size="small" aria-label="Eliminar esta rendición" onClick={() => void eliminar()}><DeleteOutlineIcon fontSize="small" /></IconButton>
              </Tooltip>
            )}
          </Box>
        )}
        {r?.avance && <Avance avance={r.avance} actual={paso} ir={ir} />}
        {r && PASOS.filter((p) => vistos.has(p)).map((p) => {
          const props: PropsPaso = { r, setR, recargar, avisar, ir, soloLectura }
          return (
            <Box key={p} sx={{ display: p === paso ? 'block' : 'none' }}>
              {p === 'datos' && <PasoDatos {...props} />}
              {p === 'comprobantes' && <PasoComprobantes {...props} textoPegar={textoPegar} alConsumirPegar={() => setTextoPegar('')} />}
              {p === 'movilidad' && <PasoMovilidad {...props} />}
              {p === 'revision' && <PasoRevision {...props} />}
              {p === 'documento' && <PasoDocumento {...props} />}
            </Box>
          )
        })}
      </Box>
      <Calculadora abierta={calc} alCerrar={() => setCalc(false)} />
      {r && <InicioRendicion r={r} abierta={inicio} alCerrar={() => setInicio(false)}
        alGuardado={(nueva) => { setR(nueva); setInicio(false); avisar('success', 'Listo: ahora registre sus comprobantes.'); ir('comprobantes') }} />}
      <Snackbar open={aviso !== null} autoHideDuration={4500} onClose={() => setAviso(null)} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        {aviso ? <Alert severity={aviso.tipo} variant="filled" onClose={() => setAviso(null)} sx={{ maxWidth: 'calc(100vw - 32px)' }}>{aviso.texto}</Alert> : undefined}
      </Snackbar>
    </Marco>
  )
}
