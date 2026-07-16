import {
  ArrowUpRight,
  CheckCircle2,
  Database,
  Layers3,
  ServerCog,
} from "lucide-react";
import { Card } from "@orkestral/ui-components";
import { useSession } from "../session/context";

const foundationItems = [
  {
    icon: ServerCog,
    title: "Sessão segura",
    description: "Access token em memória e refresh token HttpOnly.",
  },
  {
    icon: Database,
    title: "Isolamento multiempresa",
    description: "Contexto derivado do usuário e vínculo validado pela API.",
  },
  {
    icon: Layers3,
    title: "Gestão de acesso",
    description: "Empresas, usuários, convites e recuperação de senha.",
  },
];

export function DashboardPage() {
  const { me } = useSession();
  return (
    <div className="dashboard">
      <div className="dashboard__heading">
        <div>
          <span className="eyebrow">Visão geral</span>
          <h1>
            {me?.current_company?.trade_name ?? "Administração Orkestral"}
          </h1>
          <p>
            Identidade, sessões e contexto multiempresa estão ativos para
            receber os próximos módulos de negócio.
          </p>
        </div>
        <span className="phase-badge">
          <CheckCircle2 size={16} />
          Fase 2
        </span>
      </div>
      <div className="foundation-grid">
        {foundationItems.map(({ icon: Icon, title, description }) => (
          <Card key={title}>
            <div className="foundation-card__icon">
              <Icon />
            </div>
            <h2>{title}</h2>
            <p>{description}</p>
          </Card>
        ))}
      </div>
      <Card className="next-step" eyebrow="Segurança ativa">
        <div>
          <h2>Acesso autenticado e isolado por empresa</h2>
          <p>
            A empresa atual nunca é aceita livremente do front-end: ela é
            validada pelo vínculo do usuário em cada sessão.
          </p>
        </div>
        <span aria-hidden="true" className="next-step__arrow">
          <ArrowUpRight />
        </span>
      </Card>
    </div>
  );
}
