import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { LoginForm } from "./LoginForm";

describe("LoginForm", () => {
  it("validates required fields in Turkish without calling the API", async () => {
    const f = vi.spyOn(globalThis, "fetch");
    render(<LoginForm />);
    await userEvent.click(screen.getByRole("button", { name: "Giriş yap" }));
    expect(screen.getByText("E-posta adresinizi girin.")).toBeInTheDocument();
    expect(screen.getByText("Parolanızı girin.")).toBeInTheDocument();
    expect(screen.getByLabelText("E-posta")).toHaveAttribute("aria-invalid", "true");
    expect(f).not.toHaveBeenCalled();
  });

  it("shows the server's error message on failed login", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "invalid_credentials", message: "E-posta adresi veya parola hatalı." } }), { status: 401 }),
    );
    render(<LoginForm />);
    await userEvent.type(screen.getByLabelText("E-posta"), "editor@example.com");
    await userEvent.type(screen.getByLabelText("Parola"), "yanlis");
    await userEvent.click(screen.getByRole("button", { name: "Giriş yap" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("E-posta adresi veya parola hatalı.");
  });
});
