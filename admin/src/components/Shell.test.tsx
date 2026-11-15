import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AuthProvider } from "./auth";
import { Shell } from "./Shell";

function renderAs(role: "admin" | "editor") {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ user: { id: "u1", email: "a@example.com", full_name: "Ayşe Kaya", role } }), { status: 200 }),
  );
  return render(
    <AuthProvider>
      <Shell>
        <p>içerik</p>
      </Shell>
    </AuthProvider>,
  );
}

describe("Shell navigation by role", () => {
  it("hides admin-only sections from editors", async () => {
    renderAs("editor");
    expect(await screen.findByText("içerik")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Oyunlar" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Ekip ve erişim" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "İşlem kayıtları" })).not.toBeInTheDocument();
    expect(screen.getByText("İçerik editörü")).toBeInTheDocument();
  });

  it("shows staff management to admins", async () => {
    renderAs("admin");
    expect(await screen.findByRole("link", { name: "Ekip ve erişim" })).toBeInTheDocument();
  });

  it("shows a retryable error when the session check fails for reasons other than 401", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "internal_error", message: "Beklenmeyen bir hata oluştu." } }), { status: 500 }),
    );
    render(
      <AuthProvider>
        <p>içerik</p>
      </AuthProvider>,
    );
    expect(await screen.findByText("Beklenmeyen bir hata oluştu.")).toBeInTheDocument();
    expect(screen.queryByText("içerik")).not.toBeInTheDocument();
  });
});
