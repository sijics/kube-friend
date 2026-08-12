import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Dev-mode proxy: any request to /api/* is forwarded to the FastAPI backend.
    // This means the React app never hardcodes the backend URL — it always
    // uses relative paths like fetch('/api/chat').
    // In production, nginx handles this same proxying (see nginx.conf).
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
