import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Mail } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import type { MessageResponse } from "@orkestral/shared-types";
import { Alert, Button, Card, TextField } from "@orkestral/ui-components";
import { ApiClientError, request } from "../lib/http";

const forgotSchema = z.object({ email: z.email("Informe um e-mail válido.") });
type ForgotForm = z.infer<typeof forgotSchema>;

export function ForgotPasswordPage() {
  const [result, setResult] = useState<MessageResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotForm>({
    resolver: zodResolver(forgotSchema),
    defaultValues: { email: "" },
  });

  const submit = async (values: ForgotForm) => {
    setError(null);
    try {
      setResult(
        await request<MessageResponse>("/auth/forgot-password", {
          method: "POST",
          authenticated: false,
          body: values,
        }),
      );
    } catch (caught) {
      setError(
        caught instanceof ApiClientError
          ? caught.message
          : "Falha ao solicitar acesso.",
      );
    }
  };

  return (
    <div className="simple-page">
      <Card className="simple-card">
        <Mail aria-hidden="true" className="simple-card__icon" />
        <span className="eyebrow">Recuperação de acesso</span>
        <h1>Redefinição de senha</h1>
        <p>Informe seu e-mail para receber as instruções de redefinição.</p>
        {result ? (
          <Alert title="Solicitação registrada" variant="success">
            {result.message}
            {result.development_token ? (
              <div>
                <Link to={`/redefinir-senha?token=${result.development_token}`}>
                  Continuar no modo de desenvolvimento
                </Link>
              </div>
            ) : null}
          </Alert>
        ) : null}
        {error ? <Alert variant="error">{error}</Alert> : null}
        <form noValidate onSubmit={(event) => void handleSubmit(submit)(event)}>
          <TextField
            autoComplete="email"
            error={errors.email?.message}
            label="E-mail corporativo"
            type="email"
            {...register("email")}
          />
          <Button loading={isSubmitting} type="submit">
            Enviar instruções
          </Button>
        </form>
        <Link className="back-link back-link--dark" to="/login">
          <ArrowLeft size={17} />
          Voltar para o login
        </Link>
      </Card>
    </div>
  );
}
