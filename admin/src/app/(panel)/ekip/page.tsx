"use client";

import { useState, type FormEvent } from "react";
import { AdminOnly, useAuth } from "@/components/auth";
import { Modal, useFeedback } from "@/components/feedback";
import { ROLE_LABELS } from "@/components/Shell";
import { Badge, Card, EmptyState, ErrorBox, Field, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { Role } from "@/lib/types";
import { useResource } from "@/lib/useResource";

type User = { id: string; email: string; full_name: string; role: Role; is_active: boolean; last_login_at: string | null; locked: boolean };
type Invitation = { id: string; email: string; full_name: string; role: Role; state: string; expires_at: string; invited_by: string | null };

const INVITE_STATES: Record<string, string> = { pending: "Bekliyor", accepted: "Kabul edildi", revoked: "İptal edildi", expired: "Süresi doldu" };

export default function StaffPage() {
  return (
    <AdminOnly fallback={<div className="alert alert-warn">Bu sayfaya yalnızca yöneticiler erişebilir.</div>}>
      <Staff />
    </AdminOnly>
  );
}

function Staff() {
  const res = useResource<{ users: User[]; invitations: Invitation[] }>("/admin/users");
  const { user: me } = useAuth();
  const { toast, confirm } = useFeedback();
  const [inviting, setInviting] = useState(false);

  async function act(fn: () => Promise<unknown>, ok: string) {
    try {
      await fn();
      toast(ok);
      res.reload();
    } catch (e) {
      toast(errorMessage(e), "error");
    }
  }

  return (
    <>
      <PageHeader
        title="Ekip ve erişim"
        description="Panel hesapları yalnızca davetle açılır. İçerik editörleri oyun, program, salon, duyuru ve görselleri yönetebilir; yöneticiler ayrıca ekip, bildirim kuralları, kurum bilgileri ve kayıtları yönetir."
        actions={<button className="btn btn-primary" onClick={() => setInviting(true)}>Kişi davet et</button>}
      />
      {res.error && <ErrorBox message={res.error.message} onRetry={res.reload} />}
      {res.loading && !res.data && <Spinner />}
      {res.data && (
        <div className="stack">
          <Card title="Kullanıcılar">
            <table className="table">
              <thead>
                <tr>
                  <th>Kişi</th>
                  <th>Rol</th>
                  <th>Son giriş</th>
                  <th>Durum</th>
                  <th aria-label="İşlemler" />
                </tr>
              </thead>
              <tbody>
                {res.data.users.map((u) => (
                  <tr key={u.id}>
                    <td><strong>{u.full_name}</strong><div className="small muted">{u.email}</div></td>
                    <td>
                      <select
                        className="select"
                        aria-label={`${u.full_name} rolü`}
                        value={u.role}
                        disabled={u.id === me.id}
                        onChange={(e) => act(() => api.patch(`/admin/users/${u.id}`, { role: e.target.value }), "Rol güncellendi.")}
                      >
                        <option value="editor">{ROLE_LABELS.editor}</option>
                        <option value="admin">{ROLE_LABELS.admin}</option>
                      </select>
                    </td>
                    <td className="small">{formatDateTime(u.last_login_at)}</td>
                    <td>
                      <Badge status={u.is_active ? "published" : "archived"}>{u.is_active ? "Aktif" : "Erişim kapalı"}</Badge>
                      {u.locked && <div className="small" style={{ color: "var(--warn)" }}>Geçici kilitli</div>}
                    </td>
                    <td>
                      {u.id !== me.id &&
                        (u.is_active ? (
                          <button
                            className="btn btn-sm btn-danger"
                            onClick={async () => {
                              if (await confirm({ title: `${u.full_name} için erişim kapatılsın mı?`, body: "Tüm açık oturumları hemen sonlandırılır. Kayıtları silinmez; daha sonra yeniden açılabilir.", confirmLabel: "Erişimi kapat", danger: true }))
                                act(() => api.post(`/admin/users/${u.id}/deactivate`), "Erişim kapatıldı.");
                            }}
                          >
                            Erişimi kapat
                          </button>
                        ) : (
                          <button className="btn btn-sm" onClick={() => act(() => api.post(`/admin/users/${u.id}/reactivate`), "Erişim yeniden açıldı.")}>
                            Yeniden aç
                          </button>
                        ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <Card title="Davetler">
            {res.data.invitations.length === 0 ? (
              <EmptyState title="Henüz davet yok" />
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Kişi</th>
                    <th>Rol</th>
                    <th>Durum</th>
                    <th>Geçerlilik</th>
                    <th aria-label="İşlemler" />
                  </tr>
                </thead>
                <tbody>
                  {res.data.invitations.map((i) => (
                    <tr key={i.id}>
                      <td><strong>{i.full_name}</strong><div className="small muted">{i.email}</div></td>
                      <td>{ROLE_LABELS[i.role]}</td>
                      <td><Badge status={i.state}>{INVITE_STATES[i.state]}</Badge></td>
                      <td className="small">{formatDateTime(i.expires_at)}</td>
                      <td>
                        <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
                          {(i.state === "pending" || i.state === "expired") && (
                            <button className="btn btn-sm" onClick={() => act(() => api.post(`/admin/invitations/${i.id}/resend`), "Yeni davet bağlantısı gönderildi.")}>
                              Yeniden gönder
                            </button>
                          )}
                          {i.state === "pending" && (
                            <button className="btn btn-sm btn-danger" onClick={() => act(() => api.del(`/admin/invitations/${i.id}`), "Davet iptal edildi.")}>
                              İptal et
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </div>
      )}
      <Modal open={inviting} onClose={() => setInviting(false)} title="Kişi davet et">
        {inviting && (
          <InviteForm
            onCancel={() => setInviting(false)}
            onDone={() => {
              setInviting(false);
              toast("Davet e-postası gönderildi.");
              res.reload();
            }}
          />
        )}
      </Modal>
    </>
  );
}

function InviteForm({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("editor");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!name.trim()) errs.full_name = "Ad soyad zorunludur.";
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) errs.email = "Geçerli bir e-posta adresi girin.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try {
      await api.post("/admin/invitations", { full_name: name.trim(), email: email.trim(), role });
      onDone();
    } catch (err) {
      setErrors(err instanceof ApiError ? { ...err.fields, _: err.message } : { _: "Davet gönderilemedi." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="stack">
      {errors._ && <div className="alert alert-error" role="alert">{errors._}</div>}
      <Field label="Ad soyad" required error={errors.full_name}>
        {(p) => <input {...p} className="input" value={name} onChange={(e) => setName(e.target.value)} />}
      </Field>
      <Field label="E-posta" required error={errors.email}>
        {(p) => <input {...p} className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />}
      </Field>
      <Field label="Rol">
        {(p) => (
          <select {...p} className="select" value={role} onChange={(e) => setRole(e.target.value as Role)}>
            <option value="editor">İçerik editörü — oyun, program, salon, duyuru, görsel</option>
            <option value="admin">Yönetici — ayrıca ekip, bildirim kuralları, kurum bilgileri</option>
          </select>
        )}
      </Field>
      <p className="small muted" style={{ margin: 0 }}>Kişiye tek kullanımlık, süreli bir bağlantı gönderilir. Parolasını kendisi belirler.</p>
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="btn" onClick={onCancel}>Vazgeç</button>
        <button className="btn btn-primary" disabled={busy}>{busy ? "Gönderiliyor…" : "Davet gönder"}</button>
      </div>
    </form>
  );
}
