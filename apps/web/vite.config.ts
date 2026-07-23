import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

const PUBLIC_CLIENT_ENVIRONMENT = new Set([
  "VITE_API_BASE_URL",
  "VITE_AUTH_PREVIEW_ENABLED",
  "VITE_N8N_ENABLED",
  "VITE_OBJECT_STORAGE_ENABLED",
  "VITE_REMOTE_DEVELOPMENT",
]);

function assertPublicClientEnvironment(environment: Record<string, string>) {
  const forbidden = Object.keys(environment)
    .filter((key) => key.startsWith("VITE_"))
    .filter((key) => !PUBLIC_CLIENT_ENVIRONMENT.has(key));
  if (forbidden.length > 0) {
    throw new Error(
      `Variável pública Vite não permitida: ${forbidden.sort().join(", ")}. ` +
        "Tokens, senhas, chaves e credenciais nunca podem entrar no bundle do navegador.",
    );
  }

  const apiBaseUrl = environment.VITE_API_BASE_URL;
  if (apiBaseUrl && (/[@?#]/.test(apiBaseUrl) || /:\/\/[^/]*:.*@/.test(apiBaseUrl))) {
    throw new Error(
      "VITE_API_BASE_URL deve conter apenas uma origem ou caminho público, sem credenciais ou parâmetros.",
    );
  }
}

export default defineConfig(({ command, mode }) => {
  const environment = loadEnv(mode, process.cwd(), ["VITE_", "DEV_"]);
  assertPublicClientEnvironment(environment);
  if (command === "build" && environment.VITE_AUTH_PREVIEW_ENABLED === "true") {
    throw new Error(
      "VITE_AUTH_PREVIEW_ENABLED não pode ser habilitado em builds de produção.",
    );
  }
  const apiTarget =
    environment.DEV_API_PROXY_TARGET ?? "http://localhost:8000";

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
