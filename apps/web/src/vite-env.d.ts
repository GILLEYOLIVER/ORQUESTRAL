/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_AUTH_PREVIEW_ENABLED?: string;
  readonly VITE_REMOTE_DEVELOPMENT?: string;
  readonly VITE_N8N_ENABLED?: string;
  readonly VITE_OBJECT_STORAGE_ENABLED?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
