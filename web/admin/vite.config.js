// vite.config.js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    host: "localhost",
    hmr: {
      host: "localhost",
      port: 5174,
      protocol: "ws",
    },
    proxy: {
      "/api": "http://localhost:5000",  // Flask backend
    },
  },
  build: {
    outDir: "../backend/static/dist",
    emptyOutDir: true,
  },
});
