import {
  Bell,
  BookOpenText,
  Bot,
  Boxes,
  Building2,
  ChartColumnBig,
  ContactRound,
  CreditCard,
  Database,
  FolderKanban,
  LayoutDashboard,
  Landmark,
  LifeBuoy,
  LogOut,
  Megaphone,
  PackageOpen,
  RadioTower,
  ScanSearch,
  UploadCloud,
  ShieldCheck,
  UserRoundCog,
  UserRound,
  UsersRound,
  Workflow,
  Warehouse,
} from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { environment } from "../lib/environment";
import { isModuleActive, useModules } from "../modules/useModules";
import { useNotificationSummary } from "../notifications/useNotifications";
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
  const notificationSummary = useNotificationSummary(!preview);
  const attentionCount =
    (notificationSummary.data?.unread_count ?? 0) +
    (notificationSummary.data?.pending_approvals ?? 0);
  const readOnly = session.me?.access_mode === "read_only";

  const logout = async () => {
    await session.logout();
    await navigate("/login", { replace: true });
  };

  return (
    <div className={`app-shell${readOnly ? " app-shell--read-only" : ""}`}>
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
          {!preview ? (
            <NavLink className="sidebar__link" to="/app/notificacoes">
              <Bell size={18} />
              Central de atenção
              {attentionCount ? (
                <span className="sidebar__badge">{attentionCount}</span>
              ) : null}
            </NavLink>
          ) : null}
          {!preview &&
          session.me?.permissions.includes("crm.contacts.view") &&
          isModuleActive(modules.data, "crm") ? (
            <NavLink
              className="sidebar__link"
              to="/app/crm/importacao-de-dados"
            >
              <UploadCloud size={18} />
              Importar dados
            </NavLink>
          ) : null}
          {!preview &&
          session.me?.permissions.includes("crm.contacts.view") &&
          isModuleActive(modules.data, "crm") ? (
            <NavLink
              className="sidebar__link"
              to="/app/crm/sincronizacao-de-dados"
            >
              <RadioTower size={18} />
              Sincronizar dados
            </NavLink>
          ) : null}
          {!preview &&
          session.me?.permissions.includes("crm.contacts.view") &&
          isModuleActive(modules.data, "crm") ? (
            <NavLink
              className="sidebar__link"
              to="/app/crm/governanca-de-dados"
            >
              <ScanSearch size={18} />
              Qualidade de dados
            </NavLink>
          ) : null}
          {!preview &&
          environment.n8nEnabled &&
          session.me?.permissions.includes("workflows.view") ? (
            <NavLink className="sidebar__link" to="/app/automacoes">
              <Workflow size={18} />
              Automações
            </NavLink>
          ) : null}
          {!preview && session.me?.permissions.includes("events.view") ? (
            <NavLink className="sidebar__link" to="/app/eventos">
              <RadioTower size={18} />
              Eventos
            </NavLink>
          ) : null}
          {!preview && session.me?.permissions.includes("agents.view") ? (
            <NavLink className="sidebar__link" to="/app/agentes">
              <Bot size={18} />
              Agentes
            </NavLink>
          ) : null}
          {!preview &&
          environment.objectStorageEnabled &&
          session.me?.permissions.includes("knowledge.view") ? (
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
          {!preview && session.me?.permissions.includes("metadata.view") ? (
            <NavLink className="sidebar__link" to="/app/studio">
              <Database size={18} />
              Orkestral Studio
            </NavLink>
          ) : null}
          {!preview && session.me?.permissions.includes("billing.view") ? (
            <NavLink className="sidebar__link" to="/app/plano">
              <CreditCard size={18} />
              Plano e consumo
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
          {!preview &&
          session.me?.permissions.includes("support.tickets.view") &&
          isModuleActive(modules.data, "support") ? (
            <NavLink className="sidebar__link" to="/app/suporte">
              <LifeBuoy size={18} />
              Suporte
            </NavLink>
          ) : null}
          {!preview &&
          session.me?.permissions.includes("projects.view") &&
          isModuleActive(modules.data, "projects") ? (
            <NavLink className="sidebar__link" to="/app/projetos">
              <FolderKanban size={18} />
              Projetos
            </NavLink>
          ) : null}
          {!preview &&
          session.me?.permissions.includes("marketing.view") &&
          isModuleActive(modules.data, "marketing") ? (
            <NavLink className="sidebar__link" to="/app/marketing">
              <Megaphone size={18} />
              Marketing
            </NavLink>
          ) : null}
          {!preview &&
          session.me?.permissions.includes("inventory.view") &&
          isModuleActive(modules.data, "inventory") ? (
            <NavLink className="sidebar__link" to="/app/estoque">
              <Warehouse size={18} />
              Estoque
            </NavLink>
          ) : null}
          {!preview &&
          session.me?.permissions.includes("finance.view") &&
          isModuleActive(modules.data, "finance") ? (
            <NavLink className="sidebar__link" to="/app/financeiro">
              <Landmark size={18} />
              Financeiro
            </NavLink>
          ) : null}
          {!preview &&
          session.me?.permissions.includes("hr.view") &&
          isModuleActive(modules.data, "hr") ? (
            <NavLink className="sidebar__link" to="/app/recursos-humanos">
              <UserRoundCog size={18} />
              Recursos humanos
            </NavLink>
          ) : null}
          {!preview &&
          session.me?.permissions.includes("analytics.view") &&
          isModuleActive(modules.data, "analytics") ? (
            <NavLink className="sidebar__link" to="/app/analytics">
              <ChartColumnBig size={18} />
              Analytics
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
        <div className="sidebar__footer">Operação segura e integrada</div>
      </aside>
      <div className="app-main">
        {readOnly ? (
          <div className="read-only-banner" role="status">
            Administrador Somente Leitura · você pode consultar toda a empresa,
            mas qualquer alteração será bloqueada e auditada.
          </div>
        ) : null}
        {environment.remoteDevelopment ? (
          <div className="remote-development-banner" role="status">
            Ambiente de desenvolvimento remoto · dados de teste · recursos
            reduzidos
          </div>
        ) : null}
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
            {preview ? (
              <button
                aria-label="Notificações"
                className="icon-button"
                type="button"
              >
                <Bell size={19} />
              </button>
            ) : (
              <NavLink
                aria-label="Notificações"
                className="icon-button notification-button"
                to="/app/notificacoes"
              >
                <Bell size={19} />
                {attentionCount ? (
                  <span className="notification-button__badge">
                    {attentionCount > 99 ? "99+" : attentionCount}
                  </span>
                ) : null}
              </NavLink>
            )}
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
