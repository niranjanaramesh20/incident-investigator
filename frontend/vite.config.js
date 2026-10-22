import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/auth": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/users": "http://127.0.0.1:8000",
      "/evidence": "http://127.0.0.1:8000",
      "/investigate": "http://127.0.0.1:8000",
      "/investigations": "http://127.0.0.1:8000",
      "/evaluations": "http://127.0.0.1:8000",
      "/notifications": "http://127.0.0.1:8000"
    }
  }
});
