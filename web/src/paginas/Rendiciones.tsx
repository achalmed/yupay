/**
 * RENDICIÓN DE CUENTAS — la lista (2026-10-18; backend/app/api/rendiciones.py, `docs/arquitectura.md` §32).
 *
 * Cada quien ve sus rendiciones; el administrador puede ver todas, el resumen del despacho y los
 * parámetros. Celular primero: una tarjeta por COMISIÓN (2026-10-18: «la lista parece duplicada») con su
 * semana, fechas, avance, plazo y estado común, y dentro una fila por comisionado —con su nombre siempre,
 * también el propio— con lo rendido, el saldo, su avance y lo que falta. El plazo no se muestra en una
 * rendición presentada, observada o cerrada.
 *
 * Consulta: `?nueva=1` abre el alta; `?semana=<id>` (desde la Semana de representación) abre la suya o el
 * alta con esa semana; `?ver=todas|resumen`; `?parametros=1` (administrador); `?pegar=<id de mensaje>`
 * (chat) lleva el resultado del prompt a la rendición abierta.
 */
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import ButtonBase from '@mui/material/ButtonBase'
import Chip from '@mui/material/Chip'
import Typography from '@mui/material/Typography'
import LinearProgress from '@mui/material/LinearProgress'
import Alert from '@mui/material/Alert'
import Snackbar from '@mui/material/Snackbar'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import ReceiptLongOutlinedIcon from '@mui/icons-material/ReceiptLongOutlined'
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline'
import TuneOutlinedIcon from '@mui/icons-material/TuneOutlined'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import { api, ErrorApi } from '@qillqa/tiqsi'
import { PALETA } from '@qillqa/tiqsi'
import { hoyIso } from '../componentes/rendicion/apoyo'
import { textoDeMensaje } from '../componentes/rendicion/apoyo'
import { Marco } from '@qillqa/tiqsi'
import { BarraModulo } from '@qillqa/tiqsi'
import { BotonAyuda } from '@qillqa/tiqsi'
import NuevaRendicion from '../componentes/rendicion/NuevaRendicion'
import ResumenDespacho from '../componentes/rendicion/ResumenDespacho'
import ParametrosDespacho from '../componentes/rendicion/ParametrosDespacho'
import { COLOR_ESTADO } from '../componentes/rendicion/estilo'
import { agruparPorComision, diaCorto, ESTADOS, soles, textoAvance, textoAvanceComision, textoPlazo, type FilaLista, type GrupoComision } from '../componentes/rendicion/modelo'

type Aviso = { tipo: 'success' | 'error' | 'info'; texto: string }

/**
 * Una COMISIÓN (2026-10-18, Edison: «la lista parece duplicada: dos tarjetas de la SR-02»): la cabecera con la
 * semana, las fechas, el avance y el estado común; dentro, una fila por comisionado con su nombre (siempre,
 * también el propio), lo rendido, el saldo, su avance y lo pendiente. Celular primero: dos renglones por fila.
 */
function TarjetaComision({ g, hoy, alAbrir }: { g: GrupoComision; hoy: string; alAbrir: (id: number) => void }) {
  const plazo = g.limite ? textoPlazo(g.limite, hoy, 'borrador') : ''
  const vencida = Boolean(g.limite && hoy > g.limite)
  const titulo = g.semana ? `${g.semana.codigo} · ${g.semana.tema}` : `Comisión de servicio${g.lugar ? ` · ${g.lugar}` : ''}`
  return (
    <Box sx={{ borderRadius: 2, border: '1px solid', borderColor: 'divider', bgcolor: 'background.paper', overflow: 'hidden' }}>
      <Box sx={{ px: 1.5, pt: 1.25, pb: 1, bgcolor: PALETA.superficieTenue, borderBottom: '1px solid', borderColor: 'divider' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {g.estadoComun && <Chip size="small" label={ESTADOS[g.estadoComun]} sx={{ height: 22, bgcolor: `${COLOR_ESTADO[g.estadoComun]}1A`, color: COLOR_ESTADO[g.estadoComun], fontWeight: 600 }} />}
          <Typography variant="body2" sx={{ fontWeight: 650, flex: 1, minWidth: 0 }} noWrap title={titulo}>{titulo}</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0 }}>{g.filas.length === 1 ? '1 persona' : `${g.filas.length} personas`}</Typography>
        </Box>
        <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.25 }}>
          {g.inicio ? `${diaCorto(g.inicio)} al ${diaCorto(g.fin)}` : 'Sin fechas'}{g.semana && g.lugar ? ` · ${g.lugar}` : ''}
        </Typography>
        {(g.avance.total > 0 || plazo) && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.75, flexWrap: 'wrap' }}>
            {g.avance.total > 0 && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1, minWidth: 140 }}>
                <LinearProgress variant="determinate" value={g.avance.fraccion * 100} sx={{ flex: 1, height: 5, borderRadius: 3, bgcolor: PALETA.superficieMedia, '& .MuiLinearProgress-bar': { bgcolor: PALETA.exito } }} />
                <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0 }}>{textoAvanceComision(g.avance)}</Typography>
              </Box>
            )}
            {plazo && <Chip size="small" variant="outlined" label={plazo} sx={{ height: 22, ...(vencida ? { color: PALETA.error, borderColor: PALETA.error } : {}) }} />}
          </Box>
        )}
      </Box>
      {g.filas.map((r, i) => {
        const av = textoAvance(r.avance)
        return (
          <ButtonBase key={r.id} onClick={() => alAbrir(r.id)}
            sx={{ display: 'block', width: '100%', textAlign: 'left', px: 1.5, py: 1, borderTop: i ? '1px solid' : 'none', borderColor: 'divider', '&:hover': { bgcolor: PALETA.guindaSuave } }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {!g.estadoComun && <Box component="span" title={r.etiqueta_estado} sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: COLOR_ESTADO[r.estado], flexShrink: 0 }} />}
              <Typography variant="body2" sx={{ fontWeight: 600, flex: 1, minWidth: 0 }} noWrap title={r.comisionado}>{r.comisionado || 'Sin comisionado'}</Typography>
              {!g.estadoComun && <Typography variant="caption" sx={{ color: COLOR_ESTADO[r.estado], fontWeight: 600, flexShrink: 0 }}>{r.etiqueta_estado}</Typography>}
              <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0 }}>{r.codigo}</Typography>
              <ChevronRightIcon sx={{ fontSize: 18, color: 'text.disabled', flexShrink: 0 }} />
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mt: 0.25, flexWrap: 'wrap' }}>
              <Typography variant="caption" color="text.secondary">Rendido <Box component="b" sx={{ color: 'text.primary' }}>{soles(r.reconocido)}</Box></Typography>
              <Typography variant="caption" color="text.secondary">Saldo <Box component="b" sx={{ color: r.saldo > 0 ? PALETA.guinda : 'text.primary' }}>{soles(r.saldo)}</Box></Typography>
              {r.avance && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, ml: 'auto' }}>
                  <LinearProgress variant="determinate" value={av.fraccion * 100} sx={{ width: 48, height: 4, borderRadius: 2, bgcolor: PALETA.superficieMedia, '& .MuiLinearProgress-bar': { bgcolor: PALETA.exito } }} />
                  <Typography variant="caption" color="text.secondary">{r.avance.validadas}/{r.avance.total}</Typography>
                </Box>
              )}
            </Box>
            {(r.errores > 0 || (r.pendientes ?? 0) > 0) && (
              <Box sx={{ display: 'flex', gap: 0.75, mt: 0.5, flexWrap: 'wrap' }}>
                {r.errores > 0 && <Chip size="small" variant="outlined" label={`${r.errores} por corregir`} sx={{ height: 20, fontSize: 11.5, color: PALETA.error, borderColor: PALETA.error }} />}
                {(r.pendientes ?? 0) > 0 && <Chip size="small" variant="outlined" label={`${r.pendientes} pendiente(s)`} sx={{ height: 20, fontSize: 11.5, color: PALETA.avisoOscuro, borderColor: PALETA.avisoOscuro }} />}
              </Box>
            )}
          </ButtonBase>
        )
      })}
    </Box>
  )
}

export default function Rendiciones() {
  const navegar = useNavigate()
  const [consulta, setConsulta] = useSearchParams()
  const [filas, setFilas] = useState<FilaLista[] | null>(null)
  const [admin, setAdmin] = useState(false)
  const [aviso, setAviso] = useState<Aviso | null>(null)
  const [nueva, setNueva] = useState<{ semana?: number; usuario?: number } | null>(null)
  const [textoPegar, setTextoPegar] = useState('')
  const ver = consulta.get('ver') === 'todas' || consulta.get('ver') === 'resumen' ? consulta.get('ver')! : 'mias'
  const hoy = hoyIso()

  const cargar = useCallback(async () => {
    try {
      const r = await api<{ rendiciones: FilaLista[]; admin: boolean; yo: number }>(`/api/rendiciones${ver === 'todas' ? '?todas=true' : ''}`)
      setFilas(r.rendiciones)
      setAdmin(r.admin)
      return r.rendiciones
    } catch (e) {
      setFilas([])
      setAviso({ tipo: 'error', texto: e instanceof Error ? e.message : 'No se pudo cargar la lista.' })
      return []
    }
  }, [ver])
  useEffect(() => { void cargar() }, [cargar])

  const quitar = (clave: string) => {
    const c = new URLSearchParams(consulta)
    c.delete(clave)
    setConsulta(c, { replace: true })
  }

  // ?nueva=1 · ?semana=<id> · ?pegar=<id de mensaje>
  useEffect(() => {
    if (consulta.get('nueva') === '1') {
      setNueva({})
      quitar('nueva')
    }
    const semana = Number(consulta.get('semana') ?? '')
    if (semana) {
      quitar('semana')
      api<{ mia: number | null }>(`/api/rendiciones/semana/${semana}/equipo`)
        .then((r) => (r.mia ? navegar(`/rendiciones/${r.mia}`) : setNueva({ semana })))
        .catch(() => setNueva({ semana }))
    }
    const mid = Number(consulta.get('pegar') ?? '')
    if (mid) {
      quitar('pegar')
      textoDeMensaje(mid).then(async (texto) => {
        const abiertas = (await cargar()).filter((f) => ['borrador', 'observada', 'lista'].includes(f.estado))
        if (abiertas.length === 1) navegar(`/rendiciones/${abiertas[0].id}?ver=comprobantes`, { state: { textoPegar: texto } })
        else {
          setTextoPegar(texto)
          setAviso({ tipo: 'info', texto: 'Elija la rendición donde van estos comprobantes.' })
        }
      }).catch(() => setAviso({ tipo: 'error', texto: 'No se pudo traer el mensaje del chat; pegue el texto en la rendición.' }))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [consulta])

  const abrir = (id: number) => navegar(`/rendiciones/${id}`, textoPegar ? { state: { textoPegar } } : undefined)
  const grupos = agruparPorComision(filas ?? [])
  const abiertos = grupos.filter((g) => g.abierta)
  const cerrados = grupos.filter((g) => !g.abierta)

  return (
    <Marco modulo="rendicion" fondo={PALETA.fondo}>
      <Box sx={{ px: { xs: 1.5, sm: 2.5 }, py: { xs: 1.5, sm: 2.5 }, maxWidth: 980, width: '100%', mx: 'auto' }}>
        <BarraModulo
          alActualizar={cargar}
          principal={
            <Button variant="contained" startIcon={<AddCircleOutlineIcon />} onClick={() => setNueva({})}>Nueva rendición</Button>
          }
          mas={[admin && { etiqueta: 'Parámetros del despacho', icono: <TuneOutlinedIcon fontSize="small" />, alPulsar: () => setConsulta({ parametros: '1' }) }]}
        >
          {admin && (
            <ToggleButtonGroup size="small" exclusive value={ver} onChange={(_, v) => v && setConsulta(v === 'mias' ? {} : { ver: v }, { replace: true })}>
              <ToggleButton value="mias">Mías</ToggleButton>
              <ToggleButton value="todas">Todas</ToggleButton>
              <ToggleButton value="resumen">Resumen</ToggleButton>
            </ToggleButtonGroup>
          )}
          <BotonAyuda titulo="Rendición de cuentas">
            Registre sus comprobantes (foto o PDF), revise la movilidad —es la misma para todos los que viajaron juntos: lo
            que uno registra lo ve el otro— y genere los Anexos 3 y 4 listos para firmar. Puede hacer la suya o, como
            encargado, las de toda la comisión (elija el comisionado al crearla). Los controles avisan lo que falta.
          </BotonAyuda>
        </BarraModulo>

        {textoPegar && <Alert severity="info" sx={{ mb: 1.5 }} onClose={() => setTextoPegar('')}>Tiene comprobantes del chat por agregar: abra la rendición.</Alert>}
        {filas === null && <LinearProgress />}

        {ver === 'resumen' ? (
          <ResumenDespacho alAbrir={abrir} alCrear={(semana, usuario) => setNueva({ semana, usuario })} />
        ) : (
          <>
            {filas?.length === 0 && (
              <Box sx={{ textAlign: 'center', py: 5, color: 'text.secondary' }}>
                <ReceiptLongOutlinedIcon sx={{ fontSize: 44, color: PALETA.apagado }} />
                <Typography variant="body2">Aún no hay rendiciones.</Typography>
              </Box>
            )}
            {abiertos.length > 0 && (
              <Box sx={{ display: 'grid', gap: 1.25, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, alignItems: 'start', mb: 2 }}>
                {abiertos.map((g) => <TarjetaComision key={g.clave} g={g} hoy={hoy} alAbrir={abrir} />)}
              </Box>
            )}
            {cerrados.length > 0 && (
              <>
                <Typography variant="overline" color="text.secondary">Presentadas y cerradas</Typography>
                <Box sx={{ display: 'grid', gap: 1.25, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, alignItems: 'start' }}>
                  {cerrados.map((g) => <TarjetaComision key={g.clave} g={g} hoy={hoy} alAbrir={abrir} />)}
                </Box>
              </>
            )}
          </>
        )}
      </Box>

      <NuevaRendicion
        abierto={nueva !== null}
        semanaInicial={nueva?.semana}
        usuarioInicial={nueva?.usuario}
        admin={admin}
        alCerrar={() => setNueva(null)}
        alCrear={(id) => { setNueva(null); abrir(id) }}
        alExiste={(id) => { setNueva(null); setAviso({ tipo: 'info', texto: 'Ya tiene una rendición de esa semana: se abre.' }); abrir(id) }}
        alError={(e) => setAviso({ tipo: 'error', texto: e instanceof ErrorApi || e instanceof Error ? e.message : 'No se pudo crear.' })}
      />
      <ParametrosDespacho abierto={consulta.get('parametros') === '1'} alCerrar={() => quitar('parametros')} alGuardar={() => setAviso({ tipo: 'success', texto: 'Parámetros guardados.' })} />
      <Snackbar open={aviso !== null} autoHideDuration={5000} onClose={() => setAviso(null)} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        {aviso ? <Alert severity={aviso.tipo} variant="filled" onClose={() => setAviso(null)}>{aviso.texto}</Alert> : undefined}
      </Snackbar>
    </Marco>
  )
}
