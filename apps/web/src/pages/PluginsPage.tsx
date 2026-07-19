import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Cable,
  CheckCircle2,
  KeyRound,
  Power,
  RefreshCw,
  ShieldCheck,
  Unplug,
} from "lucide-react";
import { Alert, Button, Card, TextField } from "@orkestral/ui-components";
import { PermissionGuard } from "../components/PermissionGuard";
import { ApiClientError, request } from "../lib/http";
import {
  type ConnectionTestResponse,
  type CredentialResponse,
  type PluginFieldDefinition,
  type PluginResponse,
  usePlugins,
} from "../plugins/usePlugins";

function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiClientError ? error.message : fallback;
}

export function PluginsPage() {
  const queryClient = useQueryClient();
  const plugins = usePlugins();
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [credentialName, setCredentialName] = useState("");
  const [values, setValues] = useState<Record<string, string | boolean>>({});
  const [feedback, setFeedback] = useState<ConnectionTestResponse | null>(null);
  const activePlugins = useMemo(
    () =>
      plugins.data?.filter((plugin) => plugin.company_status === "active") ??
      [],
    [plugins.data],
  );
  const selected = plugins.data?.find((plugin) => plugin.code === selectedCode);

  useEffect(() => {
    if (!selectedCode && activePlugins[0])
      setSelectedCode(activePlugins[0].code);
  }, [activePlugins, selectedCode]);

  const credentials = useQuery({
    queryKey: ["plugin-credentials", selectedCode],
    queryFn: () =>
      request<CredentialResponse[]>(`/plugins/${selectedCode}/credentials`),
    enabled: Boolean(selectedCode && selected?.company_status === "active"),
  });

  const toggle = useMutation({
    mutationFn: (plugin: PluginResponse) =>
      request<PluginResponse>(`/plugins/${plugin.code}`, {
        method: "PATCH",
        body: {
          status: plugin.company_status === "active" ? "inactive" : "active",
        },
      }),
    onSuccess: (plugin) => {
      void queryClient.invalidateQueries({ queryKey: ["plugins"] });
      if (plugin.company_status === "active") setSelectedCode(plugin.code);
      else if (selectedCode === plugin.code) setSelectedCode(null);
    },
  });

  const createCredential = useMutation({
    mutationFn: () =>
      request<CredentialResponse>(`/plugins/${selectedCode}/credentials`, {
        method: "POST",
        body: { name: credentialName, values },
      }),
    onSuccess: () => {
      setCredentialName("");
      setValues({});
      void queryClient.invalidateQueries({
        queryKey: ["plugin-credentials", selectedCode],
      });
    },
  });

  const testCredential = useMutation({
    mutationFn: (credential: CredentialResponse) =>
      request<ConnectionTestResponse>(
        `/plugins/${selectedCode}/credentials/${credential.id}/test`,
        { method: "POST", timeoutMs: 15_000 },
      ),
    onSuccess: setFeedback,
  });

  const revokeCredential = useMutation({
    mutationFn: (credential: CredentialResponse) =>
      request<void>(`/plugins/${selectedCode}/credentials/${credential.id}`, {
        method: "DELETE",
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["plugin-credentials", selectedCode],
      }),
  });

  const rotateCredentials = useMutation({
    mutationFn: () =>
      request<{ rotated: number; failed: number }>(
        "/plugins/credentials/rotate",
        { method: "POST" },
      ),
  });

  const submitCredential = (event: FormEvent) => {
    event.preventDefault();
    createCredential.mutate();
  };

  const setDefaultValue = (field: PluginFieldDefinition) =>
    values[field.key] ??
    field.default ??
    (field.kind === "boolean" ? false : "");

  return (
    <div className="management-page plugin-page">
      <div className="dashboard__heading">
        <div>
          <span className="eyebrow">Ecossistema extensível</span>
          <h1>Integrações</h1>
          <p>
            Ative conectores por empresa e mantenha credenciais protegidas no
            cofre central.
          </p>
        </div>
        <PermissionGuard all={["plugins.manage"]}>
          <Button
            onClick={() => rotateCredentials.mutate()}
            loading={rotateCredentials.isPending}
            variant="ghost"
          >
            <RefreshCw size={17} /> Rotacionar cofre
          </Button>
        </PermissionGuard>
      </div>

      {plugins.isError ? (
        <Alert variant="error">
          Não foi possível carregar o catálogo de plugins.
        </Alert>
      ) : null}
      {toggle.isError ? (
        <Alert variant="error">
          {errorMessage(toggle.error, "Não foi possível alterar o plugin.")}
        </Alert>
      ) : null}
      {rotateCredentials.data ? (
        <Alert variant={rotateCredentials.data.failed ? "error" : "success"}>
          {rotateCredentials.data.rotated} credenciais rotacionadas;{" "}
          {rotateCredentials.data.failed} falhas.
        </Alert>
      ) : null}

      <div className="plugin-grid">
        {plugins.isLoading ? <p>Carregando integrações…</p> : null}
        {plugins.data?.map((plugin) => {
          const active = plugin.company_status === "active";
          return (
            <Card
              className={`plugin-card ${selectedCode === plugin.code ? "plugin-card--selected" : ""}`}
              key={plugin.id}
            >
              <div className="module-card__header">
                <span className="module-card__icon">
                  <Cable aria-hidden="true" />
                </span>
                <span
                  className={`status-chip ${active ? "status-chip--active" : "status-chip--inactive"}`}
                >
                  {active ? "ativo" : "inativo"}
                </span>
              </div>
              <div>
                <span className="eyebrow">{plugin.authentication_type}</span>
                <h2>{plugin.name}</h2>
                <p>{plugin.description}</p>
              </div>
              <div className="plugin-capabilities">
                <span>{plugin.manifest.actions.length} ações</span>
                <span>{plugin.manifest.triggers.length} gatilhos</span>
                <span>v{plugin.version}</span>
              </div>
              <div className="form-actions">
                <PermissionGuard all={["plugins.manage"]}>
                  <Button
                    loading={
                      toggle.isPending && toggle.variables?.id === plugin.id
                    }
                    onClick={() => toggle.mutate(plugin)}
                    variant={active ? "ghost" : "primary"}
                  >
                    <Power size={16} /> {active ? "Desativar" : "Ativar"}
                  </Button>
                </PermissionGuard>
                {active ? (
                  <Button
                    onClick={() => setSelectedCode(plugin.code)}
                    variant="secondary"
                  >
                    <KeyRound size={16} /> Credenciais
                  </Button>
                ) : null}
              </div>
            </Card>
          );
        })}
      </div>

      {selected ? (
        <div className="plugin-vault-layout">
          <Card
            className="plugin-credential-form"
            eyebrow="Cofre criptografado"
            title={`Nova credencial · ${selected.name}`}
          >
            <form className="stack-form" onSubmit={submitCredential}>
              <TextField
                label="Nome da credencial"
                onChange={(event) => setCredentialName(event.target.value)}
                required
                value={credentialName}
              />
              {selected.manifest.credential_fields.map((field) =>
                field.kind === "boolean" ? (
                  <label className="check-row" key={field.key}>
                    <input
                      checked={Boolean(setDefaultValue(field))}
                      onChange={(event) =>
                        setValues((current) => ({
                          ...current,
                          [field.key]: event.target.checked,
                        }))
                      }
                      type="checkbox"
                    />
                    <span>{field.label}</span>
                  </label>
                ) : (
                  <TextField
                    key={field.key}
                    label={field.label}
                    onChange={(event) =>
                      setValues((current) => ({
                        ...current,
                        [field.key]: event.target.value,
                      }))
                    }
                    placeholder={field.placeholder ?? undefined}
                    required={field.required}
                    type={
                      field.secret
                        ? "password"
                        : field.kind === "integer"
                          ? "number"
                          : field.kind
                    }
                    value={String(setDefaultValue(field))}
                  />
                ),
              )}
              {createCredential.isError ? (
                <Alert variant="error">
                  {errorMessage(
                    createCredential.error,
                    "Não foi possível salvar a credencial.",
                  )}
                </Alert>
              ) : null}
              <Button loading={createCredential.isPending} type="submit">
                <ShieldCheck size={17} /> Criptografar e salvar
              </Button>
            </form>
          </Card>

          <Card
            className="plugin-credential-list"
            eyebrow="Acesso administrativo"
            title="Credenciais cadastradas"
          >
            {feedback ? (
              <Alert variant={feedback.success ? "success" : "error"}>
                {feedback.message} ({feedback.duration_ms} ms)
              </Alert>
            ) : null}
            {testCredential.isError ? (
              <Alert variant="error">
                {errorMessage(
                  testCredential.error,
                  "O teste não pôde ser executado.",
                )}
              </Alert>
            ) : null}
            {credentials.isLoading ? <p>Carregando credenciais…</p> : null}
            {credentials.data?.length === 0 ? (
              <div className="empty-state">
                <KeyRound />
                <strong>Nenhuma credencial</strong>
                <span>Cadastre a primeira conexão deste plugin.</span>
              </div>
            ) : null}
            {credentials.data?.map((credential) => (
              <div className="credential-row" key={credential.id}>
                <div>
                  <strong>{credential.name}</strong>
                  <span>
                    {Object.keys(credential.masked_values).join(" · ") ||
                      "campos protegidos"}
                  </span>
                </div>
                <span
                  className={`status-chip ${credential.status === "active" ? "status-chip--active" : "status-chip--disabled"}`}
                >
                  {credential.status}
                </span>
                {credential.status === "active" ? (
                  <div className="form-actions">
                    <Button
                      loading={
                        testCredential.isPending &&
                        testCredential.variables?.id === credential.id
                      }
                      onClick={() => testCredential.mutate(credential)}
                      variant="secondary"
                    >
                      <CheckCircle2 size={16} /> Testar
                    </Button>
                    <Button
                      loading={
                        revokeCredential.isPending &&
                        revokeCredential.variables?.id === credential.id
                      }
                      onClick={() => revokeCredential.mutate(credential)}
                      variant="ghost"
                    >
                      <Unplug size={16} /> Revogar
                    </Button>
                  </div>
                ) : null}
              </div>
            ))}
          </Card>
        </div>
      ) : null}
    </div>
  );
}
