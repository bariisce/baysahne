"use client";

import { useState } from "react";
import { useIsAdmin } from "@/components/auth";
import { useFeedback } from "@/components/feedback";
import { Badge, Card, EmptyState, ErrorBox, PageHeader, Pager, Spinner } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api";
import { CANCEL_REASON_LABELS, formatDateTime, leadLabel } from "@/lib/format";
import type { CategorySetting, NotificationJob, NotificationSettings, Page } from "@/lib/types";
import { useResource } from "@/lib/useResource";

export default function NotificationsPage() {
  const settings = useResource<NotificationSettings>("/admin/notifications/settings");
  const isAdmin = useIsAdmin();
  const s = settings.data;

  return (
    <>
      <PageHeader
        title="Bildirimler"
        description="Bildirimler, uygulamayı yükleyip bildirim izni veren cihazlara gider. Teslimat cihaz ayarlarına, bağlantıya ve sağlayıcıya bağlıdır; her cihaza ulaşacağı garanti edilmez."
      />
      {settings.error && <ErrorBox message={settings.error.message} onRetry={settings.reload} />}
      {!s && !settings.error && <Spinner />}
      {s && (
        <div className="stack">
          <div className="grid grid-3">
            <div className="card">
              <div className="stat">{(s.devices.ios ?? 0) + (s.devices.android ?? 0)}</div>
              <div className="stat-label">İzin veren cihaz (iOS {s.devices.ios ?? 0} · Android {s.devices.android ?? 0})</div>
            </div>
            <div className="card">
              <div className="stat" style={{ fontSize: 22 }}>{s.policy.reminder_lead_minutes.map(leadLabel).join(", ") || "Kapalı"}</div>
              <div className="stat-label">Temsil hatırlatması zamanı</div>
            </div>
            <div className="card">
              <div className="stat" style={{ fontSize: 22 }}>{s.provider === "expo" ? "Gerçek gönderim" : "Geliştirme modu"}</div>
              <div className="stat-label">{s.provider === "expo" ? "Expo Push (FCM/APNs)" : `Sağlayıcı: ${s.provider} — cihazlara gerçek bildirim gitmez`}</div>
            </div>
          </div>
          {!isAdmin && <div className="alert alert-info">Bildirim ayarlarını yalnızca yöneticiler değiştirebilir. Gönderim geçmişini görebilirsiniz.</div>}
          <PolicyCard s={s} editable={isAdmin} onSaved={settings.setData} />
          {s.categories.map((c) => (
            <CategoryCard key={c.category} c={c} editable={isAdmin} onSaved={settings.setData} />
          ))}
          <JobsCard isAdmin={isAdmin} />
        </div>
      )}
    </>
  );
}

function PolicyCard({ s, editable, onSaved }: { s: NotificationSettings; editable: boolean; onSaved: (s: NotificationSettings) => void }) {
  const { toast } = useFeedback();
  const [hours, setHours] = useState(s.policy.reminder_lead_minutes.map((m) => String(m / 60)).join(", "));
  const [max, setMax] = useState(String(s.policy.max_per_device_per_day));
  const [cooldown, setCooldown] = useState(String(s.policy.broadcast_cooldown_minutes));
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    const leads = hours.split(",").map((h) => h.trim()).filter(Boolean).map((h) => Math.round(Number(h.replace(",", ".")) * 60));
    if (leads.some((l) => !Number.isFinite(l) || l < 30 || l > 20160)) return setErr("Hatırlatma süreleri 0,5 ile 336 saat arasında olmalıdır.");
    setErr(null);
    try {
      onSaved(await api.put<NotificationSettings>("/admin/notifications/policy", {
        reminder_lead_minutes: leads,
        max_per_device_per_day: Number(max),
        broadcast_cooldown_minutes: Number(cooldown),
      }));
      toast("Bildirim kuralları kaydedildi.");
    } catch (e) {
      setErr(errorMessage(e));
    }
  }

  return (
    <Card title="Kurallar">
      <div className="grid grid-3">
        <label className="field">
          <span className="label">Hatırlatma (temsilden kaç saat önce)</span>
          <input className="input" disabled={!editable} value={hours} onChange={(e) => setHours(e.target.value)} />
          <span className="hint">Birden fazla için virgülle ayırın (ör. 24, 3). Boş bırakılırsa hatırlatma gönderilmez.</span>
        </label>
        <label className="field">
          <span className="label">Cihaz başına günlük üst sınır</span>
          <input className="input" type="number" min={0} max={20} disabled={!editable} value={max} onChange={(e) => setMax(e.target.value)} />
          <span className="hint">Yeni oyun ve hatırlatmalar için. İptal/tarih değişikliği bildirimleri sınırdan muaftır. 0 = sınırsız.</span>
        </label>
        <label className="field">
          <span className="label">Yeni oyun bildirimleri arası (dakika)</span>
          <input className="input" type="number" min={0} disabled={!editable} value={cooldown} onChange={(e) => setCooldown(e.target.value)} />
          <span className="hint">Arka arkaya yayınlanan oyunların bildirimleri bu süreyle aralıklandırılır.</span>
        </label>
      </div>
      {err && <div className="alert alert-error" style={{ marginTop: 12 }} role="alert">{err}</div>}
      {editable && (
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 12 }}>
          <button className="btn btn-primary" onClick={save}>Kuralları kaydet</button>
        </div>
      )}
    </Card>
  );
}

function CategoryCard({ c, editable, onSaved }: { c: CategorySetting; editable: boolean; onSaved: (s: NotificationSettings) => void }) {
  const { toast } = useFeedback();
  const [enabled, setEnabled] = useState(c.enabled);
  const [title, setTitle] = useState(c.title_template);
  const [body, setBody] = useState(c.body_template);
  const [preview, setPreview] = useState<{ title: string; body: string } | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  async function doPreview() {
    try {
      setPreview(await api.post("/admin/notifications/preview", { category: c.category, title_template: title, body_template: body }));
      setErrors({});
    } catch (e) {
      setErrors({ _: errorMessage(e) });
    }
  }

  async function save() {
    try {
      onSaved(await api.put<NotificationSettings>(`/admin/notifications/categories/${c.category}`, { enabled, title_template: title, body_template: body }));
      setErrors({});
      toast("Bildirim şablonu kaydedildi.");
    } catch (e) {
      if (e instanceof ApiError) setErrors({ ...e.fields, _: e.message });
      else setErrors({ _: "Kaydedilemedi." });
    }
  }

  return (
    <Card title={c.label} actions={<Badge status={c.enabled ? "published" : "archived"}>{c.enabled ? "Açık" : "Kapalı"}</Badge>}>
      <div className="grid grid-2">
        <div className="stack">
          {editable && (
            <label className="check">
              <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
              <span>Bu bildirim türü açık</span>
            </label>
          )}
          <label className="field">
            <span className="label">Başlık</span>
            <input className="input" maxLength={120} disabled={!editable} value={title} aria-invalid={!!errors.title_template} onChange={(e) => setTitle(e.target.value)} />
            {errors.title_template && <span className="error">{errors.title_template}</span>}
          </label>
          <label className="field">
            <span className="label">Metin</span>
            <textarea className="textarea" style={{ minHeight: 70 }} maxLength={400} disabled={!editable} value={body} aria-invalid={!!errors.body_template} onChange={(e) => setBody(e.target.value)} />
            {errors.body_template && <span className="error">{errors.body_template}</span>}
          </label>
          <div className="small muted">
            Kullanılabilir alanlar:{" "}
            {c.placeholders.map((p) => (
              <span key={p.name} className="code" title={p.label} style={{ marginRight: 6 }}>
                {`{${p.name}}`}
              </span>
            ))}
          </div>
          {errors._ && <div className="alert alert-error" role="alert">{errors._}</div>}
          <div className="row">
            <button className="btn" onClick={doPreview}>Önizle</button>
            {editable && <button className="btn btn-primary" onClick={save}>Kaydet</button>}
          </div>
        </div>
        <div>
          <span className="label">Önizleme (örnek verilerle)</span>
          <div className="notif-preview" style={{ marginTop: 8 }} aria-live="polite">
            {preview ? (
              <>
                <strong>{preview.title}</strong>
                {preview.body}
              </>
            ) : (
              <span className="muted">“Önizle”ye basın.</span>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

function JobsCard({ isAdmin }: { isAdmin: boolean }) {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const res = useResource<Page<NotificationJob>>(`/admin/notifications/jobs?page=${page}&page_size=25${status ? `&status=${status}` : ""}`);
  const { toast, confirm } = useFeedback();

  async function act(path: string, ok: string) {
    try {
      await api.post(path);
      toast(ok);
      res.reload();
    } catch (e) {
      toast(errorMessage(e), "error");
    }
  }

  return (
    <Card
      title="Gönderim geçmişi"
      actions={
        <div className="row">
          <select className="select" aria-label="Duruma göre filtrele" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">Tümü</option>
            <option value="pending">Bekliyor</option>
            <option value="sent">Gönderildi</option>
            <option value="failed">Başarısız</option>
            <option value="cancelled">İptal edildi</option>
          </select>
          <button className="btn btn-sm" onClick={res.reload}>Yenile</button>
        </div>
      }
    >
      {res.error && <ErrorBox message={res.error.message} onRetry={res.reload} />}
      {res.loading && !res.data && <Spinner />}
      {res.data?.items.length === 0 && <EmptyState title="Kayıt yok" />}
      {res.data && res.data.items.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Tür</th>
                <th>Planlanan</th>
                <th>Durum</th>
                <th>İçerik</th>
                <th>Sonuç</th>
                <th aria-label="İşlemler" />
              </tr>
            </thead>
            <tbody>
              {res.data.items.map((j) => (
                <tr key={j.id}>
                  <td>
                    {j.category_label}
                    {j.lead_minutes ? <div className="small muted">{leadLabel(j.lead_minutes)}</div> : null}
                  </td>
                  <td className="small">{formatDateTime(j.scheduled_for)}</td>
                  <td>
                    <Badge status={j.status} />
                    {j.cancel_reason && <div className="small muted">{CANCEL_REASON_LABELS[j.cancel_reason] ?? j.cancel_reason}</div>}
                  </td>
                  <td className="small">
                    {j.title ? (
                      <>
                        <strong>{j.title}</strong>
                        <br />
                        {j.body}
                      </>
                    ) : (
                      <span className="muted">Gönderim anında oluşturulur</span>
                    )}
                  </td>
                  <td className="small">
                    {j.status === "sent" && (
                      <>
                        {j.stats.ok ?? 0} iletildi
                        {j.stats.error ? `, ${j.stats.error} hata` : ""}
                        {j.stats.rate_limited ? `, ${j.stats.rate_limited} sınır nedeniyle atlandı` : ""}
                      </>
                    )}
                    {j.last_error && <div style={{ color: "var(--danger)" }}>{j.last_error} (deneme {j.attempts}/{j.max_attempts})</div>}
                  </td>
                  <td>
                    {isAdmin && j.status === "pending" && (
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={async () => {
                          if (await confirm({ title: "Bekleyen bildirim iptal edilsin mi?", confirmLabel: "İptal et", danger: true }))
                            act(`/admin/notifications/jobs/${j.id}/cancel`, "Bildirim iptal edildi.");
                        }}
                      >
                        İptal et
                      </button>
                    )}
                    {isAdmin && j.status === "failed" && (
                      <button
                        className="btn btn-sm"
                        onClick={async () => {
                          if (await confirm({ title: "Yeniden denensin mi?", body: "Bildirimi daha önce almış cihazlara tekrar gönderilmez.", confirmLabel: "Yeniden dene" }))
                            act(`/admin/notifications/jobs/${j.id}/retry`, "Bildirim yeniden kuyruğa alındı.");
                        }}
                      >
                        Yeniden dene
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {res.data && <Pager page={page} pageSize={25} total={res.data.total} onPage={setPage} />}
    </Card>
  );
}
