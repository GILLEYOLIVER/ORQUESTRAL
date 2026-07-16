import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ command, mode }) => {
  const environment = loadEnv(mode, process.cwd(), "");
  if (command === "build" && environment.VITE_AUTH_PREVIEW_ENABLED === "true") {
    throw new Error(
      "VITE_AUTH_PREVIEW_ENABLED não pode ser habilitado em builds de produção.",
    );
  }
  const apiTarget =
    environment.VITE_DEV_API_PROXY_TARGET ?? "http://localhost:8000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/health": apiTarget,
        "/ready": apiTarget,
        "/api": {
          target: apiTarget,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
  };
});
