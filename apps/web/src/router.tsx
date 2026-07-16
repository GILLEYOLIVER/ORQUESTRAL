/* eslint-disable react-refresh/only-export-components -- este módulo exporta o singleton do roteador e seus guards locais. */
import { createBrowserRouter, Navigate } from "react-router-dom";
import { AuthenticatedLayout } from "./layouts/AuthenticatedLayout";
import { PublicLayout } from "./layouts/PublicLayout";
import { AcceptInvitationPage } from "./pages/AcceptInvitationPage";
import { CompaniesPage } from "./pages/CompaniesPage";
import { CompanySelectionPage } from "./pages/CompanySelectionPage";
import { CompanyUsersPage } from "./pages/CompanyUsersPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ErrorPage } from "./pages/ErrorPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ProfilePage } from "./pages/ProfilePage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { useSession } from "./session/context";

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
      { path: "perfil", element: <ProfilePage /> },
      { path: "empresas", element: <CompaniesPage /> },
      { path: "usuarios", element: <CompanyUsersPage /> },
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
