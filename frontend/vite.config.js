import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 127.0.0.1 rather than localhost: Node may resolve localhost to IPv6 (::1)
// while uvicorn listens on IPv4.
const apiTarget = process.env.PIPELINE_API_URL || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': apiTarget,
    },
  },
})
