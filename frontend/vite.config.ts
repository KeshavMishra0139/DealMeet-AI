import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const api = process.env.JODIDAR_API ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  // Read VITE_FIREBASE_* from the repo-root .env, next to the API settings.
  envDir: "..",
  server: { proxy: { "/api": api } },
  preview: { proxy: { "/api": api } },
  build: { chunkSizeWarningLimit: 900 },
});
