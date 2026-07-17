import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    // Dev: forward /api/* to the FastAPI backend on :8000.
    // In production the API is served by the same uvicorn process
    // (via StaticFiles), so the relative path in api.js works.
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
})
