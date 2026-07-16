import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, LockKeyhole } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import { Alert, Button, TextField } from "@orkestral/ui-components";

const loginSchema = z.object({
  email: z.email("Informe um e-mail válido."),
  password: z.string().min(1, "Informe sua senha."),
});

type LoginForm = z.infer<typeof loginSchema>;

export function LoginPage() {
  const [notice, setNotice] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const submit = () => setNotice(true);

  return (
    <div className="auth-page">
      <section className="auth-aside">
        <Link className="back-link" to="/">
          <ArrowLeft size={17} />
          Voltar ao início
        </Link>
        <div>
          <span className="eyebrow eyebrow--light">Orkestral</span>
          <h1>Seu centro de operações inteligentes.</h1>
          <p>Uma base segura para conectar pessoas, processos e tecnologia.</p>
        </div>
        <span className="auth-aside__caption">Ambiente inicial · Fase 1</span>
      </section>
      <section className="auth-content" aria-labelledby="login-title">
        <div className="auth-card">
          <div className="auth-card__icon">
            <LockKeyhole aria-hidden="true" />
          </div>
          <span className="eyebrow">Acesso seguro</span>
          <h1 id="login-title">Entrar na Orkestral</h1>
          <p className="auth-card__lead">
            Use suas credenciais empresariais para continuar.
          </p>
          {notice ? (
            <Alert title="Acesso ainda não habilitado">
              A autenticação real será disponibilizada na Fase 2. Nenhuma
              credencial foi enviada ou armazenada.
            </Alert>
          ) : null}
          <form
            noValidate
            onSubmit={(event) => void handleSubmit(submit)(event)}
          >
            <TextField
              autoComplete="email"
              error={errors.email?.message}
              label="E-mail corporativo"
              placeholder="voce@empresa.com.br"
              type="email"
              {...register("email")}
            />
            <TextField
              autoComplete="current-password"
              error={errors.password?.message}
              label="Senha"
              type="password"
              {...register("password")}
            />
            <div className="auth-card__row">
              <span>Ambiente protegido</span>
              <Link to="/esqueci-minha-senha">Esqueci minha senha</Link>
            </div>
            <Button className="auth-card__submit" type="submit">
              Continuar
            </Button>
          </form>
          <p className="auth-card__footnote">
            A Orkestral não armazena tokens no armazenamento do navegador.
          </p>
        </div>
      </section>
    </div>
  );
}
