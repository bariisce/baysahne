import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import type { ProductionSummary, Venue } from "@/lib/types";
import { PerformanceForm, validatePerformance, type PerformanceInput } from "./PerformanceForm";

const productions = [{ id: "p1", title: "Sefiller", status: "published" } as ProductionSummary];
const venues = [{ id: "v1", name: "Ana Salon", timezone: "Europe/Istanbul" } as Venue];
const base: PerformanceInput = {
  production_id: "p1", venue_id: "v1", date: "2099-05-01", time: "20:30", visibility: "published", public_note: "", internal_notes: "",
};

describe("PerformanceForm", () => {
  it("rejects missing and past dates", () => {
    expect(validatePerformance({ ...base, date: "" }).date).toBe("Tarih seçin.");
    expect(validatePerformance({ ...base, date: "2020-01-01" }, "2026-10-16").date).toBe("Geçmiş bir tarih seçilemez.");
    expect(validatePerformance({ ...base, production_id: "" }).production_id).toBe("Oyun seçin.");
    expect(validatePerformance(base, "2026-10-16")).toEqual({});
  });

  it("shows schedule conflicts and only saves after explicit confirmation", async () => {
    const onSubmit = vi
      .fn()
      .mockRejectedValueOnce(
        new ApiError(409, "schedule_conflict", "Program çakışması var.", {
          conflicts: [{ reason: "same_venue", message: "Aynı salonda yakın saatte başka bir temsil var", production: "1984", venue: "Ana Salon", local_date: "1 Mayıs 2099", local_time: "20:00" }],
        }),
      )
      .mockResolvedValueOnce(undefined);
    render(<PerformanceForm productions={productions} venues={venues} initial={base} submitLabel="Kaydet" onSubmit={onSubmit} onCancel={() => {}} />);

    await userEvent.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText(/Aynı salonda yakın saatte başka bir temsil var: 1984/)).toBeInTheDocument();
    expect(onSubmit).toHaveBeenLastCalledWith(base, false);

    await userEvent.click(screen.getByRole("button", { name: "Kontrol ettim, yine de kaydet" }));
    expect(onSubmit).toHaveBeenLastCalledWith(base, true);
  });

  it("locks date and time for already-published performances", () => {
    render(<PerformanceForm productions={productions} venues={venues} initial={base} lockDateTime submitLabel="Kaydet" onSubmit={vi.fn()} onCancel={() => {}} />);
    expect(screen.getByLabelText(/Tarih/)).toBeDisabled();
    expect(screen.getByLabelText(/Başlangıç saati/)).toBeDisabled();
  });
});
