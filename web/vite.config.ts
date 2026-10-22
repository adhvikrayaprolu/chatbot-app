import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// `npm run dev` proxies API calls to Flask on :5000; `npm run build` emits web/dist for Flask to serve.
const api = { target: 'http://127.0.0.1:5000', changeOrigin: false };

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': api, '/chat': api, '/healthz': api } },
  build: { outDir: 'dist', emptyOutDir: true },
});
