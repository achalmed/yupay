/**
 * Rendición de cuentas SOLA en el navegador (Yupay): la cáscara mínima de Tiqsi con el módulo web de Rendición, contra el
 * anfitrión mínimo del backend (yupay/sola.py). No importa nada de Qillqa. Se construye desde la raíz con
 * `npm run web:construir`.
 */
import { createRoot } from 'react-dom/client'
import { CascaronMinimo } from '@qillqa/tiqsi/minimo'
import { RENDICION } from './componentes/rendicion/modulo'

createRoot(document.getElementById('root')!).render(<CascaronMinimo modulo={RENDICION} />)
