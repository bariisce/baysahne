"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthLayout } from "@/components/AuthLayout";
import { SetPasswordForm } from "@/components/SetPasswordForm";
import { Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useHashToken } from "@/lib/use-hash-token";

export default function ResetPasswordPage() {
  const token = useHashToken();
  const [done, setDone] = useState(false);
  return (
    <AuthLayout title="Yeni parola belirleyin">
      {token === undefined && <Spinner />}
      {token === "" && (
        <div className="alert alert-error" role="alert">
          Sıfırlama bağlantısı eksik. E-postadaki bağlantıyı eksiksiz açın veya yeni bir bağlantı isteyin.
        </div>
      )}
      {done ? (
        <div className="stack">
          <div className="alert alert-success" role="status">
            Parolanız güncellendi. Güvenliğiniz için tüm oturumlar kapatıldı.
          </div>
          <Link href="/giris" className="btn btn-primary">
            Giriş yap
          </Link>
        </div>
      ) : (
        token && (
          <SetPasswordForm
            submitLabel="Parolayı güncelle"
            onSubmit={async (password) => {
              await api.post("/admin/auth/password/reset", { token, password });
              setDone(true);
            }}
          />
        )
      )}
    </AuthLayout>
  );
}
