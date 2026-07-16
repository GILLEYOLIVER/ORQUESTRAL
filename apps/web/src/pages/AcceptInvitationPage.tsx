import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { UserPlus } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link, useSearchParams } from "react-router-dom";
import { z } from "zod";
import type { MessageResponse } from "@orkestral/shared-types";
import { Alert, Button, Card, TextField } from "@orkestral/ui-components";
import { ApiClientError, request } from "../lib/http";

const schema = z
  .object({
    name: z.string().min(2, "Informe seu nome."),
    password: z.string().min(12, "Use pelo menos 12 caracteres."),
    confirmation: z.string(),
  })
  .refine((values) => values.password === values.confirmation, {
    message: "As senhas não coincidem.",
    path: ["confirmation"],
  });
type FormValues = z.infer<typeof schema>;

export function AcceptInvitationPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const submit = async (values: FormValues) => {
    setError(null);
    try {
      const response = await request<MessageResponse>(
        "/auth/accept-invitation",
        {
          method: "POST",
          authenticated: false,
          body: { token, name: values.name, password: values.password },
        },
      );
      setMessage(response.message);
    } catch (caught) {
      setError(
        caught instanceof ApiClientError
          ? caught.message
          : "Falha ao aceitar o convite.",
      );
    }
  };

  return (
    <div className="simple-page">
      <Card className="simple-card">
        <UserPlus aria-hidden="true" className="simple-card__icon" />
        <span className="eyebrow">Convite</span>
        <h1>Ative seu acesso</h1>
        {!token ? (
          <Alert variant="error">Token de convite ausente.</Alert>
        ) : null}
        {message ? (
          <Alert variant="success">
            {message} <Link to="/login">Entrar agora</Link>
          </Alert>
        ) : null}
        {error ? <Alert variant="error">{error}</Alert> : null}
        <form noValidate onSubmit={(event) => void handleSubmit(submit)(event)}>
          <TextField
            error={errors.name?.message}
            label="Nome"
            {...register("name")}
          />
          <TextField
            autoComplete="new-password"
            error={errors.password?.message}
            label="Senha"
            type="password"
            {...register("password")}
          />
          <TextField
            autoComplete="new-password"
            error={errors.confirmation?.message}
            label="Confirme a senha"
            type="password"
            {...register("confirmation")}
          />
          <Button disabled={!token} loading={isSubmitting} type="submit">
            Ativar acesso
          </Button>
        </form>
      </Card>
    </div>
  );
}
