import { useMemo, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { History, Plus, Save, ShieldCheck, Trash2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type {
  AuditEventResponse,
  PermissionResponse,
  RoleResponse,
} from "@orkestral/shared-types";
import { Alert, Button, Card, TextField } from "@orkestral/ui-components";
import { PermissionGuard } from "../components/PermissionGuard";
import { ApiClientError, request } from "../lib/http";

const schema = z.object({
  name: z.string().min(2, "Informe o nome do papel."),
  description: z.string().max(500, "Use no máximo 500 caracteres."),
  permission_codes: z.array(z.string()),
});
type FormValues = z.infer<typeof schema>;

const moduleLabels: Record<string, string> = {
  users: "Usuários",
  roles: "Papéis e permissões",
  modules: "Módulos",
  crm: "CRM",
  agents: "Agentes",
  workflows: "Workflows",
  events: "Eventos empresariais",
  integrations: "Integrações",
  billing: "Faturamento",
};

function errorMessage(caught: unknown, fallback: string) {
  return caught instanceof ApiClientError ? caught.message : fallback;
}

export function RolesPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<RoleResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    defaultValues: { name: "", description: "", permission_codes: [] },
    resolver: zodResolver(schema),
  });
  const roles = useQuery({
    queryKey: ["authorization-roles"],
    queryFn: () => request<RoleResponse[]>("/authorization/roles"),
  });
  const permissions = useQuery({
    queryKey: ["authorization-permissions"],
    queryFn: () => request<PermissionResponse[]>("/authorization/permissions"),
  });
  const audit = useQuery({
    queryKey: ["authorization-audit"],
    queryFn: () => request<AuditEventResponse[]>("/authorization/audit-events"),
  });
  const permissionGroups = useMemo(() => {
    const groups = new Map<string, PermissionResponse[]>();
    for (const permission of permissions.data ?? []) {
      groups.set(permission.module_code, [
        ...(groups.get(permission.module_code) ?? []),
        permission,
      ]);
    }
    return [...groups.entries()];
  }, [permissions.data]);

  const save = useMutation({
    mutationFn: (values: FormValues) =>
      request<RoleResponse>(
        editing ? `/authorization/roles/${editing.id}` : "/authorization/roles",
        {
          method: editing ? "PATCH" : "POST",
          body: values,
        },
      ),
    onSuccess: async () => {
      setEditing(null);
      setError(null);
      reset({ name: "", description: "", permission_codes: [] });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["authorization-roles"] }),
        queryClient.invalidateQueries({ queryKey: ["authorization-audit"] }),
      ]);
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Falha ao salvar o papel.")),
  });
  const remove = useMutation({
    mutationFn: (roleId: string) =>
      request<void>(`/authorization/roles/${roleId}`, { method: "DELETE" }),
    onSuccess: async () => {
      setError(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["authorization-roles"] }),
        queryClient.invalidateQueries({ queryKey: ["authorization-audit"] }),
      ]);
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Falha ao excluir o papel.")),
  });

  const beginEdit = (role: RoleResponse) => {
    if (role.is_system_role) return;
    setEditing(role);
    reset({
      name: role.name,
      description: role.description ?? "",
      permission_codes: role.permission_codes,
    });
  };

  return (
    <div className="management-page">
      <div className="dashboard__heading">
        <div>
          <span className="eyebrow">Autorização</span>
          <h1>Papéis e permissões</h1>
          <p>
            Defina exatamente o que cada integrante pode fazer na empresa atual.
          </p>
        </div>
      </div>
      {error ? <Alert variant="error">{error}</Alert> : null}
      <div className="roles-layout">
        <PermissionGuard all={[editing ? "roles.update" : "roles.create"]}>
          <Card eyebrow={editing ? "Editar papel" : "Novo papel"}>
            <form
              className="stack-form"
              noValidate
              onSubmit={(event) =>
                void handleSubmit((values) => save.mutate(values))(event)
              }
            >
              <TextField
                error={errors.name?.message}
                label="Nome"
                {...register("name")}
              />
              <TextField
                error={errors.description?.message}
                label="Descrição"
                {...register("description")}
              />
              <fieldset className="permission-fieldset">
                <legend>Permissões do papel</legend>
                {permissionGroups.map(([moduleCode, items]) => (
                  <section className="permission-group" key={moduleCode}>
                    <strong>{moduleLabels[moduleCode] ?? moduleCode}</strong>
                    {items.map((permission) => (
                      <label className="check-row" key={permission.id}>
                        <input
                          type="checkbox"
                          value={permission.code}
                          {...register("permission_codes")}
                        />
                        <span>
                          {permission.description}
                          <small>{permission.code}</small>
                        </span>
                      </label>
                    ))}
                  </section>
                ))}
              </fieldset>
              <div className="form-actions">
                <Button loading={save.isPending} type="submit">
                  {editing ? <Save size={17} /> : <Plus size={17} />}
                  {editing ? "Salvar alterações" : "Criar papel"}
                </Button>
                {editing ? (
                  <Button
                    onClick={() => {
                      setEditing(null);
                      reset({
                        name: "",
                        description: "",
                        permission_codes: [],
                      });
                    }}
                    type="button"
                    variant="ghost"
                  >
                    Cancelar
                  </Button>
                ) : null}
              </div>
            </form>
          </Card>
        </PermissionGuard>
        <Card className="management-list" eyebrow="Papéis da empresa">
          {roles.isLoading ? <p>Carregando papéis…</p> : null}
          {roles.isError ? (
            <Alert variant="error">Não foi possível carregar os papéis.</Alert>
          ) : null}
          {roles.data?.map((role) => (
            <article className="role-row" key={role.id}>
              <ShieldCheck aria-hidden="true" />
              <button
                className="role-row__main"
                disabled={role.is_system_role}
                onClick={() => beginEdit(role)}
                type="button"
              >
                <strong>{role.name}</strong>
                <span>{role.description ?? "Sem descrição"}</span>
                <small>{role.permission_codes.length} permissões</small>
              </button>
              {role.is_system_role ? (
                <span className="status-chip">sistema</span>
              ) : (
                <PermissionGuard all={["roles.delete"]}>
                  <Button
                    aria-label={`Excluir ${role.name}`}
                    onClick={() => remove.mutate(role.id)}
                    variant="ghost"
                  >
                    <Trash2 size={16} />
                  </Button>
                </PermissionGuard>
              )}
            </article>
          ))}
        </Card>
      </div>
      <Card className="audit-card" eyebrow="Auditoria recente">
        {audit.data?.length ? (
          audit.data.slice(0, 12).map((event) => (
            <article className="audit-row" key={event.id}>
              <History aria-hidden="true" size={17} />
              <div>
                <strong>{event.action}</strong>
                <span>
                  {event.target_type} ·{" "}
                  {new Date(event.created_at).toLocaleString("pt-BR")}
                </span>
              </div>
            </article>
          ))
        ) : (
          <p>Nenhuma alteração de autorização registrada.</p>
        )}
      </Card>
    </div>
  );
}
