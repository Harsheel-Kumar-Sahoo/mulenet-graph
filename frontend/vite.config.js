import { defineConfig } from 'vite';
// Dev: API + WebSocket proxied to the FastAPI backend (uvicorn mulenet.api.app:app --port 8000).
export default defineConfig({
  server: { proxy: { '/api': 'http://localhost:8000', '/ws': { target: 'ws://localhost:8000', ws: true } } },
  build: { outDir: 'dist', chunkSizeWarningLimit: 1200 },
});
