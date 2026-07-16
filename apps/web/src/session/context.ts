import { createContext, useContext } from "react";
import type { MeResponse } from "@orkestral/shared-types";

export type SessionStatus =
  "loading" | "anonymous" | "authenticated" | "company_selection";

export interface SessionContextValue {
  login: (email: string, password: string) => Promise<MeResponse>;
  logout: () => Promise<void>;
  me: MeResponse | null;
  refreshProfile: () => Promise<MeResponse | null>;
  selectCompany: (companyId: string) => Promise<void>;
  getAccessToken: () => string | null;
  status: SessionStatus;
}

export const SessionContext = createContext<SessionContextValue | null>(null);

export function useSession() {
  const session = useContext(SessionContext);
  if (!session) {
    throw new Error("useSession deve ser usado dentro de SessionProvider.");
  }
  return session;
}
