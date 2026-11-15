"use client";

import { useState, type FormEvent } from "react";
import { ApiError } from "@/lib/api";
import { Field } from "./ui";

export const MIN_PASSWORD = 10;

export function SetPasswordForm({
  submitLabel,
  onSubmit,
}: {
  submitLabel: string;
  onSubmit: (password: string) => Promise<void>;
}) {
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (pw.length < MIN_PASSWORD) errs.pw = `Parola en az ${MIN_PASSWORD} karakter olmalıdır.`;
    if (pw !== pw2) errs.pw2 = "Parolalar eşleşmiyor.";
    setErrors(errs);
    setFormError(null);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try {
      await onSubmit(pw);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "İşlem tamamlanamadı.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="stack">
      {formError && (
        <div className="alert alert-error" role="alert">
          {formError}
        </div>
      )}
      <Field label="Yeni parola" error={errors.pw} hint={`En az ${MIN_PASSWORD} karakter. Uzun bir cümle iyi bir seçimdir.`}>
        {(p) => <input {...p} className="input" type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} />}
      </Field>
      <Field label="Yeni parola (tekrar)" error={errors.pw2}>
        {(p) => <input {...p} className="input" type="password" autoComplete="new-password" value={pw2} onChange={(e) => setPw2(e.target.value)} />}
      </Field>
      <button className="btn btn-primary" type="submit" disabled={busy}>
        {busy ? "Kaydediliyor…" : submitLabel}
      </button>
    </form>
  );
}
