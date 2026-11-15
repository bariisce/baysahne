"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import { Field } from "./ui";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!email.trim()) errs.email = "E-posta adresinizi girin.";
    if (!password) errs.password = "Parolanızı girin.";
    setErrors(errs);
    setFormError(null);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try {
      await api.post("/admin/auth/login", { email: email.trim(), password });
      router.replace("/");
    } catch (err) {
      if (err instanceof ApiError && err.code === "validation_error") setErrors({ email: "Geçerli bir e-posta adresi girin." });
      else setFormError(err instanceof ApiError ? err.message : "Giriş yapılamadı.");
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
      <Field label="E-posta" error={errors.email}>
        {(p) => <input {...p} className="input" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />}
      </Field>
      <Field label="Parola" error={errors.password}>
        {(p) => (
          <input {...p} className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        )}
      </Field>
      <button className="btn btn-primary" type="submit" disabled={busy}>
        {busy ? "Giriş yapılıyor…" : "Giriş yap"}
      </button>
      <Link href="/parola-sifirla" className="small" style={{ textAlign: "center" }}>
        Parolamı unuttum
      </Link>
    </form>
  );
}
