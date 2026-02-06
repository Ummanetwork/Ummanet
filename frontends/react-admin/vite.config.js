import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/admin/',
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    allowedHosts: [
      'devbest.pro',
      '144.31.194.10',
      'react_admin',
      'react-admin',
      'localhost',
      '127.0.0.1',
    ],
  },
});
