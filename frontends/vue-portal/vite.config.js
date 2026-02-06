import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  base: '/portal/',
  plugins: [vue()],
  server: {
    host: true,
    port: 5173,
    allowedHosts: [
      'devbest.pro',
      '144.31.194.10',
      'vue_portal',
      'vue-portal',
      'localhost',
      '127.0.0.1',
    ],
  },
});
