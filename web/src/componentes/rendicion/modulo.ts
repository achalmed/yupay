/**
 * El módulo web de Rendición de cuentas (proyecto Yupay; fase 10.2b del contrato de Tiqsi, 2026-10-20): sus pantallas,
 * sus rutas y cómo entra al menú del anfitrión. Qillqa arma con esto su entrada en el menú (navegacion.ts) y sus
 * rutas (App.tsx); la página de Rendición SOLA (src/rendicion_sola.tsx), su cáscara mínima. El nombre, en castellano
 * y por su función.
 *
 * Los viáticos de cada comisión de servicio —la Semana de representación, sobre todo—: comprobantes con foto,
 * movilidad propuesta desde las actividades, controles y los Anexos 3 y 4. Todo el equipo salvo el invitado; cada
 * quien ve las suyas.
 */
import ReceiptLongOutlinedIcon from '@mui/icons-material/ReceiptLongOutlined'
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline'
import SummarizeOutlinedIcon from '@mui/icons-material/SummarizeOutlined'
import TuneOutlinedIcon from '@mui/icons-material/TuneOutlined'
import { definirModuloWeb } from '@qillqa/tiqsi'

export const RENDICION = definirModuloWeb({
  id: 'rendicion',
  nombre: 'Rendición de cuentas',
  corto: 'Rendiciones',
  ruta: '/rendiciones',
  icono: ReceiptLongOutlinedIcon,
  descripcion: 'Viáticos de cada comisión: comprobantes, movilidad, controles y los anexos listos para firmar.',
  roles: ['administrador', 'secretaria', 'asesor', 'diputado', 'prensa'],
  opciones: [
    { etiqueta: 'Mis rendiciones', ruta: '/rendiciones', icono: ReceiptLongOutlinedIcon, ayuda: 'Las suyas, con su saldo y su plazo' },
    { etiqueta: 'Nueva rendición', ruta: '/rendiciones?nueva=1', icono: AddCircleOutlineIcon, accion: true, ayuda: 'De una semana de representación u otra comisión' },
    { etiqueta: 'Resumen del despacho', ruta: '/rendiciones?ver=resumen', icono: SummarizeOutlinedIcon, soloAdmin: true, ayuda: 'Cada comisionado de la semana: recibido, rendido y saldo' },
    { etiqueta: 'Parámetros', ruta: '/rendiciones?parametros=1', icono: TuneOutlinedIcon, soloAdmin: true, ayuda: 'Tope diario, % de declaración jurada y plazo' },
  ],
  cargar: () => import('../../paginas/Rendiciones'),
  pantallas: [
    // Una rendición: sus pasos (datos, comprobantes, movilidad, revisión, documento).
    { ruta: '/rendiciones/:id', cargar: () => import('../../paginas/Rendicion') },
  ],
})
