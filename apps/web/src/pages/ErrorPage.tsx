import { AlertTriangle } from "lucide-react";
import { Link, useRouteError } from "react-router-dom";
import { Button, Card } from "@orkestral/ui-components";

export function ErrorPage() {
  const error = useRouteError();
  console.error("Falha de navegação", error);
  return (
    <div className="simple-page">
      <Card className="simple-card">
        <AlertTriangle
          aria-hidden="true"
          className="simple-card__icon simple-card__icon--error"
        />
        <span className="eyebrow">Não foi possível carregar</span>
        <h1>Ocorreu um erro inesperado</h1>
        <p>
          Tente novamente. Se o problema continuar, informe o identificador da
          solicitação ao suporte.
        </p>
        <Button onClick={() => window.location.reload()}>
          Tentar novamente
        </Button>
        <Link className="text-link" to="/">
          Ir para o início
        </Link>
      </Card>
    </div>
  );
}
