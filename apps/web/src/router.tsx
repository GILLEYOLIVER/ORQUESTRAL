/* eslint-disable react-refresh/only-export-components -- este módulo exporta o singleton do roteador e seus guards locais. */
import { createBrowserRouter, Navigate } from "react-router-dom";
import { AuthenticatedLayout } from "./layouts/AuthenticatedLayout";
import { PublicLayout } from "./layouts/PublicLayout";
import { DashboardPage } from "./pages/DashboardPage";
import { ErrorPage } from "./pages/ErrorPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { useSession } from "./session/context";

function ProtectedApp() {
  const session = useSession();
  if (session.status !== "authenticated") {
    return <Navigate replace to="/login" />;
  }
  return <AuthenticatedLayout />;
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
    ],
  },
  {
    path: "app",
    element: <ProtectedApp />,
    children: [{ index: true, element: <DashboardPage /> }],
  },
  {
    path: "preview/app",
    element: <DevelopmentPreview />,
    children: [{ index: true, element: <DashboardPage /> }],
  },
  { path: "*", element: <NotFoundPage /> },
]);
