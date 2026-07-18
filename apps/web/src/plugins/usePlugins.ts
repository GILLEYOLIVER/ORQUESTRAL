import { useQuery } from "@tanstack/react-query";
import { request } from "../lib/http";
import { useSession } from "../session/context";

export interface PluginFieldDefinition {
  key: string;
  label: string;
  kind: "text" | "password" | "url" | "integer" | "boolean";
  required: boolean;
  secret: boolean;
  placeholder?: string | null;
  default?: string | number | boolean | null;
}

export interface PluginManifest {
  credential_fields: PluginFieldDefinition[];
  configuration_fields: PluginFieldDefinition[];
  tools: Array<{ code: string; name: string; description: string }>;
  triggers: string[];
  actions: string[];
  supports_token_refresh: boolean;
  supports_webhooks: boolean;
}

export interface PluginResponse {
  id: string;
  code: string;
  name: string;
  version: string;
  description: string;
  authentication_type: string;
  catalog_status: string;
  company_status: "active" | "inactive";
  configuration: Record<string, unknown>;
  manifest: PluginManifest;
}

export interface CredentialResponse {
  id: string;
  plugin_id: string;
  name: string;
  status: "active" | "expired" | "revoked";
  masked_values: Record<string, string>;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConnectionTestResponse {
  test_id: string;
  success: boolean;
  message: string;
  duration_ms: number;
  tested_at: string;
}

export function usePlugins(enabled = true) {
  const { me, status } = useSession();
  return useQuery({
    queryKey: ["plugins", me?.current_company?.id],
    queryFn: () => request<PluginResponse[]>("/plugins"),
    enabled:
      enabled &&
      status === "authenticated" &&
      Boolean(me?.current_company) &&
      (me?.permissions.includes("plugins.view") ?? false),
  });
}
