/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    restoreMocks: true,
  },
  server: {
    port: 5173,
    proxy: {
      // Port 8001 by default: 8000 is a common default that other local
      // projects often occupy, which silently proxies /api to the wrong app.
      // Override with CIIS_API_PORT to match `dev.sh`.
      "/api": {
        target: `http://localhost:${process.env.CIIS_API_PORT ?? 8001}`,
        changeOrigin: true,
      },
    },
  },
});
