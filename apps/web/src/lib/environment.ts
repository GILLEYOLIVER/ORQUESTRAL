export const environment = {
  remoteDevelopment: import.meta.env.VITE_REMOTE_DEVELOPMENT === "true",
  n8nEnabled: import.meta.env.VITE_N8N_ENABLED !== "false",
  objectStorageEnabled: import.meta.env.VITE_OBJECT_STORAGE_ENABLED !== "false",
};
