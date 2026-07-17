import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Boxes,
  CheckCircle2,
  Clock3,
  KeyRound,
  PlugZap,
  Power,
  TestTube2,
} from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";
import { PermissionGuard } from "../components/PermissionGuard";
import { ApiClientError, request } from "../lib/http";

interface PluginResponse {
  id: string;
  code: string;
  name: string;
  version: string;
  description: string;
  authentication_type: string;
  catalog_status: "installed" | "planned" | "disabled";
  company_status: "active" | "inactive";
  configuration: Record<string, unknown>;
}

interface CredentialResponse {
  id: string;
  plugin_id: string;
  name: string;
  status: string;
  masked_values: Record<string, string>;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
}

interface ConnectionTestResponse {
  success: boolean;
  message: string;
}

interface CredentialFormState {
  name: string;
  endpoint: string;
  username: string;
  password: string;
  token: string;
}

const emptyCredential: CredentialFormState = {
  name: "",
  endpoint: "",
  username: "",
  password: "",
  token: "",
};

function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiClientError ? error.message : fallback;
}

export function PluginsPage() {
  const queryClient = useQueryClient();
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [credential, setCredential] = useState<CredentialFormState>(emptyCredential);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const plugins = useQuery({
    queryKey: ["plugins"],
    queryFn: () => request<PluginResponse[]>("/plugins"),
  });

  const selectedPlugin = useMemo(
    () => plugins.data?.find((plugin) => plugin.code === selectedCode) ?? null,
    [plugins.data, selectedCode],
  );

  const toggle = useMutation({
    mutationFn: (plugin: PluginResponse) =>
      request<PluginResponse>(`/plugins/${plugin.code}`, {
        method: "PATCH",
        body: {
          status: plugin.company_status === "active" ? "inactive" : "active",
          configuration: plugin.configuration,
        },
      }),
    onSuccess: async (plugin) => {
      setSuccessMessage(
        plugin.company_status === "active"
          ? `${plugin.name} foi ativado para esta empresa.`
          : `${plugin.name} foi desativado para esta empresa.`,
      );
      await queryClient.invalidateQueries({ queryKey: ["plugins"] });
    },
  });

  const saveAndTest = useMutation({
    mutationFn: async (plugin: PluginResponse) => {
      const values: Record<string, string> = {};
      if (credential.endpoint.trim()) values.endpoint = credential.endpoint.trim();
      if (credential.username.trim()) values.username = credential.username.trim();
      if (credential.password) values.password = credential.password;
      if (credential.token) values.token = credential.token;

      const created = await request<CredentialResponse>(
        `/plugins/${plugin.code}/credentials`,
        {
          method: "POST",
          body: {
            name: credential.name.trim(),
            values,
            expires_at: null,
          },
        },
      );
      return request<ConnectionTestResponse>(
        `/plugins/${plugin.code}/credentials/${created.id}/test`,
        { method: "POST" },
      );
    },
    onSuccess: (result) => {
      setSuccessMessage(result.message);
      setCredential(emptyCredential);
    },
  });

  const openConfiguration = (plugin: PluginResponse) => {
    setSuccessMessage(null);
    setSelectedCode(plugin.code);
    setCredential({
      ...emptyCredential,
      name: `${plugin.name} principal`,
    });
  };

  return (
    <div className="management-page">
      <div className="dashboard__heading">
        <div>
          <span className="eyebrow">Fase 5 · Ecossistema de plugins</span>
          <h1>Integrações da empresa</h1>
          <p>
            Ative conectores, proteja credenciais e valide a configuração sem
            expor senhas ou tokens na interface.
          </p>
        </div>
        <span className="phase-badge">
          <PlugZap size={16} /> Fase 5
        </span>
      </div>

      {plugins.isError ? (
        <Alert variant="error">Não foi possível carregar o catálogo de plugins.</Alert>
      ) : null}
      {toggle.isError ? (
        <Alert variant="error">
          {errorMessage(toggle.error, "Não foi possível alterar o plugin.")}
        </Alert>
      ) : null}
      {saveAndTest.isError ? (
        <Alert variant="error">
          {errorMessage(
            saveAndTest.error,
            "Não foi possível salvar ou testar a credencial.",
          )}
        </Alert>
      ) : null}
      {successMessage ? <Alert variant="success">{successMessage}</Alert> : null}

      <div className="module-grid">
        {plugins.isLoading ? <p>Carregando integrações…</p> : null}
        {plugins.data?.map((plugin) => {
          const installed = plugin.catalog_status === "installed";
          const active = plugin.company_status === "active";
          return (
            <Card className="module-card" key={plugin.id}>
              <div className="module-card__header">
                <span className="module-card__icon">
                  <Boxes aria-hidden="true" />
                </span>
                <span
                  className={`status-chip ${
                    active ? "status-chip--active" : "status-chip--inactive"
                  }`}
                >
                  {active ? "ativo" : installed ? "inativo" : "em breve"}
                </span>
              </div>
              <div>
                <span className="eyebrow">
                  {plugin.authentication_type.replaceAll("_", " ")}
                </span>
                <h2>{plugin.name}</h2>
                <p>{plugin.description}</p>
              </div>
              <div className="module-card__meta">
                {installed ? <CheckCircle2 size={16} /> : <Clock3 size={16} />}
                <span>
                  {installed
                    ? `Disponível · versão ${plugin.version}`
                    : "Planejado para uma próxima entrega"}
                </span>
              </div>
              {installed ? (
                <PermissionGuard all={["plugins.manage"]}>
                  <div className="form-actions">
                    <Button
                      loading={toggle.isPending && toggle.variables?.id === plugin.id}
                      onClick={() => toggle.mutate(plugin)}
                      variant={active ? "ghost" : "primary"}
                    >
                      <Power size={17} /> {active ? "Desativar" : "Ativar"}
                    </Button>
                    {active ? (
                      <Button onClick={() => openConfiguration(plugin)} variant="ghost">
                        <KeyRound size={17} /> Configurar
                      </Button>
                    ) : null}
                  </div>
                </PermissionGuard>
              ) : null}
            </Card>
          );
        })}
      </div>

      {selectedPlugin ? (
        <Card>
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Cofre de credenciais</span>
              <h2>Configurar {selectedPlugin.name}</h2>
              <p>
                Os valores sensíveis são criptografados pela API antes de serem
                persistidos.
              </p>
            </div>
            <Button onClick={() => setSelectedCode(null)} variant="ghost">
              Fechar
            </Button>
          </div>
          <form
            className="stack-form"
            onSubmit={(event) => {
              event.preventDefault();
              setSuccessMessage(null);
              saveAndTest.mutate(selectedPlugin);
            }}
          >
            <label className="native-field">
              <span>Nome da credencial</span>
              <input
                required
                value={credential.name}
                onChange={(event) =>
                  setCredential((current) => ({ ...current, name: event.target.value }))
                }
              />
            </label>
            <label className="native-field">
              <span>Endereço ou servidor</span>
              <input
                placeholder="https://api.exemplo.com ou smtp.exemplo.com"
                value={credential.endpoint}
                onChange={(event) =>
                  setCredential((current) => ({
                    ...current,
                    endpoint: event.target.value,
                  }))
                }
              />
            </label>
            {selectedPlugin.authentication_type === "username_password" ? (
              <>
                <label className="native-field">
                  <span>Usuário</span>
                  <input
                    value={credential.username}
                    onChange={(event) =>
                      setCredential((current) => ({
                        ...current,
                        username: event.target.value,
                      }))
                    }
                  />
                </label>
                <label className="native-field">
                  <span>Senha</span>
                  <input
                    required
                    type="password"
                    value={credential.password}
                    onChange={(event) =>
                      setCredential((current) => ({
                        ...current,
                        password: event.target.value,
                      }))
                    }
                  />
                </label>
              </>
            ) : (
              <label className="native-field">
                <span>Token, segredo ou chave de API</span>
                <input
                  required
                  type="password"
                  value={credential.token}
                  onChange={(event) =>
                    setCredential((current) => ({
                      ...current,
                      token: event.target.value,
                    }))
                  }
                />
              </label>
            )}
            <div className="form-actions">
              <Button loading={saveAndTest.isPending} type="submit">
                <TestTube2 size={17} /> Salvar e testar
              </Button>
            </div>
          </form>
        </Card>
      ) : null}
    </div>
  );
}
