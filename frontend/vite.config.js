import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  root: '.',
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../frontend-dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        // The analyst workbench (existing)
        analyst: resolve(__dirname, 'index-vite.html'),
        // The MarketLens client app — client-facing Diagnosis surface
        client: resolve(__dirname, 'index-client.html'),
        // The EY editor — curation overlay on the same Diagnosis surface
        editor: resolve(__dirname, 'index-editor.html'),
        // Login page — entry point before client/editor apps load
        login: resolve(__dirname, 'index-login.html'),
      },
    },
  },
});

