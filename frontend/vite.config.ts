import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'ERP',
        short_name: 'ERP',
        lang: 'fr',
        display: 'standalone',
        start_url: '/',
        theme_color: '#14532d',
        background_color: '#ffffff',
        icons: [{ src: '/icone.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' }],
      },
    }),
  ],
  // En développement, l'API Django tourne sur le port 8000.
  server: { proxy: { '/api': 'http://localhost:8000', '/admin': 'http://localhost:8000', '/static': 'http://localhost:8000' } },
})
