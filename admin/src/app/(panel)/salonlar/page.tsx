"use client";

import { useState, type FormEvent } from "react";
import { Modal, useFeedback } from "@/components/feedback";
import { Badge, EmptyState, ErrorBox, Field, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api";
import type { Venue } from "@/lib/types";
import { useResource } from "@/lib/useResource";

type VenueInput = Omit<Venue, "id">;
const EMPTY: VenueInput = { name: "", address: "", district: "", city: "Adana", maps_url: "", public_info: "", timezone: "Europe/Istanbul", is_active: true };

export default function VenuesPage() {
  const res = useResource<{ items: Venue[] }>("/admin/venues");
  const { toast, confirm } = useFeedback();
  const [editing, setEditing] = useState<Venue | "new" | null>(null);

  return (
    <>
      <PageHeader
        title="Salonlar"
        description="Temsillerin yapıldığı mekânlar. Her temsil bir salona bağlanır."
        actions={<button className="btn btn-primary" onClick={() => setEditing("new")}>Salon ekle</button>}
      />
      <div className="card">
        {res.error && <ErrorBox message={res.error.message} onRetry={res.reload} />}
        {res.loading && !res.data && <Spinner />}
        {res.data?.items.length === 0 && <EmptyState title="Henüz salon yok" />}
        {res.data && res.data.items.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Salon</th>
                <th>Adres</th>
                <th>Durum</th>
                <th aria-label="İşlemler" />
              </tr>
            </thead>
            <tbody>
              {res.data.items.map((v) => (
                <tr key={v.id}>
                  <td><strong>{v.name}</strong></td>
                  <td className="small">{[v.address, v.district, v.city].filter(Boolean).join(", ") || "—"}</td>
                  <td><Badge status={v.is_active ? "published" : "archived"}>{v.is_active ? "Aktif" : "Pasif"}</Badge></td>
                  <td>
                    <div className="row" style={{ justifyContent: "flex-end", gap: 6 }}>
                      <button className="btn btn-sm" onClick={() => setEditing(v)}>Düzenle</button>
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={async () => {
                          if (!(await confirm({ title: `${v.name} silinsin mi?`, body: "Bu salonda temsil kaydı varsa silinemez; pasif hâle getirebilirsiniz.", confirmLabel: "Sil", danger: true }))) return;
                          try {
                            await api.del(`/admin/venues/${v.id}`);
                            toast("Salon silindi.");
                            res.reload();
                          } catch (e) {
                            toast(errorMessage(e), "error");
                          }
                        }}
                      >
                        Sil
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <Modal open={!!editing} onClose={() => setEditing(null)} title={editing === "new" ? "Salon ekle" : "Salonu düzenle"}>
        {editing && (
          <VenueForm
            initial={editing === "new" ? EMPTY : editing}
            onCancel={() => setEditing(null)}
            onSubmit={async (v) => {
              if (editing === "new") await api.post("/admin/venues", v);
              else await api.put(`/admin/venues/${editing.id}`, v);
              toast("Salon kaydedildi.");
              setEditing(null);
              res.reload();
            }}
          />
        )}
      </Modal>
    </>
  );
}

function VenueForm({ initial, onSubmit, onCancel }: { initial: VenueInput; onSubmit: (v: VenueInput) => Promise<void>; onCancel: () => void }) {
  const [v, setV] = useState<VenueInput>({ ...EMPTY, ...initial });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const set = (k: keyof VenueInput, val: string | boolean) => setV((s) => ({ ...s, [k]: val }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!v.name.trim()) errs.name = "Salon adı zorunludur.";
    if (v.maps_url && !/^https:\/\//.test(v.maps_url)) errs.maps_url = "Bağlantı https:// ile başlamalıdır.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try {
      const clean = Object.fromEntries(Object.entries(v).map(([k, x]) => [k, typeof x === "string" ? x.trim() || null : x])) as VenueInput;
      await onSubmit({ ...clean, name: v.name.trim(), timezone: v.timezone || "Europe/Istanbul" });
    } catch (err) {
      setErrors(err instanceof ApiError ? { ...err.fields, _: err.message } : { _: "Kaydedilemedi." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="stack">
      {errors._ && <div className="alert alert-error" role="alert">{errors._}</div>}
      <Field label="Salon adı" required error={errors.name}>
        {(p) => <input {...p} className="input" value={v.name} onChange={(e) => set("name", e.target.value)} />}
      </Field>
      <Field label="Adres" error={errors.address}>
        {(p) => <input {...p} className="input" value={v.address ?? ""} onChange={(e) => set("address", e.target.value)} />}
      </Field>
      <div className="grid grid-2">
        <Field label="İlçe">{(p) => <input {...p} className="input" value={v.district ?? ""} onChange={(e) => set("district", e.target.value)} />}</Field>
        <Field label="Şehir">{(p) => <input {...p} className="input" value={v.city ?? ""} onChange={(e) => set("city", e.target.value)} />}</Field>
      </div>
      <Field label="Harita bağlantısı" hint="Google Haritalar vb. paylaşım bağlantısı (https://…)" error={errors.maps_url}>
        {(p) => <input {...p} className="input" value={v.maps_url ?? ""} onChange={(e) => set("maps_url", e.target.value)} />}
      </Field>
      <Field label="Seyirci için bilgi" hint="Ulaşım, otopark, erişilebilirlik gibi notlar.">
        {(p) => <textarea {...p} className="textarea" style={{ minHeight: 80 }} value={v.public_info ?? ""} onChange={(e) => set("public_info", e.target.value)} />}
      </Field>
      <label className="check">
        <input type="checkbox" checked={v.is_active !== false} onChange={(e) => set("is_active", e.target.checked)} />
        <span>Aktif (yeni temsillerde seçilebilir)</span>
      </label>
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="btn" onClick={onCancel}>Vazgeç</button>
        <button className="btn btn-primary" disabled={busy}>{busy ? "Kaydediliyor…" : "Kaydet"}</button>
      </div>
    </form>
  );
}
