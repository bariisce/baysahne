"use client";

import { useState, type FormEvent } from "react";
import { Modal, useFeedback } from "@/components/feedback";
import { MediaPicker } from "@/components/MediaPicker";
import { Badge, EmptyState, ErrorBox, Field, PageHeader, Spinner, Thumb } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { Article, Img } from "@/lib/types";
import { useResource } from "@/lib/useResource";

export default function ArticlesPage() {
  const res = useResource<{ items: Article[] }>("/admin/articles");
  const { toast, confirm } = useFeedback();
  const [editing, setEditing] = useState<Article | "new" | null>(null);

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
        title="Duyurular"
        description="Kısa haberler ve duyurular. Yayınlananlar uygulamanın ana sayfasında görünür."
        actions={<button className="btn btn-primary" onClick={() => setEditing("new")}>Duyuru yaz</button>}
      />
      <div className="card">
        {res.error && <ErrorBox message={res.error.message} onRetry={res.reload} />}
        {res.loading && !res.data && <Spinner />}
        {res.data?.items.length === 0 && <EmptyState title="Henüz duyuru yok" />}
        {res.data && res.data.items.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th aria-label="Görsel" />
                <th>Başlık</th>
                <th>Durum</th>
                <th>Yayın tarihi</th>
                <th aria-label="İşlemler" />
              </tr>
            </thead>
            <tbody>
              {res.data.items.map((a) => {
                const scheduled = a.status === "published" && a.published_at && new Date(a.published_at) > new Date();
                return (
                  <tr key={a.id}>
                    <td style={{ width: 56 }}><Thumb src={a.image?.sm?.url} alt="" /></td>
                    <td><strong>{a.title}</strong><div className="small muted">{a.excerpt}</div></td>
                    <td>{scheduled ? <Badge status="pending">Planlandı</Badge> : <Badge status={a.status} />}</td>
                    <td className="small">{formatDateTime(a.published_at)}</td>
                    <td>
                      <div className="row" style={{ justifyContent: "flex-end", gap: 6 }}>
                        <button className="btn btn-sm" onClick={() => setEditing(a)}>Düzenle</button>
                        {a.status === "draft" ? (
                          <button className="btn btn-sm btn-gold" onClick={() => act(() => api.post(`/admin/articles/${a.id}/publish`, {}), "Duyuru yayınlandı.")}>Yayınla</button>
                        ) : (
                          <button className="btn btn-sm" onClick={() => act(() => api.post(`/admin/articles/${a.id}/unpublish`), "Duyuru yayından kaldırıldı.")}>Yayından kaldır</button>
                        )}
                        <button
                          className="btn btn-sm btn-danger"
                          onClick={async () => {
                            if (await confirm({ title: "Duyuru silinsin mi?", body: "Bu işlem geri alınamaz.", confirmLabel: "Sil", danger: true }))
                              act(() => api.del(`/admin/articles/${a.id}`), "Duyuru silindi.");
                          }}
                        >
                          Sil
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      <Modal open={!!editing} onClose={() => setEditing(null)} title={editing === "new" ? "Yeni duyuru" : "Duyuruyu düzenle"} wide>
        {editing && (
          <ArticleForm
            initial={editing === "new" ? null : editing}
            onCancel={() => setEditing(null)}
            onSaved={() => {
              toast("Duyuru kaydedildi.");
              setEditing(null);
              res.reload();
            }}
          />
        )}
      </Modal>
    </>
  );
}

function ArticleForm({ initial, onSaved, onCancel }: { initial: Article | null; onSaved: () => void; onCancel: () => void }) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [body, setBody] = useState(initial?.body ?? "");
  const [image, setImage] = useState<Img | null>(initial?.image ?? null);
  const [imageId, setImageId] = useState<string | null>(initial?.image_id ?? null);
  const [pick, setPick] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!title.trim()) errs.title = "Başlık zorunludur.";
    if (!body.trim()) errs.body = "Metin zorunludur.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try {
      const payload = { title: title.trim(), body: body.trim(), image_id: imageId };
      if (initial) await api.put(`/admin/articles/${initial.id}`, payload);
      else await api.post("/admin/articles", payload);
      onSaved();
    } catch (err) {
      setErrors(err instanceof ApiError ? { ...err.fields, _: err.message } : { _: "Kaydedilemedi." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="stack">
      {errors._ && <div className="alert alert-error" role="alert">{errors._}</div>}
      <Field label="Başlık" required error={errors.title}>
        {(p) => <input {...p} className="input" maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />}
      </Field>
      <Field label="Metin" required error={errors.body} hint="Paragrafları boş satırla ayırın.">
        {(p) => <textarea {...p} className="textarea" style={{ minHeight: 220 }} value={body} onChange={(e) => setBody(e.target.value)} />}
      </Field>
      <div className="row">
        {image ? <Thumb src={image.sm?.url} alt="" /> : <div className="thumb-empty" />}
        <button type="button" className="btn btn-sm" onClick={() => setPick(true)}>{image ? "Görseli değiştir" : "Görsel ekle (isteğe bağlı)"}</button>
        {image && <button type="button" className="btn btn-sm btn-ghost" onClick={() => { setImage(null); setImageId(null); }}>Görseli kaldır</button>}
      </div>
      <p className="small muted" style={{ margin: 0 }}>Duyuru taslak olarak kaydedilir; listeden “Yayınla” ile yayına alınır.</p>
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="btn" onClick={onCancel}>Vazgeç</button>
        <button className="btn btn-primary" disabled={busy}>{busy ? "Kaydediliyor…" : "Kaydet"}</button>
      </div>
      <MediaPicker
        open={pick}
        title="Duyuru görseli"
        onClose={() => setPick(false)}
        onPick={async (ids) => {
          const m = await api.get<Img>(`/admin/media/${ids[0]}`);
          setImage(m);
          setImageId(ids[0]);
        }}
      />
    </form>
  );
}
