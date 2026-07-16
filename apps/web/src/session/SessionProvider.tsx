import { useMemo, useRef } from "react";
import type { ReactNode } from "react";
import { SessionContext } from "./context";
import type { SessionContextValue } from "./context";

export function SessionProvider({ children }: { children: ReactNode }) {
  const accessToken = useRef<string | null>(null);
  const value = useMemo<SessionContextValue>(
    () => ({
      status: "anonymous",
      getAccessToken: () => accessToken.current,
      setAccessToken: (token) => {
        accessToken.current = token;
      },
      clearAccessToken: () => {
        accessToken.current = null;
      },
    }),
    [],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}
