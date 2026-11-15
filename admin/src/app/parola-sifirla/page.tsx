"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { AuthLayout } from "@/components/AuthLayout";
import { Field } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!email.trim()) return setError("E-posta adresinizi girin.");
    setBusy(true);
    setError(null);
    try {
      const r = await api.post<{ message: string }>("/admin/auth/password/forgot", { email: email.trim() });
      setSent(r.message);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout title="Parola sıfırlama" lead="Kayıtlı e-posta adresinize bir sıfırlama bağlantısı göndereceğiz.">
      {sent ? (
        <div className="stack">
          <div className="alert alert-success" role="status">
            {sent}
          </div>
          <Link href="/giris" className="btn">
            Girişe dön
          </Link>
        </div>
      ) : (
        <form onSubmit={submit} noValidate className="stack">
          <Field label="E-posta" error={error ?? undefined}>
            {(p) => <input {...p} className="input" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />}
          </Field>
          <button className="btn btn-primary" disabled={busy}>
            {busy ? "Gönderiliyor…" : "Bağlantı gönder"}
          </button>
          <Link href="/giris" className="small" style={{ textAlign: "center" }}>
            Girişe dön
          </Link>
        </form>
      )}
    </AuthLayout>
  );
}
