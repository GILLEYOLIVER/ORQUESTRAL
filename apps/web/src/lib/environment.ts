interface EnvironmentSource {
  readonly VITE_REMOTE_DEVELOPMENT?: string;
  readonly VITE_N8N_ENABLED?: string;
  readonly VITE_OBJECT_STORAGE_ENABLED?: string;
}

export function resolveEnvironment(source: EnvironmentSource) {
  return {
    remoteDevelopment: source.VITE_REMOTE_DEVELOPMENT === "true",
    n8nEnabled: source.VITE_N8N_ENABLED !== "false",
    objectStorageEnabled: source.VITE_OBJECT_STORAGE_ENABLED !== "false",
  };
}

export const environment = resolveEnvironment(import.meta.env);
