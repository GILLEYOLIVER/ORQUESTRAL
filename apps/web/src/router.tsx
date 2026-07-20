/* eslint-disable react-refresh/only-export-components -- este módulo exporta o singleton do roteador e seus guards locais. */
import type { ReactNode } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { Alert } from "@orkestral/ui-components";
import { AuthenticatedLayout } from "./layouts/AuthenticatedLayout";
import { PublicLayout } from "./layouts/PublicLayout";
import { AcceptInvitationPage } from "./pages/AcceptInvitationPage";
import { AgentsPage } from "./pages/AgentsPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { BillingPage } from "./pages/BillingPage";
import { CompaniesPage } from "./pages/CompaniesPage";
import { CompanySelectionPage } from "./pages/CompanySelectionPage";
import { CompanyUsersPage } from "./pages/CompanyUsersPage";
import { CRMContactsPage } from "./pages/CRMContactsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ErrorPage } from "./pages/ErrorPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { FinancePage } from "./pages/FinancePage";
import { LandingPage } from "./pages/LandingPage";
import { KnowledgePage } from "./pages/KnowledgePage";
import { InventoryPage } from "./pages/InventoryPage";
import { HRPage } from "./pages/HRPage";
import { LoginPage } from "./pages/LoginPage";
import { MarketingPage } from "./pages/MarketingPage";
import { ModulesPage } from "./pages/ModulesPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { PluginsPage } from "./pages/PluginsPage";
import { WorkflowsPage } from "./pages/WorkflowsPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ProfilePage } from "./pages/ProfilePage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { RolesPage } from "./pages/RolesPage";
import { SupportPage } from "./pages/SupportPage";
import { useSession } from "./session/context";
import { isModuleActive, useModules } from "./modules/useModules";

function ProtectedApp() {
  const session = useSession();
  if (session.status === "loading") {
    return <div className="route-loading">Carregando sessão segura…</div>;
  }
  if (session.status !== "authenticated") {
    return (
      <Navigate
        replace
        to={
          session.status === "company_selection"
            ? "/selecionar-empresa"
            : "/login"
        }
      />
    );
  }
  return <AuthenticatedLayout />;
}

function CompanySelectionGuard() {
  const session = useSession();
  if (session.status === "loading") {
    return <div className="route-loading">Carregando empresas…</div>;
  }
  if (session.status === "anonymous") return <Navigate replace to="/login" />;
  if (session.status === "authenticated" && session.me?.current_company) {
    return <Navigate replace to="/app" />;
  }
  return <CompanySelectionPage />;
}

function DevelopmentPreview() {
  const previewEnabled =
    import.meta.env.DEV && import.meta.env.VITE_AUTH_PREVIEW_ENABLED === "true";
  return previewEnabled ? <AuthenticatedLayout preview /> : <NotFoundPage />;
}

function PermissionRoute({
  children,
  permission,
}: {
  children: ReactNode;
  permission: string;
}) {
  const { me } = useSession();
  return me?.permissions.includes(permission) ? (
    children
  ) : (
    <Alert variant="error">
      Você não possui permissão para acessar esta área.
    </Alert>
  );
}

function ModuleRoute({
  children,
  moduleCode,
  permission,
}: {
  children: ReactNode;
  moduleCode: string;
  permission: string;
}) {
  const { me } = useSession();
  const hasPermission = me?.permissions.includes(permission) ?? false;
  const modules = useModules(hasPermission);
  if (!hasPermission) {
    return (
      <Alert variant="error">
        Você não possui permissão para acessar esta área.
      </Alert>
    );
  }
  if (modules.isLoading) {
    return <div className="route-loading">Verificando módulo…</div>;
  }
  return isModuleActive(modules.data, moduleCode) ? (
    children
  ) : (
    <Alert variant="error">
      Este módulo não está ativo para a empresa atual.
    </Alert>
  );
}

export const router = createBrowserRouter([
  {
    element: <PublicLayout />,
    errorElement: <ErrorPage />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: "login", element: <LoginPage /> },
      { path: "esqueci-minha-senha", element: <ForgotPasswordPage /> },
      { path: "redefinir-senha", element: <ResetPasswordPage /> },
      { path: "aceitar-convite", element: <AcceptInvitationPage /> },
    ],
  },
  {
    path: "app",
    element: <ProtectedApp />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "notificacoes", element: <NotificationsPage /> },
      { path: "perfil", element: <ProfilePage /> },
      {
        path: "plano",
        element: (
          <PermissionRoute permission="billing.view">
            <BillingPage />
          </PermissionRoute>
        ),
      },
      {
        path: "empresas",
        element: (
          <PermissionRoute permission="platform.companies.view">
            <CompaniesPage />
          </PermissionRoute>
        ),
      },
      {
        path: "usuarios",
        element: (
          <PermissionRoute permission="users.view">
            <CompanyUsersPage />
          </PermissionRoute>
        ),
      },
      {
        path: "papeis",
        element: (
          <PermissionRoute permission="roles.view">
            <RolesPage />
          </PermissionRoute>
        ),
      },
      {
        path: "modulos",
        element: (
          <PermissionRoute permission="modules.view">
            <ModulesPage />
          </PermissionRoute>
        ),
      },
      {
        path: "integracoes",
        element: (
          <PermissionRoute permission="plugins.view">
            <PluginsPage />
          </PermissionRoute>
        ),
      },
      {
        path: "agentes",
        element: (
          <PermissionRoute permission="agents.view">
            <AgentsPage />
          </PermissionRoute>
        ),
      },
      {
        path: "conhecimento",
        element: (
          <PermissionRoute permission="knowledge.view">
            <KnowledgePage />
          </PermissionRoute>
        ),
      },
      {
        path: "automacoes",
        element: (
          <PermissionRoute permission="workflows.view">
            <WorkflowsPage />
          </PermissionRoute>
        ),
      },
      {
        path: "crm/contatos",
        element: (
          <ModuleRoute moduleCode="crm" permission="crm.contacts.view">
            <CRMContactsPage />
          </ModuleRoute>
        ),
      },
      {
        path: "suporte",
        element: (
          <ModuleRoute moduleCode="support" permission="support.tickets.view">
            <SupportPage />
          </ModuleRoute>
        ),
      },
      {
        path: "projetos",
        element: (
          <ModuleRoute moduleCode="projects" permission="projects.view">
            <ProjectsPage />
          </ModuleRoute>
        ),
      },
      {
        path: "marketing",
        element: (
          <ModuleRoute moduleCode="marketing" permission="marketing.view">
            <MarketingPage />
          </ModuleRoute>
        ),
      },
      {
        path: "estoque",
        element: (
          <ModuleRoute moduleCode="inventory" permission="inventory.view">
            <InventoryPage />
          </ModuleRoute>
        ),
      },
      {
        path: "financeiro",
        element: (
          <ModuleRoute moduleCode="finance" permission="finance.view">
            <FinancePage />
          </ModuleRoute>
        ),
      },
      {
        path: "recursos-humanos",
        element: (
          <ModuleRoute moduleCode="hr" permission="hr.view">
            <HRPage />
          </ModuleRoute>
        ),
      },
      {
        path: "analytics",
        element: (
          <ModuleRoute moduleCode="analytics" permission="analytics.view">
            <AnalyticsPage />
          </ModuleRoute>
        ),
      },
    ],
  },
  { path: "selecionar-empresa", element: <CompanySelectionGuard /> },
  {
    path: "preview/app",
    element: <DevelopmentPreview />,
    children: [{ index: true, element: <DashboardPage /> }],
  },
  { path: "*", element: <NotFoundPage /> },
]);
