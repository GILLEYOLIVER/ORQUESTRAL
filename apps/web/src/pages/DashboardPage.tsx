import {
  ArrowUpRight,
  CheckCircle2,
  Database,
  Layers3,
  ServerCog,
} from "lucide-react";
import { Card } from "@orkestral/ui-components";

const foundationItems = [
  {
    icon: ServerCog,
    title: "Serviços centrais",
    description: "API, worker e gateway estruturados.",
  },
  {
    icon: Database,
    title: "Persistência",
    description: "PostgreSQL e Redis preparados.",
  },
  {
    icon: Layers3,
    title: "Base modular",
    description: "Monorepo pronto para novas fases.",
  },
];

export function DashboardPage() {
  return (
    <div className="dashboard">
      <div className="dashboard__heading">
        <div>
          <span className="eyebrow">Visão geral</span>
          <h1>Fundação da plataforma</h1>
          <p>
            A estrutura técnica inicial está organizada para receber os módulos
            de negócio.
          </p>
        </div>
        <span className="phase-badge">
          <CheckCircle2 size={16} />
          Fase 1
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
      <Card className="next-step" eyebrow="Próximo marco">
        <div>
          <h2>Empresas, usuários e autenticação</h2>
          <p>
            A Fase 2 adicionará sessões reais, contexto multiempresa e gestão
            segura de acesso.
          </p>
        </div>
        <span aria-hidden="true" className="next-step__arrow">
          <ArrowUpRight />
        </span>
      </Card>
    </div>
  );
}
