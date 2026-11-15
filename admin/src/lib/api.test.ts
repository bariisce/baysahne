import { describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";

function mockFetch(status: number, body: unknown) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(body === null ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }),
  );
}

describe("api client", () => {
  it("sends the CSRF header and JSON body to the proxied /api path", async () => {
    const f = mockFetch(200, { ok: true });
    await api.post("/admin/productions", { title: "X" });
    const [url, init] = f.mock.calls[0];
    expect(url).toBe("/api/v1/admin/productions");
    expect((init!.headers as Record<string, string>)["X-Requested-With"]).toBe("baysahne-admin");
    expect(init!.body).toBe(JSON.stringify({ title: "X" }));
    expect(init!.credentials).toBe("same-origin");
  });

  it("turns the backend error envelope into ApiError with field messages", async () => {
    mockFetch(422, {
      error: { code: "validation_error", message: "Lütfen formdaki hataları düzeltin.", details: { fields: [{ field: "title", message: "Bu alan zorunludur." }] } },
    });
    const err = (await api.post("/admin/productions", {}).catch((e) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.message).toBe("Lütfen formdaki hataları düzeltin.");
    expect(err.fields).toEqual({ title: "Bu alan zorunludur." });
  });

  it("reports network failures in Turkish", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    const err = (await api.get("/admin/dashboard").catch((e) => e)) as ApiError;
    expect(err.code).toBe("network_error");
    expect(err.message).toMatch(/Sunucuya ulaşılamadı/);
  });

  it("signals an expired session so the app can return to the login page", async () => {
    mockFetch(401, { error: { code: "unauthorized", message: "Oturumunuz sona erdi." } });
    const handler = vi.fn();
    window.addEventListener("baysahne:unauthorized", handler);
    await api.get("/admin/dashboard").catch(() => null);
    expect(handler).toHaveBeenCalledTimes(1);
    // a failed login (auth endpoint) must not trigger a redirect loop
    await api.post("/admin/auth/login", {}).catch(() => null);
    expect(handler).toHaveBeenCalledTimes(1);
    window.removeEventListener("baysahne:unauthorized", handler);
  });
});
