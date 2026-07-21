import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  CheckCircle2,
  Download,
  PackageCheck,
  Rocket,
  Upload,
} from "lucide-react";
import { Alert, Button, Card } from "@orkestral/ui-components";
import { ApiClientError, request } from "../lib/http";

type Environment =
  "local" | "testing" | "development" | "staging" | "production";
type ReleaseStatus = "draft" | "validated" | "published" | "retired";
type PackageRelease = {
  id: string;
  package_key: string;
  display_name: string;
  version: string;
  status: ReleaseStatus;
  source_environment: Environment;
  checksum: string;
};
type ReleaseBundle = {
  format_version: "2.0";
  created_at: string;
  manifest: {
    package_key: string;
    display_name: string;
    version: string;
    source_environment: Environment;
    dependencies: Array<{
      package_key: string;
      version: string;
      optional: boolean;
    }>;
  };
  artifact: unknown;
  checksum: string;
};
type InstallPreview = {
  can_install: boolean;
  package_key: string;
  version: string;
  actions: string[];
  blockers: string[];
  plan_checksum: string;
};
type SystemVersion = { environment: Environment };

function errorMessage(error: unknown) {
  return error instanceof ApiClientError
    ? error.message
    : "Não foi possível concluir a operação com o pacote.";
}

function downloadJson(filename: string, content: unknown) {
  const blob = new Blob([JSON.stringify(content, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function nextEnvironment(environment: Environment): Environment | null {
  const targets: Partial<Record<Environment, Environment>> = {
    local: "development",
    testing: "development",
    development: "staging",
    staging: "production",
  };
  return targets[environment] ?? null;
}

export function MetadataPackageLifecycle({
  definitionId,
  entityKey,
  publishedVersion,
  canPublish,
}: {
  definitionId: string | null;
  entityKey: string | null;
  publishedVersion: number | null;
  canPublish: boolean;
}) {
  const queryClient = useQueryClient();
  const [version, setVersion] = useState("1.0.0");
  const [bundle, setBundle] = useState<ReleaseBundle | null>(null);
  const [preview, setPreview] = useState<InstallPreview | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const system = useQuery({
    queryKey: ["system-version"],
    queryFn: () => request<SystemVersion>("/system/version"),
  });
  const releases = useQuery({
    queryKey: ["metadata-package-releases", definitionId],
    enabled: Boolean(definitionId),
    queryFn: () =>
      request<PackageRelease[]>(
        `/metadata/packages/releases?definition_id=${definitionId}`,
      ),
  });
  const refresh = () => {
    void queryClient.invalidateQueries({
      queryKey: ["metadata-package-releases"],
    });
    void queryClient.invalidateQueries({ queryKey: ["metadata-entities"] });
  };
  const createRelease = useMutation({
    mutationFn: () =>
      request<PackageRelease>("/metadata/packages/releases", {
        method: "POST",
        body: { definition_id: definitionId, version, dependencies: [] },
      }),
    onSuccess: refresh,
  });
  const validateRelease = useMutation({
    mutationFn: (id: string) =>
      request(`/metadata/packages/releases/${id}/validate`, { method: "POST" }),
    onSuccess: refresh,
  });
  const publishRelease = useMutation({
    mutationFn: (id: string) =>
      request(`/metadata/packages/releases/${id}/publish`, { method: "POST" }),
    onSuccess: refresh,
  });
  const exportRelease = useMutation({
    mutationFn: (release: PackageRelease) =>
      request<ReleaseBundle>(
        `/metadata/packages/releases/${release.id}/bundle`,
      ).then((content) => ({ content, release })),
    onSuccess: ({ content, release }) =>
      downloadJson(
        `${release.package_key}-${release.version}.orkestral-release.json`,
        content,
      ),
  });
  const promotion = useMutation({
    mutationFn: ({
      release,
      target,
    }: {
      release: PackageRelease;
      target: Environment;
    }) =>
      request<{ allowed: boolean; bundle: ReleaseBundle | null }>(
        `/metadata/packages/releases/${release.id}/promotion`,
        { method: "POST", body: { target_environment: target } },
      ).then((result) => ({ result, release, target })),
    onSuccess: ({ result, release, target }) => {
      if (result.allowed && result.bundle) {
        downloadJson(
          `${release.package_key}-${release.version}-para-${target}.orkestral-release.json`,
          result.bundle,
        );
      }
    },
  });
  const previewInstall = useMutation({
    mutationFn: (selected: ReleaseBundle) =>
      request<InstallPreview>("/metadata/packages/installations/preview", {
        method: "POST",
        body: {
          bundle: selected,
          target_environment: system.data?.environment ?? "local",
        },
      }),
    onSuccess: setPreview,
  });
  const install = useMutation({
    mutationFn: () =>
      request("/metadata/packages/installations", {
        method: "POST",
        body: {
          bundle,
          target_environment: system.data?.environment ?? "local",
          plan_checksum: preview?.plan_checksum,
        },
      }),
    onSuccess: () => {
      setBundle(null);
      setPreview(null);
      refresh();
    },
  });
  const operationError =
    createRelease.error ??
    validateRelease.error ??
    publishRelease.error ??
    exportRelease.error ??
    promotion.error ??
    previewInstall.error ??
    install.error;
  const target = system.data ? nextEnvironment(system.data.environment) : null;

  return (
    <Card className="metadata-package-lifecycle">
      <div className="metadata-card-heading">
        <div>
          <span className="eyebrow">Distribuição controlada</span>
          <h2>Versões e implantação de pacotes</h2>
          <p>
            Valide dependências, simule alterações e promova somente artefatos
            íntegros.
          </p>
        </div>
        <PackageCheck size={28} />
      </div>
      {operationError || fileError ? (
        <Alert variant="error">
          {fileError ?? errorMessage(operationError)}
        </Alert>
      ) : null}
      <div className="metadata-package-columns">
        <section>
          <h3>Releases desta entidade</h3>
          {definitionId && publishedVersion ? (
            <div className="metadata-package-create">
              <label>
                <span>Nova versão SemVer</span>
                <input
                  aria-label="Nova versão SemVer"
                  onChange={(event) => setVersion(event.target.value)}
                  value={version}
                />
              </label>
              <Button
                loading={createRelease.isPending}
                onClick={() => createRelease.mutate()}
              >
                <Archive size={16} /> Criar release
              </Button>
            </div>
          ) : (
            <p className="metadata-package-empty">
              {definitionId
                ? "Publique a entidade para liberar releases."
                : "Selecione uma entidade para gerenciar suas releases."}
            </p>
          )}
          <div className="metadata-release-list">
            {(releases.data ?? []).map((release) => (
              <article key={release.id}>
                <div>
                  <strong>{release.display_name}</strong>
                  <span>
                    {release.package_key}@{release.version} · {release.status}
                  </span>
                  <small>
                    {release.checksum.slice(0, 12)} ·{" "}
                    {release.source_environment}
                  </small>
                </div>
                <div className="metadata-release-actions">
                  {release.status === "draft" ? (
                    <button
                      onClick={() => validateRelease.mutate(release.id)}
                      type="button"
                    >
                      <CheckCircle2 size={15} /> Validar
                    </button>
                  ) : null}
                  {release.status === "validated" && canPublish ? (
                    <button
                      onClick={() => publishRelease.mutate(release.id)}
                      type="button"
                    >
                      <Rocket size={15} /> Publicar
                    </button>
                  ) : null}
                  {release.status === "published" ? (
                    <button
                      onClick={() => exportRelease.mutate(release)}
                      type="button"
                    >
                      <Download size={15} /> Bundle
                    </button>
                  ) : null}
                  {release.status === "published" && target && canPublish ? (
                    <button
                      onClick={() => promotion.mutate({ release, target })}
                      type="button"
                    >
                      <Rocket size={15} /> Promover para {target}
                    </button>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        </section>
        <section>
          <h3>Instalação com prévia obrigatória</h3>
          <label className="metadata-package-upload">
            <Upload size={20} /> Selecionar bundle 2.0
            <input
              accept="application/json,.json"
              onChange={async (event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                try {
                  const parsed = JSON.parse(await file.text()) as ReleaseBundle;
                  setBundle(parsed);
                  setPreview(null);
                  setFileError(null);
                  previewInstall.mutate(parsed);
                } catch {
                  setFileError(
                    "O arquivo selecionado não contém um bundle JSON válido.",
                  );
                }
                event.target.value = "";
              }}
              type="file"
            />
          </label>
          {preview ? (
            <div
              className={
                preview.can_install
                  ? "metadata-install-plan ready"
                  : "metadata-install-plan blocked"
              }
            >
              <strong>
                {preview.package_key}@{preview.version}
              </strong>
              <span>
                {preview.can_install
                  ? "Pronto para instalar"
                  : "Instalação bloqueada"}
              </span>
              <ul>
                {(preview.blockers.length
                  ? preview.blockers
                  : preview.actions
                ).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              {preview.can_install ? (
                <Button
                  loading={install.isPending}
                  onClick={() => install.mutate()}
                >
                  <PackageCheck size={16} /> Confirmar instalação
                </Button>
              ) : null}
            </div>
          ) : (
            <p className="metadata-package-empty">
              O sistema não altera dados antes de mostrar todas as ações e
              bloqueios.
            </p>
          )}
        </section>
      </div>
      {entityKey ? (
        <small className="metadata-package-context">
          Contexto atual: {entityKey}
        </small>
      ) : null}
    </Card>
  );
}
