import { createContext, useContext } from "react";

export type SessionStatus = "anonymous" | "authenticated";

export interface SessionContextValue {
  clearAccessToken: () => void;
  getAccessToken: () => string | null;
  setAccessToken: (token: string) => void;
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
