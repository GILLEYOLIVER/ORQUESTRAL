import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserPlus, UsersRound } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";
import type {
  CompanyUserResponse,
  InvitationResponse,
  RoleResponse,
} from "@orkestral/shared-types";
import { Alert, Button, Card, TextField } from "@orkestral/ui-components";
import { PermissionGuard } from "../components/PermissionGuard";
import { ApiClientError, request } from "../lib/http";
import { useSession } from "../session/context";

const schema = z.object({
  name: z.string().min(2, "Informe o nome."),
  email: z.email("Informe um e-mail válido."),
  role_id: z.uuid("Selecione um papel."),
});
type FormValues = z.infer<typeof schema>;

export function CompanyUsersPage() {
  const { me } = useSession();
  const queryClient = useQueryClient();
  const [invitation, setInvitation] = useState<InvitationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });
  const canView = me?.permissions.includes("users.view") ?? false;
  const canViewRoles = me?.permissions.includes("roles.view") ?? false;
  const canUpdate = me?.permissions.includes("users.update") ?? false;
  const users = useQuery({
    queryKey: ["company-users", me?.current_company?.id],
    queryFn: () => request<CompanyUserResponse[]>("/company/users"),
    enabled: canView,
  });
  const roles = useQuery({
    queryKey: ["authorization-roles"],
    queryFn: () => request<RoleResponse[]>("/authorization/roles"),
    enabled: canViewRoles,
  });
  const assignableRoles =
    roles.data?.filter(
      (role) => !(role.is_system_role && role.name === "Proprietário"),
    ) ?? [];
  const invite = useMutation({
    mutationFn: (values: FormValues) =>
      request<InvitationResponse>("/company/invitations", {
        method: "POST",
        body: values,
      }),
    onSuccess: async (result) => {
      setInvitation(result);
      setError(null);
      reset();
      await queryClient.invalidateQueries({ queryKey: ["company-users"] });
    },
    onError: (caught) =>
      setError(
        caught instanceof ApiClientError
          ? caught.message
          : "Falha ao convidar usuário.",
      ),
  });
  const changeStatus = useMutation({
    mutationFn: ({
      userId,
      status,
    }: {
      userId: string;
      status: "active" | "disabled";
    }) =>
      request<CompanyUserResponse>(`/company/users/${userId}`, {
        method: "PATCH",
        body: { status },
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["company-users"] }),
  });
  const assignRole = useMutation({
    mutationFn: ({ userId, roleId }: { userId: string; roleId: string }) =>
      request<CompanyUserResponse>(`/company/users/${userId}`, {
        method: "PATCH",
        body: { role_id: roleId },
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["company-users"] }),
    onError: (caught) =>
      setError(
        caught instanceof ApiClientError
          ? caught.message
          : "Falha ao alterar o papel.",
      ),
  });

  if (!canView) {
    return (
      <Alert variant="error">
        Você não possui permissão para visualizar usuários.
      </Alert>
    );
  }
  return (
    <div className="management-page">
      <div className="dashboard__heading">
        <div>
          <span className="eyebrow">Equipe</span>
          <h1>Usuários da empresa</h1>
          <p>Convide pessoas e controle o acesso ao tenant atual.</p>
        </div>
      </div>
      {invitation?.development_token ? (
        <Alert
          title="Convite criado no modo de desenvolvimento"
          variant="success"
        >
          <Link to={`/aceitar-convite?token=${invitation.development_token}`}>
            Abrir link de ativação de {invitation.email}
          </Link>
        </Alert>
      ) : null}
      <div className="management-grid">
        <PermissionGuard all={["users.create", "roles.view"]}>
          <Card eyebrow="Convidar usuário">
            {error ? <Alert variant="error">{error}</Alert> : null}
            <form
              className="stack-form"
              noValidate
              onSubmit={(event) =>
                void handleSubmit((values) => invite.mutate(values))(event)
              }
            >
              <TextField
                error={errors.name?.message}
                label="Nome"
                {...register("name")}
              />
              <TextField
                error={errors.email?.message}
                label="E-mail"
                type="email"
                {...register("email")}
              />
              <label className="native-field">
                <span>Papel inicial</span>
                <select
                  aria-invalid={Boolean(errors.role_id)}
                  {...register("role_id")}
                >
                  <option value="">Selecione um papel</option>
                  {assignableRoles.map((role) => (
                    <option key={role.id} value={role.id}>
                      {role.name}
                    </option>
                  ))}
                </select>
                {errors.role_id ? (
                  <small role="alert">{errors.role_id.message}</small>
                ) : null}
              </label>
              <Button loading={invite.isPending} type="submit">
                <UserPlus size={17} /> Enviar convite
              </Button>
            </form>
          </Card>
        </PermissionGuard>
        <Card className="management-list" eyebrow="Membros">
          {users.isLoading ? <p>Carregando usuários…</p> : null}
          {users.data?.map((member) => (
            <article className="management-row" key={member.membership_id}>
              <UsersRound aria-hidden="true" />
              <div>
                <strong>{member.name}</strong>
                <span>
                  {member.email} · {member.role_name ?? "Sem papel"}
                </span>
              </div>
              <span
                className={`status-chip status-chip--${member.membership_status}`}
              >
                {member.is_owner ? "proprietário" : member.membership_status}
              </span>
              {!member.is_owner && canUpdate ? (
                <div className="member-actions">
                  <PermissionGuard all={["roles.view"]}>
                    <select
                      aria-label={`Papel de ${member.name}`}
                      onChange={(event) =>
                        assignRole.mutate({
                          userId: member.user_id,
                          roleId: event.target.value,
                        })
                      }
                      value={member.role_id ?? ""}
                    >
                      {assignableRoles.map((role) => (
                        <option key={role.id} value={role.id}>
                          {role.name}
                        </option>
                      ))}
                    </select>
                  </PermissionGuard>
                  <Button
                    onClick={() =>
                      changeStatus.mutate({
                        userId: member.user_id,
                        status:
                          member.membership_status === "disabled"
                            ? "active"
                            : "disabled",
                      })
                    }
                    variant="ghost"
                  >
                    {member.membership_status === "disabled"
                      ? "Ativar"
                      : "Desabilitar"}
                  </Button>
                </div>
              ) : null}
            </article>
          ))}
        </Card>
      </div>
    </div>
  );
}
