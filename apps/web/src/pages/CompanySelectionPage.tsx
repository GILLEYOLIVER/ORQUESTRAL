import { Building2 } from "lucide-react";
import { Navigate } from "react-router-dom";
import { Button, Card } from "@orkestral/ui-components";
import { useSession } from "../session/context";

export function CompanySelectionPage() {
  const session = useSession();
  if (!session.me) return <Navigate replace to="/login" />;

  return (
    <div className="simple-page">
      <Card className="selection-card">
        <Building2 aria-hidden="true" className="simple-card__icon" />
        <span className="eyebrow">Contexto de trabalho</span>
        <h1>Selecione uma empresa</h1>
        <p>
          Seus dados e permissões serão carregados para a empresa escolhida.
        </p>
        <div className="selection-list">
          {session.me.memberships.map((membership) => (
            <Button
              key={membership.id}
              onClick={() => void session.selectCompany(membership.company.id)}
              variant="secondary"
            >
              <span>{membership.company.trade_name}</span>
              <small>{membership.is_owner ? "Proprietário" : "Membro"}</small>
            </Button>
          ))}
        </div>
      </Card>
    </div>
  );
}
