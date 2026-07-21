import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { AccessTokenResponse, MeResponse } from "@orkestral/shared-types";
import { queryClient } from "../lib/queryClient";
import { registerAuthRefreshHandler, request } from "../lib/http";
import { SessionContext } from "./context";
import type { SessionContextValue, SessionStatus } from "./context";
import { clearAccessToken, getAccessToken, setAccessToken } from "./tokenStore";

function sessionStatus(profile: MeResponse): SessionStatus {
  return profile.requires_company_selection
    ? "company_selection"
    : "authenticated";
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SessionStatus>("loading");
  const [me, setMe] = useState<MeResponse | null>(null);
  const started = useRef(false);

  const refreshAccessToken = useCallback(async () => {
    try {
      const tokens = await request<AccessTokenResponse>("/auth/refresh", {
        method: "POST",
        authenticated: false,
        allowAuthRefresh: false,
      });
      setAccessToken(tokens.access_token);
      return tokens.access_token;
    } catch {
      clearAccessToken();
      return null;
    }
  }, []);

  const loadProfile = useCallback(async () => {
    const profile = await request<MeResponse>("/auth/me", {
      allowAuthRefresh: false,
    });
    setMe(profile);
    setStatus(sessionStatus(profile));
    return profile;
  }, []);

  useEffect(() => {
    registerAuthRefreshHandler(refreshAccessToken);
    return () => registerAuthRefreshHandler(null);
  }, [refreshAccessToken]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void (async () => {
      const token = await refreshAccessToken();
      if (!token) {
        setStatus("anonymous");
        return;
      }
      try {
        await loadProfile();
      } catch {
        clearAccessToken();
        setMe(null);
        setStatus("anonymous");
      }
    })();
  }, [loadProfile, refreshAccessToken]);

  const value = useMemo<SessionContextValue>(
    () => ({
      status,
      me,
      getAccessToken,
      developmentLogin: async () => {
        setStatus("loading");
        try {
          const tokens = await request<AccessTokenResponse>(
            "/auth/development-login",
            {
              method: "POST",
              authenticated: false,
              allowAuthRefresh: false,
            },
          );
          setAccessToken(tokens.access_token);
          return await loadProfile();
        } catch (error) {
          clearAccessToken();
          setMe(null);
          setStatus("anonymous");
          throw error;
        }
      },
      login: async (email, password) => {
        setStatus("loading");
        try {
          const tokens = await request<AccessTokenResponse>("/auth/login", {
            method: "POST",
            authenticated: false,
            allowAuthRefresh: false,
            body: { email, password },
          });
          setAccessToken(tokens.access_token);
          return await loadProfile();
        } catch (error) {
          clearAccessToken();
          setMe(null);
          setStatus("anonymous");
          throw error;
        }
      },
      loginWithReadOnlyLink: async (token) => {
        setStatus("loading");
        try {
          const tokens = await request<AccessTokenResponse>(
            "/auth/read-only-links/exchange",
            {
              method: "POST",
              authenticated: false,
              allowAuthRefresh: false,
              body: { token },
            },
          );
          setAccessToken(tokens.access_token);
          return await loadProfile();
        } catch (error) {
          clearAccessToken();
          setMe(null);
          setStatus("anonymous");
          throw error;
        }
      },
      logout: async () => {
        try {
          await request<void>("/auth/logout", {
            method: "POST",
            authenticated: false,
            allowAuthRefresh: false,
          });
        } finally {
          clearAccessToken();
          setMe(null);
          setStatus("anonymous");
          queryClient.clear();
        }
      },
      refreshProfile: async () => {
        if (!getAccessToken()) return null;
        return loadProfile();
      },
      selectCompany: async (companyId) => {
        const tokens = await request<AccessTokenResponse>(
          "/auth/select-company",
          { method: "POST", body: { company_id: companyId } },
        );
        setAccessToken(tokens.access_token);
        await loadProfile();
      },
    }),
    [loadProfile, me, status],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}
