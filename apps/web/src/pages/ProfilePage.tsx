import { Mail, ShieldCheck, UserRound } from "lucide-react";
import { Card } from "@orkestral/ui-components";
import { useSession } from "../session/context";

export function ProfilePage() {
  const { me } = useSession();
  if (!me) return null;
  return (
    <div className="management-page">
      <div className="dashboard__heading">
        <div>
          <span className="eyebrow">Conta</span>
          <h1>Perfil do usuário</h1>
          <p>Dados da identidade autenticada e do contexto atual.</p>
        </div>
      </div>
      <div className="profile-grid">
        <Card>
          <UserRound />
          <strong>{me.user.name}</strong>
          <span>{me.user.status}</span>
        </Card>
        <Card>
          <Mail />
          <strong>{me.user.email}</strong>
          <span>E-mail de acesso</span>
        </Card>
        <Card>
          <ShieldCheck />
          <strong>
            {me.user.is_platform_admin
              ? "Administrador da plataforma"
              : "Usuário da empresa"}
          </strong>
          <span>{me.permissions.length} permissões ativas</span>
        </Card>
      </div>
    </div>
  );
}
