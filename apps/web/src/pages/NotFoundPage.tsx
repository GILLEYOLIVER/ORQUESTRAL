import { Compass } from "lucide-react";
import { Link } from "react-router-dom";
import { Card } from "@orkestral/ui-components";

export function NotFoundPage() {
  return (
    <div className="simple-page">
      <Card className="simple-card">
        <Compass aria-hidden="true" className="simple-card__icon" />
        <span className="eyebrow">Erro 404</span>
        <h1>Página não encontrada</h1>
        <p>O endereço informado não existe ou ainda não está disponível.</p>
        <Link className="hero__cta" to="/">
          Voltar ao início
        </Link>
      </Card>
    </div>
  );
}
