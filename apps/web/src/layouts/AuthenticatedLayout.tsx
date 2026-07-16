import {
  Bell,
  Bot,
  Boxes,
  ChevronDown,
  LayoutDashboard,
  Workflow,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

export function AuthenticatedLayout({
  preview = false,
}: {
  preview?: boolean;
}) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink
          aria-label="Orkestral"
          className="brand brand--inverse"
          to="/preview/app"
        >
          <span aria-hidden="true" className="brand__mark">
            O
          </span>
          <span>Orkestral</span>
        </NavLink>
        <nav aria-label="Navegação principal" className="sidebar__nav">
          <NavLink className="sidebar__link" to="/preview/app">
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
        </nav>
        <div className="sidebar__footer">Fase 1 · Fundação</div>
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
            <strong>Desenvolvimento</strong>
          </div>
          <div className="app-header__actions">
            <button
              aria-label="Notificações"
              className="icon-button"
              type="button"
            >
              <Bell size={19} />
            </button>
            <button className="profile-button" type="button">
              <span>Equipe Orkestral</span>
              <ChevronDown size={16} />
            </button>
          </div>
        </header>
        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
