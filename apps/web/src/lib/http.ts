import type { ProblemDetails } from "@orkestral/shared-types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

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
  body?: unknown;
  timeoutMs?: number;
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
  const { body, headers, timeoutMs = 10_000, ...init } = options;
  const combined = combineSignal(init.signal, timeoutMs);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        "X-Request-ID": crypto.randomUUID(),
        ...headers,
      },
      signal: combined.signal,
    });

    if (!response.ok) {
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
