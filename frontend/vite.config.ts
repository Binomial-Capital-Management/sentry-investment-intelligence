import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@stores': path.resolve(__dirname, './src/stores'),
      '@services': path.resolve(__dirname, './src/services'),
      '@utils': path.resolve(__dirname, './src/utils'),
      '@styles': path.resolve(__dirname, './src/styles'),
    },
  },
  server: {
    port: 3000,
    open: '/sentry',
    proxy: {
      '/api': {
        target: 'http://localhost:8002',  // FastAPI port
        changeOrigin: true,
        // Don't rewrite the path - backend expects /api prefix
        rewrite: undefined,
        configure: (proxy) => {
          // Increase timeouts for long-running tools like ARIMA (5 minutes default)
          const t = Number(process.env.VITE_DEV_PROXY_TIMEOUT_MS ?? 300000);
          // @ts-ignore
          proxy.timeout = t;
          // @ts-ignore
          proxy.proxyTimeout = t;
        },
      },
      '/v6': {
        target: 'http://localhost:8002',
        changeOrigin: true,
        // No rewrite; backend exposes /v6 directly
      },
    },
  },
});