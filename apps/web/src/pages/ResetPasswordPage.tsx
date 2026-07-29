import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { KeyRound } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link, useSearchParams } from "react-router";
import { z } from "zod";
import type { MessageResponse } from "@orkestral/shared-types";
import { Alert, Button, Card, TextField } from "@orkestral/ui-components";
import { ApiClientError, request } from "../lib/http";

const schema = z
  .object({
    password: z.string().min(12, "Use pelo menos 12 caracteres."),
    confirmation: z.string(),
  })
  .refine((values) => values.password === values.confirmation, {
    message: "As senhas não coincidem.",
    path: ["confirmation"],
  });
type FormValues = z.infer<typeof schema>;

export function ResetPasswordPage() {
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
      const response = await request<MessageResponse>("/auth/reset-password", {
        method: "POST",
        authenticated: false,
        body: { token, password: values.password },
      });
      setMessage(response.message);
    } catch (caught) {
      setError(
        caught instanceof ApiClientError
          ? caught.message
          : "Falha ao redefinir a senha.",
      );
    }
  };

  return (
    <div className="simple-page">
      <Card className="simple-card">
        <KeyRound aria-hidden="true" className="simple-card__icon" />
        <span className="eyebrow">Segurança</span>
        <h1>Crie uma nova senha</h1>
        {!token ? (
          <Alert variant="error">Token de recuperação ausente.</Alert>
        ) : null}
        {message ? (
          <Alert variant="success">
            {message} <Link to="/login">Ir para o login</Link>
          </Alert>
        ) : null}
        {error ? <Alert variant="error">{error}</Alert> : null}
        <form noValidate onSubmit={(event) => void handleSubmit(submit)(event)}>
          <TextField
            autoComplete="new-password"
            error={errors.password?.message}
            hint="12 caracteres, maiúscula, minúscula, número e símbolo."
            label="Nova senha"
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
            Redefinir senha
          </Button>
        </form>
      </Card>
    </div>
  );
}
