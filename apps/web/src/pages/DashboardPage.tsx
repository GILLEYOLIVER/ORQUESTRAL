import {
  ArrowUpRight,
  CheckCircle2,
  Database,
  KeyRound,
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
  {
    icon: KeyRound,
    title: "Cofre de credenciais",
    description: "Segredos de integrações armazenados de forma criptografada.",
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
            O núcleo de plugins está ativo e as integrações podem ser habilitadas
            separadamente para cada empresa.
          </p>
        </div>
        <span className="phase-badge">
          <CheckCircle2 size={16} />
          Fase 5
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
      <Card className="next-step" eyebrow="Integrações disponíveis">
        <div>
          <h2>Plugins e credenciais isolados por empresa</h2>
          <p>
            Ative Webhook, SMTP ou API REST, cadastre a credencial no cofre e
            valide a configuração diretamente pela nova página de Integrações.
          </p>
        </div>
        <span aria-hidden="true" className="next-step__arrow">
          <ArrowUpRight />
        </span>
      </Card>
    </div>
  );
}
