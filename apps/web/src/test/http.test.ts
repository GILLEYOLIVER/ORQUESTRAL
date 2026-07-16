import { afterEach, describe, expect, it, vi } from "vitest";
import { request } from "../lib/http";

afterEach(() => vi.restoreAllMocks());

describe("HTTP client", () => {
  it("normaliza Problem Details", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          type: "about:blank",
          title: "Indisponível",
          status: 503,
          detail: "Tente novamente.",
          instance: "/ready",
          request_id: "req-1",
        }),
        {
          status: 503,
          headers: { "content-type": "application/problem+json" },
        },
      ),
    );

    await expect(request("/ready")).rejects.toMatchObject({
      status: 503,
      message: "Tente novamente.",
    });
  });

  it("sempre envia cookies e request ID", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    await request("/health");
    expect(fetchMock).toHaveBeenCalledWith(
      "/health",
      expect.objectContaining({
        credentials: "include",
        headers: expect.objectContaining({
          "X-Request-ID": expect.any(String),
        }),
      }),
    );
  });
});
