import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-antd": ["antd"],
          "vendor-react": ["@tanstack/react-query", "react", "react-dom", "zustand"],
        },
      },
    },
  },
  server: {
    host: "127.0.0.1",
    port: 1420,
    strictPort: true,
  },
  test: {
    coverage: {
      include: ["src/**/*.{ts,tsx}"],
      provider: "v8",
      reporter: ["text", "html"],
    },
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
