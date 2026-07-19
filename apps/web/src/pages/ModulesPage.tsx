import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Boxes, CheckCircle2, Clock3, Power } from "lucide-react";
import type { ModuleResponse } from "@orkestral/shared-types";
import { Alert, Button, Card } from "@orkestral/ui-components";
import { PermissionGuard } from "../components/PermissionGuard";
import { ApiClientError, request } from "../lib/http";
import { useModules } from "../modules/useModules";

export function ModulesPage() {
  const queryClient = useQueryClient();
  const modules = useModules();
  const toggle = useMutation({
    mutationFn: (module: ModuleResponse) =>
      request<ModuleResponse>(`/modules/${module.code}`, {
        method: "PATCH",
        body: {
          status: module.company_status === "active" ? "inactive" : "active",
        },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["modules"] }),
  });

  return (
    <div className="management-page">
      <div className="dashboard__heading">
        <div>
          <span className="eyebrow">Núcleo modular</span>
          <h1>Módulos da empresa</h1>
          <p>
            Ative apenas as capacidades necessárias para a operação deste
            tenant.
          </p>
        </div>
      </div>
      {modules.isError ? (
        <Alert variant="error">
          Não foi possível carregar o catálogo de módulos.
        </Alert>
      ) : null}
      {toggle.isError ? (
        <Alert variant="error">
          {toggle.error instanceof ApiClientError
            ? toggle.error.message
            : "Não foi possível alterar o módulo."}
        </Alert>
      ) : null}
      <div className="module-grid">
        {modules.isLoading ? <p>Carregando catálogo…</p> : null}
        {modules.data?.map((module) => {
          const active = module.company_status === "active";
          return (
            <Card className="module-card" key={module.id}>
              <div className="module-card__header">
                <span className="module-card__icon">
                  <Boxes aria-hidden="true" />
                </span>
                <span
                  className={`status-chip ${
                    active ? "status-chip--active" : "status-chip--inactive"
                  }`}
                >
                  {active ? "ativo" : module.installed ? "inativo" : "em breve"}
                </span>
              </div>
              <div>
                <span className="eyebrow">{module.category}</span>
                <h2>{module.name}</h2>
                <p>{module.description}</p>
              </div>
              <div className="module-card__meta">
                {module.installed ? (
                  <CheckCircle2 size={16} />
                ) : (
                  <Clock3 size={16} />
                )}
                <span>
                  {module.installed
                    ? `Instalado · versão ${module.version}`
                    : "Disponibilidade futura"}
                </span>
              </div>
              {module.installed ? (
                <PermissionGuard all={["modules.manage"]}>
                  <Button
                    loading={
                      toggle.isPending && toggle.variables?.id === module.id
                    }
                    onClick={() => toggle.mutate(module)}
                    variant={active ? "ghost" : "primary"}
                  >
                    <Power size={17} /> {active ? "Desativar" : "Ativar módulo"}
                  </Button>
                </PermissionGuard>
              ) : null}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
