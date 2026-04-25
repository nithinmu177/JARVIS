import { defineConfig } from "vite";

export default defineConfig({
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/ws": {
        target: "http://127.0.0.1:8340",
        ws: true,
      },
      "/api": {
        target: "http://127.0.0.1:8340",
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
