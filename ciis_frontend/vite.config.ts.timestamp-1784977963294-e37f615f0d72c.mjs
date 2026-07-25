// vite.config.ts
import react from "file:///sessions/sweet-focused-shannon/mnt/project/ciis_frontend/node_modules/@vitejs/plugin-react/dist/index.js";
import path from "node:path";
import { defineConfig } from "file:///sessions/sweet-focused-shannon/mnt/project/ciis_frontend/node_modules/vite/dist/node/index.js";
var __vite_injected_original_dirname = "/sessions/sweet-focused-shannon/mnt/project/ciis_frontend";
var vite_config_default = defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__vite_injected_original_dirname, "src") }
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    restoreMocks: true
  },
  server: {
    port: 5173,
    proxy: {
      // Port 8001 by default: 8000 is a common default that other local
      // projects often occupy, which silently proxies /api to the wrong app.
      // Override with CIIS_API_PORT to match `dev.sh`.
      "/api": {
        target: `http://localhost:${process.env.CIIS_API_PORT ?? 8001}`,
        changeOrigin: true
      }
    }
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcudHMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCIvc2Vzc2lvbnMvc3dlZXQtZm9jdXNlZC1zaGFubm9uL21udC9wcm9qZWN0L2NpaXNfZnJvbnRlbmRcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfZmlsZW5hbWUgPSBcIi9zZXNzaW9ucy9zd2VldC1mb2N1c2VkLXNoYW5ub24vbW50L3Byb2plY3QvY2lpc19mcm9udGVuZC92aXRlLmNvbmZpZy50c1wiO2NvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9pbXBvcnRfbWV0YV91cmwgPSBcImZpbGU6Ly8vc2Vzc2lvbnMvc3dlZXQtZm9jdXNlZC1zaGFubm9uL21udC9wcm9qZWN0L2NpaXNfZnJvbnRlbmQvdml0ZS5jb25maWcudHNcIjsvLy8gPHJlZmVyZW5jZSB0eXBlcz1cInZpdGVzdC9jb25maWdcIiAvPlxuaW1wb3J0IHJlYWN0IGZyb20gXCJAdml0ZWpzL3BsdWdpbi1yZWFjdFwiO1xuaW1wb3J0IHBhdGggZnJvbSBcIm5vZGU6cGF0aFwiO1xuaW1wb3J0IHsgZGVmaW5lQ29uZmlnIH0gZnJvbSBcInZpdGVcIjtcblxuZXhwb3J0IGRlZmF1bHQgZGVmaW5lQ29uZmlnKHtcbiAgcGx1Z2luczogW3JlYWN0KCldLFxuICByZXNvbHZlOiB7XG4gICAgYWxpYXM6IHsgXCJAXCI6IHBhdGgucmVzb2x2ZShfX2Rpcm5hbWUsIFwic3JjXCIpIH0sXG4gIH0sXG4gIHRlc3Q6IHtcbiAgICBnbG9iYWxzOiB0cnVlLFxuICAgIGVudmlyb25tZW50OiBcImpzZG9tXCIsXG4gICAgc2V0dXBGaWxlczogW1wiLi9zcmMvdGVzdC9zZXR1cC50c1wiXSxcbiAgICBjc3M6IGZhbHNlLFxuICAgIHJlc3RvcmVNb2NrczogdHJ1ZSxcbiAgfSxcbiAgc2VydmVyOiB7XG4gICAgcG9ydDogNTE3MyxcbiAgICBwcm94eToge1xuICAgICAgLy8gUG9ydCA4MDAxIGJ5IGRlZmF1bHQ6IDgwMDAgaXMgYSBjb21tb24gZGVmYXVsdCB0aGF0IG90aGVyIGxvY2FsXG4gICAgICAvLyBwcm9qZWN0cyBvZnRlbiBvY2N1cHksIHdoaWNoIHNpbGVudGx5IHByb3hpZXMgL2FwaSB0byB0aGUgd3JvbmcgYXBwLlxuICAgICAgLy8gT3ZlcnJpZGUgd2l0aCBDSUlTX0FQSV9QT1JUIHRvIG1hdGNoIGBkZXYuc2hgLlxuICAgICAgXCIvYXBpXCI6IHtcbiAgICAgICAgdGFyZ2V0OiBgaHR0cDovL2xvY2FsaG9zdDoke3Byb2Nlc3MuZW52LkNJSVNfQVBJX1BPUlQgPz8gODAwMX1gLFxuICAgICAgICBjaGFuZ2VPcmlnaW46IHRydWUsXG4gICAgICB9LFxuICAgIH0sXG4gIH0sXG59KTtcbiJdLAogICJtYXBwaW5ncyI6ICI7QUFDQSxPQUFPLFdBQVc7QUFDbEIsT0FBTyxVQUFVO0FBQ2pCLFNBQVMsb0JBQW9CO0FBSDdCLElBQU0sbUNBQW1DO0FBS3pDLElBQU8sc0JBQVEsYUFBYTtBQUFBLEVBQzFCLFNBQVMsQ0FBQyxNQUFNLENBQUM7QUFBQSxFQUNqQixTQUFTO0FBQUEsSUFDUCxPQUFPLEVBQUUsS0FBSyxLQUFLLFFBQVEsa0NBQVcsS0FBSyxFQUFFO0FBQUEsRUFDL0M7QUFBQSxFQUNBLE1BQU07QUFBQSxJQUNKLFNBQVM7QUFBQSxJQUNULGFBQWE7QUFBQSxJQUNiLFlBQVksQ0FBQyxxQkFBcUI7QUFBQSxJQUNsQyxLQUFLO0FBQUEsSUFDTCxjQUFjO0FBQUEsRUFDaEI7QUFBQSxFQUNBLFFBQVE7QUFBQSxJQUNOLE1BQU07QUFBQSxJQUNOLE9BQU87QUFBQTtBQUFBO0FBQUE7QUFBQSxNQUlMLFFBQVE7QUFBQSxRQUNOLFFBQVEsb0JBQW9CLFFBQVEsSUFBSSxpQkFBaUIsSUFBSTtBQUFBLFFBQzdELGNBQWM7QUFBQSxNQUNoQjtBQUFBLElBQ0Y7QUFBQSxFQUNGO0FBQ0YsQ0FBQzsiLAogICJuYW1lcyI6IFtdCn0K
