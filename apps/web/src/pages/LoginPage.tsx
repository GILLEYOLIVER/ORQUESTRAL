import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Link2, LockKeyhole, ShieldCheck, X } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router";
import { z } from "zod";
import { Alert, Button, TextField } from "@orkestral/ui-components";
import { ApiClientError, request } from "../lib/http";
import { useSession } from "../session/context";

const loginSchema = z.object({
  email: z.email("Informe um e-mail válido."),
  password: z.string().min(1, "Informe sua senha."),
});

type LoginForm = z.infer<typeof loginSchema>;
type DevelopmentAccess = { enabled: boolean };
type LinkCandidate = {
  company_id: string;
  company_name: string;
  user_id: string;
  user_name: string;
  user_email: string;
};
type LinkAuthorization = {
  authorization_token: string;
  expires_at: string;
  candidates: LinkCandidate[];
};
type GeneratedLink = { id: string; token: string; expires_at: string };

export function LoginPage() {
  const [error, setError] = useState<string | null>(null);
  const [developmentSubmitting, setDevelopmentSubmitting] = useState(false);
  const [linkDialogOpen, setLinkDialogOpen] = useState(false);
  const [linkAuthorization, setLinkAuthorization] =
    useState<LinkAuthorization | null>(null);
  const [linkEmail, setLinkEmail] = useState("");
  const [linkPassword, setLinkPassword] = useState("");
  const [selectedCandidate, setSelectedCandidate] = useState("");
  const [expirationMinutes, setExpirationMinutes] = useState("480");
  const [generatedUrl, setGeneratedUrl] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const [linkSubmitting, setLinkSubmitting] = useState(false);
  const session = useSession();
  const navigate = useNavigate();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });
  const developmentAccess = useQuery({
    queryKey: ["development-access"],
    queryFn: () =>
      request<DevelopmentAccess>("/auth/development-access", {
        authenticated: false,
        allowAuthRefresh: false,
      }),
    retry: false,
    staleTime: 60_000,
  });

  const submit = async (values: LoginForm) => {
    setError(null);
    try {
      const profile = await session.login(values.email, values.password);
      await navigate(
        profile.requires_company_selection ? "/selecionar-empresa" : "/app",
        { replace: true },
      );
    } catch (caught) {
      setError(
        caught instanceof ApiClientError
          ? caught.message
          : "Não foi possível entrar.",
      );
    }
  };

  const accessAsAdministrator = async () => {
    setError(null);
    setDevelopmentSubmitting(true);
    try {
      const profile = await session.developmentLogin();
      await navigate(
        profile.requires_company_selection ? "/selecionar-empresa" : "/app",
        { replace: true },
      );
    } catch (caught) {
      setError(
        caught instanceof ApiClientError
          ? caught.message
          : "Não foi possível acessar o ambiente local.",
      );
    } finally {
      setDevelopmentSubmitting(false);
    }
  };

  const closeLinkDialog = () => {
    setLinkDialogOpen(false);
    setLinkAuthorization(null);
    setLinkPassword("");
    setSelectedCandidate("");
    setGeneratedUrl("");
    setLinkError(null);
  };

  const authorizeLinkGeneration = async (event: React.FormEvent) => {
    event.preventDefault();
    setLinkError(null);
    setLinkSubmitting(true);
    try {
      const authorization = await request<LinkAuthorization>(
        "/auth/read-only-links/authorize",
        {
          method: "POST",
          authenticated: false,
          allowAuthRefresh: false,
          body: { email: linkEmail, password: linkPassword },
        },
      );
      setLinkAuthorization(authorization);
      const first = authorization.candidates[0];
      setSelectedCandidate(first ? `${first.company_id}:${first.user_id}` : "");
      setLinkPassword("");
    } catch (caught) {
      setLinkError(
        caught instanceof ApiClientError
          ? caught.message
          : "Não foi possível autenticar o administrador.",
      );
    } finally {
      setLinkSubmitting(false);
    }
  };

  const generateReadOnlyLink = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!linkAuthorization || !selectedCandidate) return;
    const [companyId, userId] = selectedCandidate.split(":");
    setLinkError(null);
    setLinkSubmitting(true);
    try {
      const generated = await request<GeneratedLink>("/auth/read-only-links", {
        method: "POST",
        authenticated: false,
        allowAuthRefresh: false,
        headers: {
          "X-Read-Only-Link-Authorization":
            linkAuthorization.authorization_token,
        },
        body: {
          company_id: companyId,
          target_user_id: userId,
          expiration_minutes: Number(expirationMinutes),
        },
      });
      setGeneratedUrl(
        `${window.location.origin}/acesso-socio#token=${encodeURIComponent(generated.token)}`,
      );
    } catch (caught) {
      setLinkError(
        caught instanceof ApiClientError
          ? caught.message
          : "Não foi possível gerar o link.",
      );
    } finally {
      setLinkSubmitting(false);
    }
  };

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
        <span className="auth-aside__caption">Acesso seguro multiempresa</span>
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
          {error ? (
            <Alert title="Não foi possível entrar" variant="error">
              {error}
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
            <Button
              className="auth-card__submit"
              loading={isSubmitting}
              type="submit"
            >
              Continuar
            </Button>
          </form>
          {developmentAccess.data?.enabled ? (
            <Button
              className="auth-card__submit"
              loading={developmentSubmitting}
              onClick={() => void accessAsAdministrator()}
              type="button"
            >
              <ShieldCheck aria-hidden="true" size={18} />
              Acessar como administrador
            </Button>
          ) : null}
          <button
            className="auth-card__link-generator"
            onClick={() => setLinkDialogOpen(true)}
            type="button"
          >
            <Link2 aria-hidden="true" size={15} />
            Gerar link de acesso
          </button>
          <p className="auth-card__footnote">
            A Orkestral não armazena tokens no armazenamento do navegador.
          </p>
        </div>
        {linkDialogOpen ? (
          <div className="secure-link-overlay">
            <section
              aria-labelledby="secure-link-title"
              aria-modal="true"
              className="secure-link-dialog"
              role="dialog"
            >
              <button
                aria-label="Fechar"
                className="secure-link-dialog__close"
                onClick={closeLinkDialog}
                type="button"
              >
                <X size={18} />
              </button>
              <span className="eyebrow">Acesso de sócios</span>
              <h2 id="secure-link-title">
                {generatedUrl
                  ? "Link seguro criado"
                  : linkAuthorization
                    ? "Defina o acesso somente leitura"
                    : "Confirme sua identidade de administrador"}
              </h2>
              <p>
                {linkAuthorization
                  ? "O usuário verá a mesma plataforma, mas toda alteração será bloqueada pelo servidor."
                  : "Nenhum link pode ser criado sem autenticação administrativa."}
              </p>
              {linkError ? <Alert variant="error">{linkError}</Alert> : null}
              {generatedUrl ? (
                <div className="secure-link-result">
                  <label htmlFor="generated-read-only-link">
                    Link de acesso
                  </label>
                  <input
                    id="generated-read-only-link"
                    readOnly
                    value={generatedUrl}
                  />
                  <Button
                    onClick={() =>
                      void navigator.clipboard.writeText(generatedUrl)
                    }
                    type="button"
                  >
                    Copiar link
                  </Button>
                </div>
              ) : linkAuthorization ? (
                <form onSubmit={(event) => void generateReadOnlyLink(event)}>
                  <label htmlFor="read-only-user">Usuário</label>
                  <select
                    id="read-only-user"
                    onChange={(event) =>
                      setSelectedCandidate(event.target.value)
                    }
                    required
                    value={selectedCandidate}
                  >
                    {linkAuthorization.candidates.map((candidate) => (
                      <option
                        key={`${candidate.company_id}:${candidate.user_id}`}
                        value={`${candidate.company_id}:${candidate.user_id}`}
                      >
                        {candidate.user_name} · {candidate.company_name} ·{" "}
                        {candidate.user_email}
                      </option>
                    ))}
                  </select>
                  <label htmlFor="read-only-expiration">Expiração</label>
                  <select
                    id="read-only-expiration"
                    onChange={(event) =>
                      setExpirationMinutes(event.target.value)
                    }
                    value={expirationMinutes}
                  >
                    <option value="60">1 hora</option>
                    <option value="480">8 horas</option>
                    <option value="1440">1 dia</option>
                    <option value="10080">7 dias</option>
                    <option value="43200">30 dias</option>
                  </select>
                  <Button loading={linkSubmitting} type="submit">
                    Gerar token seguro
                  </Button>
                </form>
              ) : (
                <form onSubmit={(event) => void authorizeLinkGeneration(event)}>
                  <TextField
                    autoComplete="email"
                    label="E-mail do administrador"
                    onChange={(event) => setLinkEmail(event.target.value)}
                    required
                    type="email"
                    value={linkEmail}
                  />
                  <TextField
                    autoComplete="current-password"
                    label="Senha do administrador"
                    onChange={(event) => setLinkPassword(event.target.value)}
                    required
                    type="password"
                    value={linkPassword}
                  />
                  <Button loading={linkSubmitting} type="submit">
                    Autenticar administrador
                  </Button>
                </form>
              )}
            </section>
          </div>
        ) : null}
      </section>
    </div>
  );
}
