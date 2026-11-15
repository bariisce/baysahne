"use client";

import { useState, type FormEvent } from "react";
import { useAuth } from "@/components/auth";
import { useFeedback } from "@/components/feedback";
import { MIN_PASSWORD } from "@/components/SetPasswordForm";
import { ROLE_LABELS } from "@/components/Shell";
import { Card, Field, PageHeader } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";

export default function AccountPage() {
  const { user } = useAuth();
  const { toast } = useFeedback();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  async function submit(e: FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!current) errs.current = "Mevcut parolanızı girin.";
    if (next.length < MIN_PASSWORD) errs.next = `Yeni parola en az ${MIN_PASSWORD} karakter olmalıdır.`;
    setErrors(errs);
    if (Object.keys(errs).length) return;
    try {
      await api.post("/admin/auth/password/change", { current_password: current, new_password: next });
      setCurrent("");
      setNext("");
      toast("Parolanız güncellendi.");
    } catch (err) {
      setErrors({ _: errorMessage(err) });
    }
  }

  return (
    <>
      <PageHeader title="Hesabım" description={`${user.full_name} · ${user.email} · ${ROLE_LABELS[user.role]}`} />
      <Card title="Parola değiştir">
        <form onSubmit={submit} noValidate className="stack" style={{ maxWidth: 420 }}>
          {errors._ && <div className="alert alert-error" role="alert">{errors._}</div>}
          <Field label="Mevcut parola" error={errors.current}>
            {(p) => <input {...p} className="input" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />}
          </Field>
          <Field label="Yeni parola" error={errors.next}>
            {(p) => <input {...p} className="input" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />}
          </Field>
          <div><button className="btn btn-primary">Parolayı güncelle</button></div>
        </form>
      </Card>
    </>
  );
}
