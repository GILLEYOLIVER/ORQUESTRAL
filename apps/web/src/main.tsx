import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import "@orkestral/ui-components/styles.css";
import "./styles.css";
import { queryClient } from "./lib/queryClient";
import { router } from "./router";
import { SessionProvider } from "./session/SessionProvider";

const root = document.getElementById("root");
if (!root) {
  throw new Error("Elemento raiz não encontrado.");
}

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </QueryClientProvider>
  </StrictMode>,
);
