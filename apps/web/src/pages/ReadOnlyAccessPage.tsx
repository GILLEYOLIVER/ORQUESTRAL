import { useEffect, useRef, useState } from "react";
import { Eye, LockKeyhole } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Alert } from "@orkestral/ui-components";
import { ApiClientError } from "../lib/http";
import { useSession } from "../session/context";

export function ReadOnlyAccessPage() {
  const session = useSession();
  const navigate = useNavigate();
  const started = useRef(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const params = new URLSearchParams(window.location.hash.slice(1));
    const token = params.get("token");
    window.history.replaceState(null, "", "/acesso-socio");
    if (!token) {
      setError("Este link não contém um token de acesso válido.");
      return;
    }
    void session
      .loginWithReadOnlyLink(token)
      .then(() => navigate("/app", { replace: true }))
      .catch((caught) =>
        setError(
          caught instanceof ApiClientError
            ? caught.message
            : "Não foi possível validar o link de acesso.",
        ),
      );
  }, [navigate, session]);

  return (
    <div className="readonly-access-page">
      <section className="readonly-access-card">
        <div className="auth-card__icon">
          {error ? <LockKeyhole /> : <Eye />}
        </div>
        <span className="eyebrow">Acesso seguro</span>
        <h1>Administrador Somente Leitura</h1>
        {error ? (
          <Alert title="Link indisponível" variant="error">
            {error}
          </Alert>
        ) : (
          <p>
            Validando o acesso e preparando a plataforma sem permissões de
            alteração…
          </p>
        )}
      </section>
    </div>
  );
}
