import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import tailwindcss from '@tailwindcss/vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // Optionally, rewrite the path if your backend expects no '/api' prefix:
        // rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
});
