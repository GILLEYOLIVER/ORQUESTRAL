import {
  Bell,
  Bot,
  Boxes,
  Building2,
  LayoutDashboard,
  LogOut,
  UserRound,
  UsersRound,
  Workflow,
} from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useSession } from "../session/context";

export function AuthenticatedLayout({
  preview = false,
}: {
  preview?: boolean;
}) {
  const session = useSession();
  const navigate = useNavigate();
  const rootPath = preview ? "/preview/app" : "/app";
  const userName = session.me?.user.name ?? "Equipe Orkestral";
  const companyName =
    session.me?.current_company?.trade_name ?? "Administração da plataforma";

  const logout = async () => {
    await session.logout();
    await navigate("/login", { replace: true });
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink
          aria-label="Orkestral"
          className="brand brand--inverse"
          to={rootPath}
        >
          <span aria-hidden="true" className="brand__mark">
            O
          </span>
          <span>Orkestral</span>
        </NavLink>
        <nav aria-label="Navegação principal" className="sidebar__nav">
          <NavLink className="sidebar__link" end to={rootPath}>
            <LayoutDashboard size={18} />
            Visão geral
          </NavLink>
          <span
            aria-disabled="true"
            className="sidebar__link sidebar__link--disabled"
          >
            <Workflow size={18} />
            Automações
          </span>
          <span
            aria-disabled="true"
            className="sidebar__link sidebar__link--disabled"
          >
            <Bot size={18} />
            Agentes
          </span>
          <span
            aria-disabled="true"
            className="sidebar__link sidebar__link--disabled"
          >
            <Boxes size={18} />
            Integrações
          </span>
          {!preview &&
          session.me?.permissions.includes("company:manage_users") ? (
            <NavLink className="sidebar__link" to="/app/usuarios">
              <UsersRound size={18} />
              Usuários
            </NavLink>
          ) : null}
          {!preview && session.me?.user.is_platform_admin ? (
            <NavLink className="sidebar__link" to="/app/empresas">
              <Building2 size={18} />
              Empresas
            </NavLink>
          ) : null}
          {!preview ? (
            <NavLink className="sidebar__link" to="/app/perfil">
              <UserRound size={18} />
              Meu perfil
            </NavLink>
          ) : null}
        </nav>
        <div className="sidebar__footer">Fase 2 · Identidade e acesso</div>
      </aside>
      <div className="app-main">
        {preview ? (
          <div className="preview-banner" role="status">
            Prévia de desenvolvimento · sem sessão real
          </div>
        ) : null}
        <header className="app-header">
          <div>
            <span className="app-header__eyebrow">Ambiente</span>
            <strong>{companyName}</strong>
          </div>
          <div className="app-header__actions">
            <button
              aria-label="Notificações"
              className="icon-button"
              type="button"
            >
              <Bell size={19} />
            </button>
            <NavLink
              className="profile-button"
              to={preview ? rootPath : "/app/perfil"}
            >
              <span>{userName}</span>
            </NavLink>
            {!preview ? (
              <button
                aria-label="Sair"
                className="icon-button"
                onClick={() => void logout()}
                type="button"
              >
                <LogOut size={18} />
              </button>
            ) : null}
          </div>
        </header>
        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
