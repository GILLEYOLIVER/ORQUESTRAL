import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserPlus, UsersRound } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import type {
  CompanyUserResponse,
  InvitationResponse,
} from "@orkestral/shared-types";
import { Alert, Button, Card, TextField } from "@orkestral/ui-components";
import { ApiClientError, request } from "../lib/http";
import { useSession } from "../session/context";

const schema = z.object({
  name: z.string().min(2, "Informe o nome."),
  email: z.email("Informe um e-mail válido."),
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
  const canManage = me?.permissions.includes("company:manage_users") ?? false;
  const users = useQuery({
    queryKey: ["company-users", me?.current_company?.id],
    queryFn: () => request<CompanyUserResponse[]>("/company/users"),
    enabled: canManage,
  });
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

  if (!canManage) {
    return (
      <Alert variant="error">Acesso restrito ao proprietário da empresa.</Alert>
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
            <Button loading={invite.isPending} type="submit">
              <UserPlus size={17} /> Enviar convite
            </Button>
          </form>
        </Card>
        <Card className="management-list" eyebrow="Membros">
          {users.isLoading ? <p>Carregando usuários…</p> : null}
          {users.data?.map((member) => (
            <article className="management-row" key={member.membership_id}>
              <UsersRound aria-hidden="true" />
              <div>
                <strong>{member.name}</strong>
                <span>{member.email}</span>
              </div>
              <span
                className={`status-chip status-chip--${member.membership_status}`}
              >
                {member.is_owner ? "proprietário" : member.membership_status}
              </span>
              {!member.is_owner ? (
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
              ) : null}
            </article>
          ))}
        </Card>
      </div>
    </div>
  );
}
