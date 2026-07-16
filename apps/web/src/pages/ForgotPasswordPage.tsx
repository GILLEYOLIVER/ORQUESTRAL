import { ArrowLeft, Mail } from "lucide-react";
import { Link } from "react-router-dom";
import { Alert, Card } from "@orkestral/ui-components";

export function ForgotPasswordPage() {
  return (
    <div className="simple-page">
      <Card className="simple-card">
        <Mail aria-hidden="true" className="simple-card__icon" />
        <span className="eyebrow">Recuperação de acesso</span>
        <h1>Redefinição de senha</h1>
        <Alert>
          Este fluxo será ativado junto com a autenticação segura na Fase 2.
        </Alert>
        <Link className="back-link back-link--dark" to="/login">
          <ArrowLeft size={17} />
          Voltar para o login
        </Link>
      </Card>
    </div>
  );
}
