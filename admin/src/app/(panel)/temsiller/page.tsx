"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Modal, useFeedback } from "@/components/feedback";
import { PerformanceForm, type PerformanceInput } from "@/components/PerformanceForm";
import { Badge, EmptyState, ErrorBox, PageHeader, Pager, Spinner } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api";
import { todayInIstanbul } from "@/lib/format";
import type { Page, Performance, ProductionSummary, Venue } from "@/lib/types";
import { useResource } from "@/lib/useResource";

function toLocal(v: PerformanceInput) {
  return `${v.date}T${v.time}`;
}

export default function PerformancesPage() {
  const search = useSearchParams();
  const { toast, confirm } = useFeedback();
  const [scope, setScope] = useState<"upcoming" | "past">("upcoming");
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(search.get("yeni") === "1");
  const [editing, setEditing] = useState<Performance | null>(null);
  const [rescheduling, setRescheduling] = useState<Performance | null>(null);
  const [cancelling, setCancelling] = useState<Performance | null>(null);

  const list = useResource<Page<Performance>>(`/admin/performances?scope=${scope}&page=${page}&page_size=50`);
  const productions = useResource<Page<ProductionSummary>>("/admin/productions?page_size=100");
  const venues = useResource<{ items: Venue[] }>("/admin/venues");

  const prods = productions.data?.items ?? [];
  const vens = venues.data?.items ?? [];

  async function act(fn: () => Promise<Performance>, ok: (p: Performance) => string) {
    try {
      const r = await fn();
      toast(ok(r));
      list.reload();
    } catch (e) {
      toast(errorMessage(e), "error");
    }
  }

  const noVenues = venues.data && vens.length === 0;

  return (
    <>
      <PageHeader
        title="Program / Temsiller"
        description="Her temsil ayrı yönetilir. Saatler salonun yerel saatidir (Europe/Istanbul). İptal ve tarih değişiklikleri, temsili daha önce görmüş seyirciye bildirilir."
        actions={
          <button className="btn btn-primary" onClick={() => setCreating(true)} disabled={!!noVenues}>
            Temsil ekle
          </button>
        }
      />
      {noVenues && (
        <div className="alert alert-warn" style={{ marginBottom: 16 }}>
          Temsil eklemeden önce <Link href="/salonlar">bir salon ekleyin</Link>.
        </div>
      )}
      <div className="card">
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={scope === "upcoming"} onClick={() => { setScope("upcoming"); setPage(1); }}>
            Yaklaşan
          </button>
          <button role="tab" aria-selected={scope === "past"} onClick={() => { setScope("past"); setPage(1); }}>
            Geçmiş
          </button>
        </div>
        {list.error && <ErrorBox message={list.error.message} onRetry={list.reload} />}
        {list.loading && !list.data && <Spinner />}
        {list.data && list.data.items.length === 0 && (
          <EmptyState title={scope === "upcoming" ? "Yaklaşan temsil yok" : "Geçmiş temsil yok"}>
            {scope === "upcoming" && <p>Uygulama, gerçek tarihler girilene kadar “yakında duyurulacak” mesajı gösterir.</p>}
          </EmptyState>
        )}
        {list.data && list.data.items.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Tarih ve saat</th>
                  <th>Oyun</th>
                  <th>Salon</th>
                  <th>Durum</th>
                  <th aria-label="İşlemler" />
                </tr>
              </thead>
              <tbody>
                {list.data.items.map((x) => (
                  <tr key={x.id} style={x.is_cancelled ? { opacity: 0.75 } : undefined}>
                    <td>
                      <strong>{x.local_date}</strong>
                      <br />
                      <span className="small muted">
                        {x.local_weekday}, {x.local_time}
                      </span>
                      {x.is_rescheduled && x.rescheduled_from_local && (
                        <div className="small muted">
                          Önceki: {x.rescheduled_from_local.local_date} {x.rescheduled_from_local.local_time}
                        </div>
                      )}
                    </td>
                    <td>
                      <Link className="rowlink" href={`/oyunlar/${x.production.id}?sekme=temsiller`}>
                        {x.production.title}
                      </Link>
                      {x.production_status !== "published" && <div className="small" style={{ color: "var(--warn)" }}>Oyun yayında değil</div>}
                    </td>
                    <td>{x.venue.name}</td>
                    <td>
                      <div className="row" style={{ gap: 6 }}>
                        <Badge status={x.status} />
                        <Badge status={x.visibility} />
                      </div>
                      {x.cancellation_note && <div className="small muted">{x.cancellation_note}</div>}
                    </td>
                    <td>
                      {!x.is_past && (
                        <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
                          {x.status === "scheduled" && x.visibility === "draft" && (
                            <button className="btn btn-sm btn-gold" onClick={() => act(() => api.post(`/admin/performances/${x.id}/publish`), () => "Temsil yayınlandı.")}>
                              Yayınla
                            </button>
                          )}
                          <button className="btn btn-sm" onClick={() => setEditing(x)}>
                            Düzenle
                          </button>
                          {x.status === "scheduled" && (
                            <>
                              <button className="btn btn-sm" onClick={() => setRescheduling(x)}>
                                Tarih değiştir
                              </button>
                              <button className="btn btn-sm btn-danger" onClick={() => setCancelling(x)}>
                                İptal et
                              </button>
                            </>
                          )}
                          {x.status === "cancelled" && (
                            <button
                              className="btn btn-sm"
                              onClick={async () => {
                                if (await confirm({ title: "İptal geri alınsın mı?", body: "Temsil yeniden planlanmış duruma döner. İptal bildirimi gönderilmediyse iptal edilir.", confirmLabel: "Geri al" }))
                                  act(() => api.post(`/admin/performances/${x.id}/restore`), () => "İptal geri alındı.");
                              }}
                            >
                              İptali geri al
                            </button>
                          )}
                          {x.visibility === "published" && x.status === "scheduled" && (
                            <button
                              className="btn btn-sm btn-ghost"
                              onClick={async () => {
                                if (await confirm({ title: "Temsil yayından kaldırılsın mı?", body: "Uygulamadan kaldırılır; seyirciye bildirim gönderilmez. Seyirciyi bilgilendirmek için “İptal et”i kullanın.", confirmLabel: "Yayından kaldır" }))
                                  act(() => api.post(`/admin/performances/${x.id}/unpublish`), () => "Temsil yayından kaldırıldı.");
                              }}
                            >
                              Yayından kaldır
                            </button>
                          )}
                          {!x.first_published_at && (
                            <button
                              className="btn btn-sm btn-ghost"
                              onClick={async () => {
                                if (await confirm({ title: "Taslak temsil silinsin mi?", confirmLabel: "Sil", danger: true }))
                                  try {
                                    await api.del(`/admin/performances/${x.id}`);
                                    toast("Taslak temsil silindi.");
                                    list.reload();
                                  } catch (e) {
                                    toast(errorMessage(e), "error");
                                  }
                              }}
                            >
                              Sil
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {list.data && <Pager page={page} pageSize={50} total={list.data.total} onPage={setPage} />}
      </div>

      <Modal open={creating} onClose={() => setCreating(false)} title="Temsil ekle">
        {creating && !(productions.data && venues.data) && <Spinner />}
        {creating && productions.data && venues.data && (
          <PerformanceForm
            productions={prods}
            venues={vens}
            submitLabel="Kaydet"
            initial={{
              production_id: search.get("oyun") ?? "",
              venue_id: vens.length === 1 ? vens[0].id : "",
              date: "",
              time: "20:30",
              visibility: "published",
              public_note: "",
              internal_notes: "",
            }}
            onCancel={() => setCreating(false)}
            onSubmit={async (v, allow) => {
              const r = await api.post<Performance>("/admin/performances", {
                production_id: v.production_id,
                venue_id: v.venue_id,
                starts_at_local: toLocal(v),
                visibility: v.visibility,
                public_note: v.public_note || null,
                internal_notes: v.internal_notes || null,
                allow_conflict: allow,
              });
              setCreating(false);
              toast(r.warnings?.length ? `Temsil kaydedildi. ${r.warnings.join(" ")}` : "Temsil kaydedildi.");
              list.reload();
            }}
          />
        )}
      </Modal>

      <Modal open={!!editing} onClose={() => setEditing(null)} title="Temsili düzenle">
        {editing && (
          <PerformanceForm
            productions={prods}
            venues={vens}
            submitLabel="Kaydet"
            showVisibility={false}
            lockDateTime={!!editing.first_published_at}
            initial={{
              production_id: editing.production.id,
              venue_id: editing.venue.id,
              date: editing.local_iso.slice(0, 10),
              time: editing.local_iso.slice(11, 16),
              visibility: editing.visibility,
              public_note: editing.public_note ?? "",
              internal_notes: editing.internal_notes ?? "",
            }}
            onCancel={() => setEditing(null)}
            onSubmit={async (v, allow) => {
              await api.patch(`/admin/performances/${editing.id}`, {
                venue_id: v.venue_id,
                ...(editing.first_published_at ? {} : { starts_at_local: toLocal(v) }),
                public_note: v.public_note || null,
                internal_notes: v.internal_notes || null,
                allow_conflict: allow,
              });
              setEditing(null);
              toast("Temsil güncellendi.");
              list.reload();
            }}
          />
        )}
      </Modal>

      <RescheduleDialog perf={rescheduling} onClose={() => setRescheduling(null)} onDone={list.reload} />
      <CancelDialog perf={cancelling} onClose={() => setCancelling(null)} onDone={list.reload} />
    </>
  );
}

function RescheduleDialog({ perf, onClose, onDone }: { perf: Performance | null; onClose: () => void; onDone: () => void }) {
  const { toast } = useFeedback();
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [notify, setNotify] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [conflictMsg, setConflictMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save(allow: boolean) {
    if (!perf) return;
    if (!date || !time) return setErr("Yeni tarih ve saati seçin.");
    if (date < todayInIstanbul()) return setErr("Geçmiş bir tarih seçilemez.");
    setBusy(true);
    setErr(null);
    try {
      const r = await api.post<Performance>(`/admin/performances/${perf.id}/reschedule`, {
        starts_at_local: `${date}T${time}`,
        notify,
        allow_conflict: allow,
      });
      toast(r.notification_job_id ? "Tarih değişti. Seyirci bildirimi kuyruğa alındı." : "Tarih değişti.");
      onClose();
      onDone();
    } catch (e) {
      if (e instanceof ApiError && e.code === "schedule_conflict") setConflictMsg(e.message);
      else setErr(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={!!perf}
      onClose={onClose}
      title="Tarih değiştir"
      footer={
        <>
          <button className="btn" onClick={onClose}>
            Vazgeç
          </button>
          {conflictMsg && (
            <button className="btn" disabled={busy} onClick={() => save(true)}>
              Çakışmaya rağmen kaydet
            </button>
          )}
          <button className="btn btn-primary" disabled={busy} onClick={() => save(false)}>
            Tarihi değiştir
          </button>
        </>
      }
    >
      {perf && (
        <div className="stack">
          <p style={{ margin: 0 }}>
            <strong>{perf.production.title}</strong> — şu an: {perf.local_date} {perf.local_time}, {perf.venue.name}
          </p>
          {err && <div className="alert alert-error" role="alert">{err}</div>}
          {conflictMsg && <div className="alert alert-warn" role="alert">{conflictMsg}</div>}
          <div className="grid grid-2">
            <label className="field">
              <span className="label">Yeni tarih</span>
              <input type="date" className="input" min={todayInIstanbul()} value={date} onChange={(e) => { setDate(e.target.value); setConflictMsg(null); }} />
            </label>
            <label className="field">
              <span className="label">Yeni saat</span>
              <input type="time" className="input" value={time} onChange={(e) => { setTime(e.target.value); setConflictMsg(null); }} />
            </label>
          </div>
          <label className="check">
            <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} />
            <span>
              <strong>Seyirciye bildirim gönder</strong>
              <br />
              <span className="small muted">Yalnızca daha önce yayınlanmış temsiller için gönderilir. Eski hatırlatmalar otomatik iptal edilir.</span>
            </span>
          </label>
        </div>
      )}
    </Modal>
  );
}

function CancelDialog({ perf, onClose, onDone }: { perf: Performance | null; onClose: () => void; onDone: () => void }) {
  const { toast } = useFeedback();
  const [note, setNote] = useState("");
  const [notify, setNotify] = useState(true);
  const [busy, setBusy] = useState(false);

  async function save() {
    if (!perf) return;
    setBusy(true);
    try {
      const r = await api.post<Performance>(`/admin/performances/${perf.id}/cancel`, { cancellation_note: note || null, notify });
      toast(r.notification_job_id ? "Temsil iptal edildi. Seyirci bildirimi kuyruğa alındı." : "Temsil iptal edildi.");
      onClose();
      setNote("");
      onDone();
    } catch (e) {
      toast(errorMessage(e), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={!!perf}
      onClose={onClose}
      title="Temsili iptal et"
      footer={
        <>
          <button className="btn" onClick={onClose}>
            Vazgeç
          </button>
          <button className="btn btn-danger-solid" disabled={busy} onClick={save}>
            Temsili iptal et
          </button>
        </>
      }
    >
      {perf && (
        <div className="stack">
          <p style={{ margin: 0 }}>
            <strong>{perf.production.title}</strong> — {perf.local_date} {perf.local_weekday}, {perf.local_time}
          </p>
          <p className="small muted" style={{ margin: 0 }}>
            İptal edilen temsil uygulamada “İptal edildi” olarak işaretli görünür ve mevcut bir temsil gibi sunulmaz. Kayıt silinmez.
          </p>
          <label className="field">
            <span className="label">Seyirciye açıklama (isteğe bağlı)</span>
            <input className="input" maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} placeholder="ör. Teknik nedenlerle" />
          </label>
          <label className="check">
            <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} />
            <span>
              <strong>Seyirciye bildirim gönder</strong>
              <br />
              <span className="small muted">Yalnızca temsil daha önce yayınlandıysa gönderilir. Bekleyen hatırlatmalar iptal edilir.</span>
            </span>
          </label>
        </div>
      )}
    </Modal>
  );
}
