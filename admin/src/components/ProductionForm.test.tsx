import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import { ProductionForm, toInput, validate } from "./ProductionForm";

describe("ProductionForm validation", () => {
  it("requires a title, https video links and named credits", () => {
    const v = { ...toInput(null), title: " ", videos: [{ url: "http://x.example", title: null }], credits: [{ role: "other" as const, role_label: null, name: "" }] };
    const e = validate(v);
    expect(e.title).toBe("Oyun adı zorunludur.");
    expect(e["videos.0.url"]).toBe("Bağlantı https:// ile başlamalıdır.");
    expect(e["credits.0.name"]).toBe("İsim zorunludur.");
    expect(e["credits.0.role_label"]).toBe("Görev adını yazın.");
  });

  it("blocks submission until errors are fixed", async () => {
    const onSubmit = vi.fn();
    render(<ProductionForm initial={toInput(null)} submitLabel="Kaydet" onSubmit={onSubmit} />);
    await userEvent.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText("Oyun adı zorunludur.")).toBeInTheDocument();
  });

  it("submits normalised genres and credits", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ProductionForm initial={toInput(null)} submitLabel="Kaydet" onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText(/Oyun adı/), "Yeni Oyun");
    fireEvent.change(screen.getByLabelText("Tür"), { target: { value: " Dram ,  , Komedi " } });
    await userEvent.click(screen.getByRole("button", { name: "Kişi ekle" }));
    await userEvent.type(screen.getByLabelText("İsim"), "Ayşe Yılmaz");
    await userEvent.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
    const payload = onSubmit.mock.calls[0][0];
    expect(payload.genres).toEqual(["Dram", "Komedi"]);
    expect(payload.credits).toEqual([{ role: "cast", role_label: null, name: "Ayşe Yılmaz" }]);
  });

  it("maps server field errors back onto the form", async () => {
    const onSubmit = vi.fn().mockRejectedValue(
      new ApiError(409, "slug_taken", "Bu kısa ad başka bir oyunda kullanılıyor.", { fields: [{ field: "title", message: "Sunucu hatası" }] }),
    );
    render(<ProductionForm initial={{ ...toInput(null), title: "A" }} submitLabel="Kaydet" onSubmit={onSubmit} />);
    await userEvent.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText("Bu kısa ad başka bir oyunda kullanılıyor.")).toBeInTheDocument();
    expect(screen.getByText("Sunucu hatası")).toBeInTheDocument();
  });
});
