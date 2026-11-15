"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthLayout } from "@/components/AuthLayout";
import { SetPasswordForm } from "@/components/SetPasswordForm";
import { ROLE_LABELS } from "@/components/Shell";
import { Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useHashToken } from "@/lib/use-hash-token";

type Invitation = { email: string; full_name: string; role: "admin" | "editor"; expires_at: string };

export default function AcceptInvitationPage() {
  const token = useHashToken();
  const router = useRouter();
  const [inv, setInv] = useState<Invitation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (token === undefined) return;
    let cancelled = false;
    const check = token
      ? api.post<Invitation>("/admin/auth/invitations/inspect", { token })
      : Promise.reject(new Error("missing"));
    check
      .then((r) => !cancelled && setInv(r))
      .catch((e) => !cancelled && setError(token ? errorMessage(e) : "Davet bağlantısı eksik. E-postadaki bağlantıyı eksiksiz açın."));
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <AuthLayout title="Daveti kabul edin" lead="Bay Sahne yönetim paneli hesabınızı oluşturun.">
      {!inv && !error && <Spinner />}
      {error && (
        <div className="alert alert-error" role="alert">
          {error}
        </div>
      )}
      {inv && token && (
        <div className="stack">
          <div className="alert alert-info">
            <strong>{inv.full_name}</strong>
            <br />
            {inv.email} · {ROLE_LABELS[inv.role]}
          </div>
          <SetPasswordForm
            submitLabel="Hesabımı oluştur"
            onSubmit={async (password) => {
              await api.post("/admin/auth/invitations/accept", { token, password });
              router.replace("/");
            }}
          />
        </div>
      )}
    </AuthLayout>
  );
}
