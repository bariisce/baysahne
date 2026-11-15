"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useFeedback, Modal } from "@/components/feedback";
import { MediaPicker } from "@/components/MediaPicker";
import { ProductionForm, toInput } from "@/components/ProductionForm";
import { Badge, Card, EmptyState, ErrorBox, PageHeader, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { mediaSrc } from "@/lib/media";
import type { Page, Performance, Production } from "@/lib/types";
import { useResource } from "@/lib/useResource";

const TABS = [
  { id: "bilgiler", label: "Bilgiler" },
  { id: "gorseller", label: "Afiş ve görseller" },
  { id: "temsiller", label: "Temsiller" },
  { id: "onizleme", label: "Önizleme" },
] as const;

export default function ProductionEditorPage() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const [tab, setTab] = useState<string>(search.get("sekme") ?? "bilgiler");
  const res = useResource<Production>(`/admin/productions/${id}`);
  const { toast, confirm } = useFeedback();
  const [publishOpen, setPublishOpen] = useState(false);
  const [notify, setNotify] = useState(false);
  const p = res.data;

  async function run(action: () => Promise<Production | void>, ok: string) {
    try {
      const r = await action();
      if (r) res.setData(r);
      toast(ok);
    } catch (e) {
      toast(errorMessage(e), "error");
    }
  }

  if (res.error) return <ErrorBox message={res.error.message} onRetry={res.reload} />;
  if (!p) return <Spinner />;

  const neverPublished = !p.first_published_at;

  return (
    <>
      <PageHeader
        title={p.title}
        description={
          <span className="row" style={{ gap: 8 }}>
            <Badge status={p.status} />
            {p.on_stage && <Badge status="gold">Sahnede</Badge>}
            {p.issues.length > 0 && <span className="small">Eksik: {p.issues.map((i) => i.message).join(", ")}</span>}
          </span>
        }
        actions={
          <>
            {p.status === "published" && (
              <button
                className="btn"
                onClick={async () => {
                  if (await confirm({ title: "Yayından kaldırılsın mı?", body: "Oyun ve temsilleri uygulamada görünmez olur. Bekleyen bildirimleri iptal edilir.", confirmLabel: "Yayından kaldır" }))
                    run(() => api.post<Production>(`/admin/productions/${p.id}/unpublish`), "Oyun yayından kaldırıldı.");
                }}
              >
                Yayından kaldır
              </button>
            )}
            {p.status !== "archived" && (
              <button
                className="btn"
                onClick={async () => {
                  if (await confirm({ title: "Oyun arşivlensin mi?", body: "Arşivlenen oyun uygulamada görünmez; temsil geçmişi korunur. Daha sonra geri alınabilir.", confirmLabel: "Arşivle" }))
                    run(() => api.post<Production>(`/admin/productions/${p.id}/archive`), "Oyun arşivlendi.");
                }}
              >
                Arşivle
              </button>
            )}
            {p.status === "archived" && (
              <button className="btn" onClick={() => run(() => api.post<Production>(`/admin/productions/${p.id}/restore`), "Oyun taslağa alındı.")}>
                Arşivden çıkar
              </button>
            )}
            {neverPublished && p.status === "draft" && (
              <button
                className="btn btn-danger"
                onClick={async () => {
                  if (await confirm({ title: "Taslak silinsin mi?", body: "Bu işlem geri alınamaz.", confirmLabel: "Sil", danger: true }))
                    try {
                      await api.del(`/admin/productions/${p.id}`);
                      toast("Taslak silindi.");
                      router.replace("/oyunlar");
                    } catch (e) {
                      toast(errorMessage(e), "error");
                    }
                }}
              >
                Sil
              </button>
            )}
            {p.status !== "published" && (
              <button
                className="btn btn-gold"
                onClick={() => {
                  setNotify(false);
                  setPublishOpen(true);
                }}
              >
                Yayınla
              </button>
            )}
          </>
        }
      />

      <div className="tabs" role="tablist" aria-label="Oyun bölümleri">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "bilgiler" && (
        <ProductionForm
          key={p.updated_at}
          initial={toInput(p)}
          submitLabel="Değişiklikleri kaydet"
          onSubmit={async (v) => {
            const r = await api.patch<Production>(`/admin/productions/${p.id}`, v);
            res.setData(r);
            toast("Değişiklikler kaydedildi.");
          }}
        />
      )}
      {tab === "gorseller" && <MediaTab p={p} onChange={res.setData} />}
      {tab === "temsiller" && <PerformancesTab p={p} />}
      {tab === "onizleme" && <PreviewTab id={p.id} />}

      <Modal
        open={publishOpen}
        onClose={() => setPublishOpen(false)}
        title="Oyun yayınlansın mı?"
        footer={
          <>
            <button className="btn" onClick={() => setPublishOpen(false)}>
              Vazgeç
            </button>
            <button
              className="btn btn-gold"
              onClick={async () => {
                setPublishOpen(false);
                try {
                  const r = await api.post<Production>(`/admin/productions/${p.id}/publish`, { notify });
                  res.setData(r);
                  toast(r.notification_job_id ? "Oyun yayınlandı. Bildirim kuyruğa alındı." : "Oyun yayınlandı.");
                } catch (e) {
                  toast(errorMessage(e), "error");
                }
              }}
            >
              Yayınla
            </button>
          </>
        }
      >
        <div className="stack">
          <p style={{ margin: 0 }}>Oyun uygulamada herkese görünür olacak. Yayın öncesi “Önizleme” sekmesinden kontrol edebilirsiniz.</p>
          {p.issues.length > 0 && <div className="alert alert-warn">Eksik bilgiler: {p.issues.map((i) => i.message).join(", ")}</div>}
          {neverPublished ? (
            <label className="check">
              <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} />
              <span>
                <strong>“Yeni oyun” bildirimi gönder</strong>
                <br />
                <span className="small muted">Bildirim iznini vermiş tüm cihazlara bir kez gönderilir. Aynı oyun için tekrar gönderilmez.</span>
              </span>
            </label>
          ) : (
            <p className="small muted" style={{ margin: 0 }}>
              Bu oyun daha önce yayınlandığı için “yeni oyun” bildirimi tekrar gönderilmez.
            </p>
          )}
        </div>
      </Modal>
    </>
  );
}

function MediaTab({ p, onChange }: { p: Production; onChange: (p: Production) => void }) {
  const { toast, confirm } = useFeedback();
  const [pick, setPick] = useState<null | "poster" | "gallery">(null);

  async function act(fn: () => Promise<Production>, ok: string) {
    try {
      onChange(await fn());
      toast(ok);
    } catch (e) {
      toast(errorMessage(e), "error");
    }
  }

  const reorder = (i: number, d: number) => {
    const ids = p.gallery.map((g) => g.image_id);
    const [x] = ids.splice(i, 1);
    ids.splice(i + d, 0, x);
    act(() => api.put<Production>(`/admin/productions/${p.id}/images/order`, { image_ids: ids }), "Sıralama güncellendi.");
  };

  return (
    <div className="stack">
      <Card title="Afiş">
        <div className="row" style={{ alignItems: "flex-start", gap: 20 }}>
          <div className="poster-box">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {p.poster ? <img src={mediaSrc(p.poster.lg?.url ?? p.poster.url)} alt={`${p.title} afişi`} /> : <span>Afiş yok.<br />Uygulamada sade bir yer tutucu gösterilir.</span>}
          </div>
          <div className="stack">
            <button className="btn btn-primary" onClick={() => setPick("poster")}>
              {p.poster ? "Afişi değiştir" : "Afiş ekle"}
            </button>
            {p.poster && (
              <button className="btn btn-danger" onClick={() => act(() => api.del<Production>(`/admin/productions/${p.id}/poster`), "Afiş kaldırıldı.")}>
                Afişi kaldır
              </button>
            )}
            <p className="small muted" style={{ maxWidth: 360, margin: 0 }}>
              Dikey (3:4) afişler en iyi sonucu verir. Eski afiş silinmez; Görseller kütüphanesinde kalır.
            </p>
          </div>
        </div>
      </Card>

      <Card title={`Oyundan kareler (${p.gallery.length})`} actions={<button className="btn" onClick={() => setPick("gallery")}>Görsel ekle</button>}>
        {p.gallery.length === 0 ? (
          <EmptyState title="Galeri boş">
            <p>Oyundan fotoğraflar ekleyin. Uygulamada kaydırılabilir galeri olarak görünür.</p>
          </EmptyState>
        ) : (
          <div className="media-grid">
            {p.gallery.map((g, i) => (
              <div key={g.image_id} className="media-tile">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={mediaSrc(g.sm?.url ?? g.url)} alt={g.caption ?? `${p.title} — kare ${i + 1}`} loading="lazy" />
                <div className="meta">{i + 1}. sıra</div>
                <div className="tools">
                  <button className="btn btn-sm" aria-label={`${i + 1}. görseli sola taşı`} disabled={i === 0} onClick={() => reorder(i, -1)}>
                    ←
                  </button>
                  <button className="btn btn-sm" aria-label={`${i + 1}. görseli sağa taşı`} disabled={i === p.gallery.length - 1} onClick={() => reorder(i, 1)}>
                    →
                  </button>
                  <button
                    className="btn btn-sm btn-danger"
                    onClick={async () => {
                      if (await confirm({ title: "Görsel galeriden kaldırılsın mı?", body: "Dosya silinmez; Görseller kütüphanesinde kalır.", confirmLabel: "Kaldır" }))
                        act(() => api.del<Production>(`/admin/productions/${p.id}/images/${g.image_id}`), "Görsel galeriden kaldırıldı.");
                    }}
                  >
                    Kaldır
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <MediaPicker
        open={pick === "poster"}
        title="Afiş seç"
        onClose={() => setPick(null)}
        onPick={(ids) => act(() => api.put<Production>(`/admin/productions/${p.id}/poster`, { media_id: ids[0] }), "Afiş güncellendi.")}
      />
      <MediaPicker
        open={pick === "gallery"}
        multiple
        title="Galeriye görsel ekle"
        onClose={() => setPick(null)}
        onPick={(ids) => act(() => api.post<Production>(`/admin/productions/${p.id}/images`, { media_ids: ids }), "Görseller galeriye eklendi.")}
      />
    </div>
  );
}

function PerformancesTab({ p }: { p: Production }) {
  const res = useResource<Page<Performance>>(`/admin/performances?production_id=${p.id}&scope=all&page_size=100`);
  return (
    <Card title="Bu oyunun temsilleri" actions={<Link className="btn btn-primary" href={`/temsiller?yeni=1&oyun=${p.id}`}>Temsil ekle</Link>}>
      {p.status !== "published" && <div className="alert alert-warn" style={{ marginBottom: 12 }}>Oyun yayında olmadığı için temsilleri uygulamada görünmez.</div>}
      {res.error && <ErrorBox message={res.error.message} onRetry={res.reload} />}
      {res.loading && !res.data && <Spinner />}
      {res.data && res.data.items.length === 0 && (
        <EmptyState title="Temsil yok">
          <p>Oyun, temsil tarihi olmadan da katalogda görünür.</p>
        </EmptyState>
      )}
      {res.data && res.data.items.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>Tarih</th>
              <th>Salon</th>
              <th>Durum</th>
            </tr>
          </thead>
          <tbody>
            {res.data.items.map((x) => (
              <tr key={x.id}>
                <td>
                  {x.local_date} {x.local_weekday}, {x.local_time}
                  {x.is_past && <span className="small muted"> (geçmiş)</span>}
                </td>
                <td>{x.venue.name}</td>
                <td className="row" style={{ gap: 6 }}>
                  <Badge status={x.status} />
                  <Badge status={x.visibility} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

type PreviewData = Production & { excerpt: string | null; performances: Performance[] };

function PreviewTab({ id }: { id: string }) {
  const res = useResource<PreviewData>(`/admin/productions/${id}/preview`);
  const d = res.data;
  if (res.error) return <ErrorBox message={res.error.message} onRetry={res.reload} />;
  if (!d) return <Spinner />;
  return (
    <div className="grid grid-2">
      <div className="phone" aria-label="Uygulama önizlemesi">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        {d.poster ? <img className="poster" src={mediaSrc(d.poster.lg?.url ?? d.poster.url)} alt="" /> : <div className="poster" style={{ background: "#2a231c" }} />}
        <div className="gold" style={{ marginTop: 14 }}>
          {d.genres.join(" · ")}
        </div>
        <h2>{d.title}</h2>
        {d.duration_label && <div className="small" style={{ color: "#9c8b72" }}>{d.duration_label}</div>}
        {d.description && <p>{d.description}</p>}
        {d.credits.map((c, i) => (
          <div key={i} className="small" style={{ color: "#e5ddd0" }}>
            <span style={{ color: "#9c8b72" }}>{c.label}</span> {c.name}
          </div>
        ))}
      </div>
      <Card title="Önizleme notları">
        <ul className="small" style={{ paddingLeft: 18 }}>
          <li>Önizleme, oyun taslak olsa bile uygulamadaki görünümü gösterir.</li>
          <li>Boş alanlar uygulamada gizlenir; uydurma içerik gösterilmez.</li>
          <li>Galeride {d.gallery.length} görsel, {d.videos.length} video var.</li>
          <li>Yaklaşan temsil: {d.performances.filter((x) => !x.is_cancelled).length}</li>
        </ul>
      </Card>
    </div>
  );
}
