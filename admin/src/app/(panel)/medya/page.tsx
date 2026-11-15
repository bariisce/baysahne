"use client";

import { useState } from "react";
import { Modal, useFeedback } from "@/components/feedback";
import { UploadZone } from "@/components/MediaPicker";
import { EmptyState, ErrorBox, Field, PageHeader, Pager, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { formatBytes, formatDateTime } from "@/lib/format";
import { mediaSrc } from "@/lib/media";
import type { MediaItem, Page } from "@/lib/types";
import { useResource } from "@/lib/useResource";

const USAGE_LABELS: Record<string, string> = {
  production_poster: "Afiş",
  production_gallery: "Galeri",
  article_image: "Duyuru görseli",
  organization_logo: "Kurum logosu",
};

export default function MediaPage() {
  const [page, setPage] = useState(1);
  const res = useResource<Page<MediaItem>>(`/admin/media?page=${page}&page_size=48`);
  const [selected, setSelected] = useState<string | null>(null);
  const { toast } = useFeedback();

  return (
    <>
      <PageHeader title="Görseller" description="Tüm yüklenen görseller. Kullanımda olan bir görsel silinemez." />
      <div className="stack">
        <div className="card">
          <UploadZone
            onUploaded={(items) => {
              const dup = items.filter((i) => i.duplicate).length;
              toast(dup ? `${items.length - dup} görsel yüklendi; ${dup} tanesi zaten kütüphanedeydi.` : `${items.length} görsel yüklendi.`);
              res.reload();
            }}
          />
        </div>
        <div className="card">
          {res.error && <ErrorBox message={res.error.message} onRetry={res.reload} />}
          {res.loading && !res.data && <Spinner />}
          {res.data?.items.length === 0 && <EmptyState title="Henüz görsel yok" />}
          {res.data && (
            <>
              <div className="media-grid">
                {res.data.items.map((m) => (
                  <button key={m.id} type="button" className="media-tile selectable" style={{ padding: 0, textAlign: "left" }} onClick={() => setSelected(m.id)}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={mediaSrc(m.sm?.url ?? m.url)} alt={m.alt ?? m.original_filename ?? ""} loading="lazy" />
                    <div className="meta">{m.original_filename ?? "görsel"}</div>
                  </button>
                ))}
              </div>
              <Pager page={page} pageSize={48} total={res.data.total} onPage={setPage} />
            </>
          )}
        </div>
      </div>
      <MediaDetail
        id={selected}
        onClose={() => setSelected(null)}
        onDeleted={() => {
          setSelected(null);
          res.reload();
        }}
      />
    </>
  );
}

function MediaDetail({ id, onClose, onDeleted }: { id: string | null; onClose: () => void; onDeleted: () => void }) {
  const res = useResource<MediaItem>(id ? `/admin/media/${id}` : null);
  const { toast, confirm } = useFeedback();
  const [alt, setAlt] = useState<string | null>(null);
  const m = res.data && res.data.id === id ? res.data : null;
  const inUse = (m?.usage?.length ?? 0) > 0;

  return (
    <Modal
      open={!!id}
      onClose={() => { setAlt(null); onClose(); }}
      title="Görsel ayrıntıları"
      wide
      footer={
        m && (
          <>
            <button
              className="btn btn-danger"
              disabled={inUse}
              title={inUse ? "Kullanımda olan görsel silinemez" : undefined}
              onClick={async () => {
                if (!(await confirm({ title: "Görsel kalıcı olarak silinsin mi?", body: "Dosya depodan silinir. Bu işlem geri alınamaz.", confirmLabel: "Sil", danger: true }))) return;
                try {
                  await api.del(`/admin/media/${m.id}`);
                  toast("Görsel silindi.");
                  onDeleted();
                } catch (e) {
                  toast(errorMessage(e), "error");
                }
              }}
            >
              Sil
            </button>
            <button
              className="btn btn-primary"
              onClick={async () => {
                try {
                  res.setData(await api.patch<MediaItem>(`/admin/media/${m.id}`, { alt_text: (alt ?? m.alt ?? "").trim() || null }));
                  toast("Açıklama kaydedildi.");
                } catch (e) {
                  toast(errorMessage(e), "error");
                }
              }}
            >
              Kaydet
            </button>
          </>
        )
      }
    >
      {!m && <Spinner />}
      {m && (
        <div className="grid grid-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={mediaSrc(m.lg?.url ?? m.url)} alt={m.alt ?? ""} style={{ width: "100%", borderRadius: 8, background: "var(--cream)" }} />
          <div className="stack small">
            <div><strong>Dosya:</strong> {m.original_filename ?? "—"}</div>
            <div><strong>Boyut:</strong> {m.width}×{m.height} · {formatBytes(m.byte_size)}</div>
            <div><strong>Yüklenme:</strong> {formatDateTime(m.created_at)}</div>
            <div>
              <strong>Kullanıldığı yerler:</strong>
              {inUse ? (
                <ul style={{ margin: "4px 0", paddingLeft: 18 }}>
                  {m.usage!.map((u, i) => (
                    <li key={i}>{USAGE_LABELS[u.type] ?? u.type}: {u.label}</li>
                  ))}
                </ul>
              ) : (
                " kullanılmıyor"
              )}
            </div>
            <Field label="Erişilebilirlik açıklaması" hint="Ekran okuyucular için görselin kısa tarifi.">
              {(p) => <input {...p} className="input" maxLength={300} value={alt ?? m.alt ?? ""} onChange={(e) => setAlt(e.target.value)} />}
            </Field>
          </div>
        </div>
      )}
    </Modal>
  );
}
