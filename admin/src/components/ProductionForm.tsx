"use client";

import { useState, type FormEvent } from "react";
import { ApiError } from "@/lib/api";
import { CREDIT_ROLE_LABELS } from "@/lib/format";
import type { CreditRole, Production } from "@/lib/types";
import { Field } from "./ui";

export type ProductionInput = {
  title: string;
  slug?: string;
  short_description: string | null;
  description: string | null;
  genres: string[];
  duration_minutes: number | null;
  act_count: number | null;
  duration_text: string | null;
  is_featured: boolean;
  on_stage: boolean;
  sort_order: number;
  home_order: number | null;
  credits: { role: CreditRole; role_label: string | null; name: string }[];
  videos: { url: string; title: string | null }[];
};

const ROLES = Object.keys(CREDIT_ROLE_LABELS) as CreditRole[];

export function toInput(p?: Production | null): ProductionInput {
  return {
    title: p?.title ?? "",
    slug: p?.slug,
    short_description: p?.short_description ?? null,
    description: p?.description ?? null,
    genres: p?.genres ?? [],
    duration_minutes: p?.duration_minutes ?? null,
    act_count: p?.act_count ?? null,
    duration_text: p?.duration_text ?? null,
    is_featured: p?.is_featured ?? false,
    on_stage: p?.on_stage ?? false,
    sort_order: p?.sort_order ?? 0,
    home_order: p?.home_order ?? null,
    credits: (p?.credits ?? []).map((c) => ({ role: c.role, role_label: c.role === "other" ? c.label ?? null : null, name: c.name })),
    videos: (p?.videos ?? []).map((v) => ({ url: v.url, title: v.title })),
  };
}

export function validate(v: ProductionInput): Record<string, string> {
  const e: Record<string, string> = {};
  if (!v.title.trim()) e.title = "Oyun adı zorunludur.";
  if (v.duration_minutes !== null && (v.duration_minutes < 1 || v.duration_minutes > 1440)) e.duration_minutes = "1 ile 1440 dakika arasında olmalıdır.";
  if (v.act_count !== null && (v.act_count < 1 || v.act_count > 20)) e.act_count = "1 ile 20 arasında olmalıdır.";
  if (v.home_order !== null && (v.home_order < 1 || v.home_order > 1000)) e.home_order = "1 ile 1000 arasında olmalıdır.";
  v.credits.forEach((c, i) => {
    if (!c.name.trim()) e[`credits.${i}.name`] = "İsim zorunludur.";
    if (c.role === "other" && !c.role_label?.trim()) e[`credits.${i}.role_label`] = "Görev adını yazın.";
  });
  v.videos.forEach((vid, i) => {
    if (!/^https:\/\/\S+$/.test(vid.url.trim())) e[`videos.${i}.url`] = "Bağlantı https:// ile başlamalıdır.";
  });
  return e;
}

function num(s: string): number | null {
  if (!s.trim()) return null;
  const n = Number(s);
  return Number.isFinite(n) ? Math.trunc(n) : null;
}

export function ProductionForm({
  initial,
  submitLabel,
  onSubmit,
}: {
  initial: ProductionInput;
  submitLabel: string;
  onSubmit: (v: ProductionInput) => Promise<void>;
}) {
  const [v, setV] = useState<ProductionInput>(initial);
  const [genresText, setGenresText] = useState(initial.genres.join(", "));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof ProductionInput>(k: K, val: ProductionInput[K]) => setV((s) => ({ ...s, [k]: val }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    const payload: ProductionInput = {
      ...v,
      genres: genresText.split(",").map((g) => g.trim()).filter(Boolean),
      credits: v.credits.map((c) => ({ ...c, role_label: c.role === "other" ? c.role_label : null })),
    };
    const errs = validate(payload);
    setErrors(errs);
    setFormError(null);
    if (Object.keys(errs).length) {
      setFormError("Lütfen işaretli alanları düzeltin.");
      return;
    }
    setBusy(true);
    try {
      await onSubmit(payload);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.fields);
        setFormError(err.message);
      } else setFormError("Kaydedilemedi.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="stack" aria-label="Oyun bilgileri">
      {formError && (
        <div className="alert alert-error" role="alert">
          {formError}
        </div>
      )}
      <div className="card stack">
        <h2>Temel bilgiler</h2>
        <Field label="Oyun adı" required error={errors.title}>
          {(p) => <input {...p} className="input" value={v.title} onChange={(e) => set("title", e.target.value)} maxLength={200} />}
        </Field>
        {initial.slug !== undefined && (
          <Field label="Kısa ad (bağlantı)" hint="Uygulama bağlantılarında kullanılır. Yalnızca küçük harf, rakam ve tire." error={errors.slug}>
            {(p) => <input {...p} className="input" value={v.slug ?? ""} onChange={(e) => set("slug", e.target.value)} maxLength={150} />}
          </Field>
        )}
        <Field label="Kısa açıklama" hint="Listelerde görünür. Boş bırakılırsa hikâyenin başı kullanılır." error={errors.short_description}>
          {(p) => (
            <textarea {...p} className="textarea" style={{ minHeight: 70 }} maxLength={400} value={v.short_description ?? ""} onChange={(e) => set("short_description", e.target.value || null)} />
          )}
        </Field>
        <Field label="Hikâye / açıklama" error={errors.description}>
          {(p) => (
            <textarea {...p} className="textarea" style={{ minHeight: 200 }} value={v.description ?? ""} onChange={(e) => set("description", e.target.value || null)} />
          )}
        </Field>
        <Field label="Tür" hint="Birden fazlaysa virgülle ayırın (ör. Dram, Gerilim)." error={errors.genres}>
          {(p) => <input {...p} className="input" value={genresText} onChange={(e) => setGenresText(e.target.value)} />}
        </Field>
      </div>

      <div className="card stack">
        <h2>Süre</h2>
        <div className="grid grid-3">
          <Field label="Süre (dakika)" error={errors.duration_minutes}>
            {(p) => <input {...p} className="input" inputMode="numeric" value={v.duration_minutes ?? ""} onChange={(e) => set("duration_minutes", num(e.target.value))} />}
          </Field>
          <Field label="Perde sayısı" error={errors.act_count}>
            {(p) => <input {...p} className="input" inputMode="numeric" value={v.act_count ?? ""} onChange={(e) => set("act_count", num(e.target.value))} />}
          </Field>
          <Field label="Süre (serbest metin)" hint="Sayısal değer yoksa gösterilir." error={errors.duration_text}>
            {(p) => <input {...p} className="input" maxLength={120} value={v.duration_text ?? ""} onChange={(e) => set("duration_text", e.target.value || null)} />}
          </Field>
        </div>
      </div>

      <div className="card stack">
        <div className="card-head" style={{ margin: 0 }}>
          <h2>Künye</h2>
          <button type="button" className="btn btn-sm" onClick={() => set("credits", [...v.credits, { role: "cast", role_label: null, name: "" }])}>
            Kişi ekle
          </button>
        </div>
        {v.credits.length === 0 && <p className="muted small">Henüz künye bilgisi yok.</p>}
        {v.credits.map((c, i) => (
          <fieldset key={i} className="grid" style={{ gridTemplateColumns: "180px 1fr 1fr auto", alignItems: "end" }}>
            <legend className="sr-only">Künye satırı {i + 1}</legend>
            <Field label="Görev">
              {(p) => (
                <select
                  {...p}
                  className="select"
                  value={c.role}
                  onChange={(e) => set("credits", v.credits.map((x, j) => (j === i ? { ...x, role: e.target.value as CreditRole } : x)))}
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {CREDIT_ROLE_LABELS[r]}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            {c.role === "other" ? (
              <Field label="Görev adı" error={errors[`credits.${i}.role_label`]}>
                {(p) => (
                  <input {...p} className="input" value={c.role_label ?? ""} onChange={(e) => set("credits", v.credits.map((x, j) => (j === i ? { ...x, role_label: e.target.value } : x)))} />
                )}
              </Field>
            ) : (
              <div />
            )}
            <Field label="İsim" error={errors[`credits.${i}.name`]}>
              {(p) => <input {...p} className="input" value={c.name} onChange={(e) => set("credits", v.credits.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} />}
            </Field>
            <div className="row" style={{ gap: 4, paddingBottom: 2 }}>
              <button type="button" className="btn btn-sm" aria-label="Yukarı taşı" disabled={i === 0} onClick={() => set("credits", move(v.credits, i, -1))}>
                ↑
              </button>
              <button type="button" className="btn btn-sm" aria-label="Aşağı taşı" disabled={i === v.credits.length - 1} onClick={() => set("credits", move(v.credits, i, 1))}>
                ↓
              </button>
              <button type="button" className="btn btn-sm btn-danger" aria-label="Satırı kaldır" onClick={() => set("credits", v.credits.filter((_, j) => j !== i))}>
                Kaldır
              </button>
            </div>
          </fieldset>
        ))}
      </div>

      <div className="card stack">
        <div className="card-head" style={{ margin: 0 }}>
          <h2>Video bağlantıları</h2>
          <button type="button" className="btn btn-sm" onClick={() => set("videos", [...v.videos, { url: "", title: null }])}>
            Video ekle
          </button>
        </div>
        {v.videos.length === 0 && <p className="muted small">Fragman veya tanıtım videosu bağlantısı ekleyebilirsiniz (YouTube önerilir).</p>}
        {v.videos.map((vid, i) => (
          <fieldset key={i} className="grid" style={{ gridTemplateColumns: "2fr 1fr auto", alignItems: "end" }}>
            <legend className="sr-only">Video {i + 1}</legend>
            <Field label="Bağlantı" error={errors[`videos.${i}.url`]}>
              {(p) => <input {...p} className="input" placeholder="https://youtu.be/…" value={vid.url} onChange={(e) => set("videos", v.videos.map((x, j) => (j === i ? { ...x, url: e.target.value } : x)))} />}
            </Field>
            <Field label="Başlık">
              {(p) => <input {...p} className="input" value={vid.title ?? ""} onChange={(e) => set("videos", v.videos.map((x, j) => (j === i ? { ...x, title: e.target.value || null } : x)))} />}
            </Field>
            <button type="button" className="btn btn-sm btn-danger" onClick={() => set("videos", v.videos.filter((_, j) => j !== i))}>
              Kaldır
            </button>
          </fieldset>
        ))}
      </div>

      <div className="card stack">
        <h2>Uygulamada gösterim</h2>
        <label className="check">
          <input type="checkbox" checked={v.is_featured} onChange={(e) => set("is_featured", e.target.checked)} />
          <span>
            <strong>Öne çıkan</strong>
            <br />
            <span className="small muted">Ana sayfanın en üstündeki vitrinde gösterilir.</span>
          </span>
        </label>
        <label className="check">
          <input type="checkbox" checked={v.on_stage} onChange={(e) => set("on_stage", e.target.checked)} />
          <span>
            <strong>Sahnede</strong>
            <br />
            <span className="small muted">Güncel repertuvar etiketi. Temsil tarihlerinden bağımsızdır.</span>
          </span>
        </label>
        <Field
          label="Ana sayfa sırası"
          hint="Ana sayfadaki Repertuvar şeridinde soldan sağa kaçıncı sırada duracağı (1, 2, 3…). Boş bırakılırsa oyun bu şeritte gösterilmez."
          error={errors.home_order}
        >
          {(p) => <input {...p} className="input" style={{ maxWidth: 140 }} inputMode="numeric" value={v.home_order ?? ""} onChange={(e) => set("home_order", num(e.target.value))} />}
        </Field>
        <Field label="Sıralama" hint="Oyunlar listesindeki sıra. Küçük sayı önce gösterilir.">
          {(p) => <input {...p} className="input" style={{ maxWidth: 140 }} inputMode="numeric" value={v.sort_order} onChange={(e) => set("sort_order", num(e.target.value) ?? 0)} />}
        </Field>
      </div>

      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {busy ? "Kaydediliyor…" : submitLabel}
        </button>
      </div>
    </form>
  );
}

function move<T>(arr: T[], i: number, d: number): T[] {
  const out = [...arr];
  const [x] = out.splice(i, 1);
  out.splice(i + d, 0, x);
  return out;
}
