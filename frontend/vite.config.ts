import { defineConfig } from "vite";

export default defineConfig({
  server: {
    host: "0.0.0.0",
    port: 5173,
    allowedHosts: true,
    proxy: {
      "/ws": {
        target: "http://127.0.0.1:8340",
        ws: true,
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path,
      },
      "/api": {
        target: "http://127.0.0.1:8340",
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    outDir: "dist",
  },
  preview: {
    host: "0.0.0.0",
    port: 4173,
  },
});
