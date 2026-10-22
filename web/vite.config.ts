// Rendición de cuentas SOLA (Yupay): una página con la cáscara mínima de Tiqsi, que sirve el anfitrión mínimo del backend
// (RENDICION_WEB=web/dist). Desde la raíz: `npm run web:construir` (o `npm run web` con la API sola en 8031).
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const aqui = (ruta: string) => fileURLToPath(new URL(ruta, import.meta.url))

export default defineConfig({
  root: aqui('./sola'),
  plugins: [react()],
  // Tiqsi web llega por enlace: sin seguirlo, sus importaciones de React y MUI se resuelven aquí (una sola copia).
  resolve: { preserveSymlinks: true },
  build: { outDir: aqui('./dist'), emptyOutDir: true, chunkSizeWarningLimit: 1600 },
  server: { port: 5301, strictPort: true, proxy: { '/api': 'http://127.0.0.1:8031' } },
})
