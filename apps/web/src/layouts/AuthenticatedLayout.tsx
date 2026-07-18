import {
  Bell,
  BookOpenText,
  Bot,
  Boxes,
  Building2,
  ContactRound,
  LayoutDashboard,
  LogOut,
  PackageOpen,
  ShieldCheck,
  UserRound,
  UsersRound,
  Workflow,
} from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { isModuleActive, useModules } from "../modules/useModules";
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
  const modules = useModules(!preview);

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
          {!preview && session.me?.permissions.includes("workflows.view") ? (
            <NavLink className="sidebar__link" to="/app/automacoes">
              <Workflow size={18} />
              Automações
            </NavLink>
          ) : null}
          {!preview && session.me?.permissions.includes("agents.view") ? (
            <NavLink className="sidebar__link" to="/app/agentes">
              <Bot size={18} />
              Agentes
            </NavLink>
          ) : null}
          {!preview && session.me?.permissions.includes("knowledge.view") ? (
            <NavLink className="sidebar__link" to="/app/conhecimento">
              <BookOpenText size={18} />
              Conhecimento
            </NavLink>
          ) : null}
          {!preview && session.me?.permissions.includes("plugins.view") ? (
            <NavLink className="sidebar__link" to="/app/integracoes">
              <Boxes size={18} />
              Integrações
            </NavLink>
          ) : null}
          {!preview && session.me?.permissions.includes("modules.view") ? (
            <NavLink className="sidebar__link" to="/app/modulos">
              <PackageOpen size={18} />
              Módulos
            </NavLink>
          ) : null}
          {!preview &&
          session.me?.permissions.includes("crm.contacts.view") &&
          isModuleActive(modules.data, "crm") ? (
            <NavLink className="sidebar__link" to="/app/crm/contatos">
              <ContactRound size={18} />
              Contatos
            </NavLink>
          ) : null}
          {!preview && session.me?.permissions.includes("users.view") ? (
            <NavLink className="sidebar__link" to="/app/usuarios">
              <UsersRound size={18} />
              Usuários
            </NavLink>
          ) : null}
          {!preview && session.me?.permissions.includes("roles.view") ? (
            <NavLink className="sidebar__link" to="/app/papeis">
              <ShieldCheck size={18} />
              Papéis
            </NavLink>
          ) : null}
          {!preview &&
          session.me?.permissions.includes("platform.companies.view") ? (
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
        <div className="sidebar__footer">Fase 9 · Automacoes visuais</div>
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
