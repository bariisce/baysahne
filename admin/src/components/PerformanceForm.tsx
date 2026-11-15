"use client";

import { useState, type FormEvent } from "react";
import { ApiError } from "@/lib/api";
import { todayInIstanbul } from "@/lib/format";
import type { ProductionSummary, Venue } from "@/lib/types";
import { Field } from "./ui";

export type Conflict = { reason: string; message: string; production: string; venue: string; local_date: string; local_time: string };

export type PerformanceInput = {
  production_id: string;
  venue_id: string;
  date: string; // YYYY-MM-DD (venue-local)
  time: string; // HH:MM (venue-local)
  visibility: "draft" | "published";
  public_note: string;
  internal_notes: string;
};

export function validatePerformance(v: PerformanceInput, today = todayInIstanbul()): Record<string, string> {
  const e: Record<string, string> = {};
  if (!v.production_id) e.production_id = "Oyun seçin.";
  if (!v.venue_id) e.venue_id = "Salon seçin.";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v.date)) e.date = "Tarih seçin.";
  else if (v.date < today) e.date = "Geçmiş bir tarih seçilemez.";
  if (!/^\d{2}:\d{2}$/.test(v.time)) e.time = "Saat seçin.";
  return e;
}

/**
 * Create/edit form for a performance. Times are entered in the venue's local time (Europe/Istanbul by
 * default) and converted to UTC on the server, so the editor's own computer clock/timezone never matters.
 * A 409 schedule_conflict response shows the clashing performances and asks for explicit confirmation.
 */
export function PerformanceForm({
  productions,
  venues,
  initial,
  lockDateTime,
  submitLabel,
  showVisibility = true,
  onSubmit,
  onCancel,
}: {
  productions: ProductionSummary[];
  venues: Venue[];
  initial: PerformanceInput;
  lockDateTime?: boolean;
  submitLabel: string;
  showVisibility?: boolean;
  onSubmit: (v: PerformanceInput, allowConflict: boolean) => Promise<void>;
  onCancel: () => void;
}) {
  const [v, setV] = useState(initial);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [conflicts, setConflicts] = useState<Conflict[] | null>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof PerformanceInput>(k: K, val: PerformanceInput[K]) => {
    setV((s) => ({ ...s, [k]: val }));
    setConflicts(null);
  };

  async function submit(e: FormEvent | null, allowConflict = false) {
    e?.preventDefault();
    const errs = lockDateTime ? {} : validatePerformance(v);
    setErrors(errs);
    setFormError(null);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try {
      await onSubmit(v, allowConflict);
    } catch (err) {
      if (err instanceof ApiError && err.code === "schedule_conflict") {
        setConflicts((err.details as { conflicts: Conflict[] }).conflicts);
      } else if (err instanceof ApiError) {
        setErrors(err.fields);
        setFormError(err.message);
      } else setFormError("Kaydedilemedi.");
    } finally {
      setBusy(false);
    }
  }

  const activeVenues = venues.filter((x) => x.is_active !== false || x.id === v.venue_id);
  const usable = productions.filter((p) => p.status !== "archived" || p.id === v.production_id);

  return (
    <form onSubmit={(e) => submit(e)} noValidate className="stack" aria-label="Temsil bilgileri">
      {formError && (
        <div className="alert alert-error" role="alert">
          {formError}
        </div>
      )}
      <Field label="Oyun" required error={errors.production_id}>
        {(p) => (
          <select {...p} className="select" value={v.production_id} onChange={(e) => set("production_id", e.target.value)} disabled={lockDateTime}>
            <option value="">Seçin…</option>
            {usable.map((x) => (
              <option key={x.id} value={x.id}>
                {x.title}
                {x.status !== "published" ? " (yayında değil)" : ""}
              </option>
            ))}
          </select>
        )}
      </Field>
      <Field label="Salon" required error={errors.venue_id}>
        {(p) => (
          <select {...p} className="select" value={v.venue_id} onChange={(e) => set("venue_id", e.target.value)}>
            <option value="">Seçin…</option>
            {activeVenues.map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
              </option>
            ))}
          </select>
        )}
      </Field>
      <div className="grid grid-2">
        <Field label="Tarih" required error={errors.date} hint={lockDateTime ? "Yayınlanmış temsilin tarihi “Tarih değiştir” ile değiştirilir." : undefined}>
          {(p) => <input {...p} type="date" className="input" min={todayInIstanbul()} value={v.date} disabled={lockDateTime} onChange={(e) => set("date", e.target.value)} />}
        </Field>
        <Field label="Başlangıç saati" required error={errors.time} hint="Salonun yerel saati (Türkiye).">
          {(p) => <input {...p} type="time" className="input" value={v.time} disabled={lockDateTime} onChange={(e) => set("time", e.target.value)} />}
        </Field>
      </div>
      <Field label="Seyirciye not" hint="İsteğe bağlı. Uygulamada temsilin yanında görünür (ör. “Galası”)." error={errors.public_note}>
        {(p) => <input {...p} className="input" maxLength={500} value={v.public_note} onChange={(e) => set("public_note", e.target.value)} />}
      </Field>
      <Field label="İç not" hint="Yalnızca panelde görünür." error={errors.internal_notes}>
        {(p) => <textarea {...p} className="textarea" style={{ minHeight: 70 }} value={v.internal_notes} onChange={(e) => set("internal_notes", e.target.value)} />}
      </Field>
      {showVisibility && (
        <label className="check">
          <input type="checkbox" checked={v.visibility === "published"} onChange={(e) => set("visibility", e.target.checked ? "published" : "draft")} />
          <span>
            <strong>Hemen yayınla</strong>
            <br />
            <span className="small muted">İşaretlenmezse taslak olarak kaydedilir ve uygulamada görünmez.</span>
          </span>
        </label>
      )}
      {conflicts && (
        <div className="alert alert-warn" role="alert">
          <strong>Program çakışması</strong>
          <ul style={{ margin: "6px 0", paddingLeft: 18 }}>
            {conflicts.map((c, i) => (
              <li key={i}>
                {c.message}: {c.production} — {c.local_date} {c.local_time}, {c.venue}
              </li>
            ))}
          </ul>
          <button type="button" className="btn btn-sm" onClick={() => submit(null, true)} disabled={busy}>
            Kontrol ettim, yine de kaydet
          </button>
        </div>
      )}
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="btn" onClick={onCancel}>
          Vazgeç
        </button>
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {busy ? "Kaydediliyor…" : submitLabel}
        </button>
      </div>
    </form>
  );
}
