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
    title: "Núcleo modular",
    description: "Funcionalidades ativadas separadamente por empresa.",
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
            O núcleo modular está ativo e o primeiro módulo funcional de CRM
            já pode ser habilitado para cada empresa.
          </p>
        </div>
        <span className="phase-badge">
          <CheckCircle2 size={16} />
          Fase 4
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
      <Card className="next-step" eyebrow="CRM disponível">
        <div>
          <h2>Contatos comerciais isolados por empresa</h2>
          <p>
            Ative o CRM no catálogo de módulos para usar pesquisa, filtros,
            etiquetas, paginação e gestão completa de contatos.
          </p>
        </div>
        <span aria-hidden="true" className="next-step__arrow">
          <ArrowUpRight />
        </span>
      </Card>
    </div>
  );
}
