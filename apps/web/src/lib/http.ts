import type { ProblemDetails } from "@orkestral/shared-types";
import { getAccessToken } from "../session/tokenStore";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

export class ApiClientError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly problem?: ProblemDetails,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  authenticated?: boolean;
  allowAuthRefresh?: boolean;
  body?: unknown;
  timeoutMs?: number;
}

let refreshHandler: (() => Promise<string | null>) | null = null;

export function registerAuthRefreshHandler(
  handler: (() => Promise<string | null>) | null,
) {
  refreshHandler = handler;
}

function combineSignal(
  signal: AbortSignal | null | undefined,
  timeoutMs: number,
) {
  const controller = new AbortController();
  const timeout = window.setTimeout(
    () => controller.abort("timeout"),
    timeoutMs,
  );
  const abort = () => controller.abort(signal?.reason);
  signal?.addEventListener("abort", abort, { once: true });
  return {
    signal: controller.signal,
    dispose: () => {
      window.clearTimeout(timeout);
      signal?.removeEventListener("abort", abort);
    },
  };
}

export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const {
    allowAuthRefresh = true,
    authenticated = true,
    body,
    headers,
    timeoutMs = 10_000,
    ...init
  } = options;
  const combined = combineSignal(init.signal, timeoutMs);
  const token = authenticated ? getAccessToken() : null;

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        "X-Request-ID": crypto.randomUUID(),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
      signal: combined.signal,
    });

    if (!response.ok) {
      if (
        response.status === 401 &&
        authenticated &&
        allowAuthRefresh &&
        refreshHandler
      ) {
        const refreshedToken = await refreshHandler();
        if (refreshedToken) {
          return request<T>(path, {
            ...options,
            allowAuthRefresh: false,
          });
        }
      }
      const contentType = response.headers.get("content-type") ?? "";
      const problem = contentType.includes("application/problem+json")
        ? ((await response.json()) as ProblemDetails)
        : undefined;
      throw new ApiClientError(
        problem?.detail ?? "A solicitação não pôde ser concluída.",
        response.status,
        problem,
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    if (combined.signal.aborted) {
      throw new ApiClientError("A solicitação excedeu o tempo limite.", 0);
    }
    throw new ApiClientError("Não foi possível conectar ao serviço.", 0);
  } finally {
    combined.dispose();
  }
}
