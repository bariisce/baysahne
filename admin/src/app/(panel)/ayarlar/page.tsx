"use client";

import { useState } from "react";
import { AdminOnly } from "@/components/auth";
import { Modal, useFeedback } from "@/components/feedback";
import { Badge, Card, ErrorBox, Field, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useResource } from "@/lib/useResource";

type About = {
  motto?: string; story_title?: string; story?: string; quote?: string; quote_author?: string;
  values?: { title: string; text: string }[]; mission?: string; vision?: string;
};
type Org = {
  name: string; short_name: string | null; address: string | null; phones: string[]; email: string | null;
  website_url: string | null; instagram_url: string | null; x_url: string | null; youtube_url: string | null;
  about: About; logo_id: string | null;
};
type LegalDoc = { id: string; slug: string; title: string; body: string; applies_to: string; status: "draft" | "published"; review_note: string | null; updated_at: string };

const APPLIES: Record<string, string> = { mobile_app: "Mobil uygulama", website: "Web sitesi", all: "Tümü" };

export default function SettingsPage() {
  return (
    <AdminOnly fallback={<div className="alert alert-warn">Bu sayfaya yalnızca yöneticiler erişebilir.</div>}>
      <PageHeader title="Kurum ve yasal metinler" description="Uygulamadaki Hakkımızda ve iletişim bilgileri ile yasal metinler." />
      <div className="stack">
        <OrgCard />
        <LegalCard />
      </div>
    </AdminOnly>
  );
}

function OrgCard() {
  const res = useResource<Org>("/admin/organization");
  if (res.error) return <ErrorBox message={res.error.message} onRetry={res.reload} />;
  if (!res.data) return <Spinner />;
  return <OrgForm key={JSON.stringify(res.data)} initial={res.data} onSaved={res.setData} />;
}

function OrgForm({ initial, onSaved }: { initial: Org; onSaved: (o: Org) => void }) {
  const { toast } = useFeedback();
  const [o, setO] = useState<Org>(initial);
  const [phones, setPhones] = useState(initial.phones.join(", "));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (k: keyof Org, v: string) => setO((s) => ({ ...s, [k]: v || null }));
  const setAbout = (k: keyof About, v: unknown) => setO((s) => ({ ...s, about: { ...s.about, [k]: v || undefined } }));

  async function save() {
    try {
      const payload = { ...o, name: o.name, phones: phones.split(",").map((p) => p.trim()).filter(Boolean), about: { ...o.about, values: o.about.values ?? [] } };
      onSaved(await api.put<Org>("/admin/organization", payload));
      setErrors({});
      toast("Kurum bilgileri kaydedildi.");
    } catch (e) {
      setErrors(e instanceof ApiError ? { ...e.fields, _: e.message } : { _: "Kaydedilemedi." });
    }
  }

  const text = (label: string, k: keyof Org, hint?: string) => (
    <Field label={label} hint={hint} error={errors[k]}>
      {(p) => <input {...p} className="input" value={(o[k] as string) ?? ""} onChange={(e) => set(k, e.target.value)} />}
    </Field>
  );
  const values = o.about.values ?? [];

  return (
    <Card title="Kurum bilgileri" actions={<button className="btn btn-primary" onClick={save}>Kaydet</button>}>
      <div className="stack">
        {errors._ && <div className="alert alert-error" role="alert">{errors._}</div>}
        <div className="grid grid-2">
          {text("Unvan", "name")}
          {text("Kısa ad", "short_name")}
          {text("Adres", "address")}
          <Field label="Telefonlar" hint="Virgülle ayırın." error={errors.phones}>
            {(p) => <input {...p} className="input" value={phones} onChange={(e) => setPhones(e.target.value)} />}
          </Field>
          {text("E-posta", "email")}
          {text("Web sitesi", "website_url", "https://…")}
          {text("Instagram", "instagram_url")}
          {text("X", "x_url")}
          {text("YouTube", "youtube_url")}
        </div>
        <h2 style={{ marginTop: 10 }}>Hakkımızda</h2>
        <div className="grid grid-2">
          <Field label="Slogan">{(p) => <input {...p} className="input" value={o.about.motto ?? ""} onChange={(e) => setAbout("motto", e.target.value)} />}</Field>
          <Field label="Hikâye başlığı">{(p) => <input {...p} className="input" value={o.about.story_title ?? ""} onChange={(e) => setAbout("story_title", e.target.value)} />}</Field>
        </div>
        <Field label="Hikâyemiz">{(p) => <textarea {...p} className="textarea" style={{ minHeight: 160 }} value={o.about.story ?? ""} onChange={(e) => setAbout("story", e.target.value)} />}</Field>
        <div className="grid grid-2">
          <Field label="Alıntı">{(p) => <input {...p} className="input" value={o.about.quote ?? ""} onChange={(e) => setAbout("quote", e.target.value)} />}</Field>
          <Field label="Alıntı sahibi">{(p) => <input {...p} className="input" value={o.about.quote_author ?? ""} onChange={(e) => setAbout("quote_author", e.target.value)} />}</Field>
        </div>
        <div className="stack">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span className="label">Değerlerimiz</span>
            <button type="button" className="btn btn-sm" onClick={() => setAbout("values", [...values, { title: "", text: "" }])}>Değer ekle</button>
          </div>
          {values.map((v, i) => (
            <div key={i} className="grid" style={{ gridTemplateColumns: "1fr 2fr auto", alignItems: "end" }}>
              <Field label="Başlık">{(p) => <input {...p} className="input" value={v.title} onChange={(e) => setAbout("values", values.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))} />}</Field>
              <Field label="Açıklama">{(p) => <input {...p} className="input" value={v.text} onChange={(e) => setAbout("values", values.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))} />}</Field>
              <button type="button" className="btn btn-sm btn-danger" onClick={() => setAbout("values", values.filter((_, j) => j !== i))}>Kaldır</button>
            </div>
          ))}
        </div>
        <div className="grid grid-2">
          <Field label="Misyon">{(p) => <textarea {...p} className="textarea" value={o.about.mission ?? ""} onChange={(e) => setAbout("mission", e.target.value)} />}</Field>
          <Field label="Vizyon">{(p) => <textarea {...p} className="textarea" value={o.about.vision ?? ""} onChange={(e) => setAbout("vision", e.target.value)} />}</Field>
        </div>
      </div>
    </Card>
  );
}

function LegalCard() {
  const res = useResource<{ items: LegalDoc[] }>("/admin/legal");
  const { toast, confirm } = useFeedback();
  const [editing, setEditing] = useState<LegalDoc | null>(null);

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
    <Card title="Yasal metinler">
      <div className="alert alert-warn" style={{ marginBottom: 14 }}>
        İçe aktarılan metinler web sitesi için yazılmıştır ve uygulamada olmayan işlemlerden (üyelik, yorumlar, Firebase Authentication/Firestore) söz eder. Yayınlamadan önce kurum ve gerekirse bir hukuk uzmanı tarafından gözden geçirilmelidir.
      </div>
      {res.error && <ErrorBox message={res.error.message} onRetry={res.reload} />}
      {res.data && (
        <table className="table">
          <thead>
            <tr><th>Metin</th><th>Geçerli olduğu yer</th><th>Durum</th><th>Güncellendi</th><th aria-label="İşlemler" /></tr>
          </thead>
          <tbody>
            {res.data.items.map((d) => (
              <tr key={d.id}>
                <td><strong>{d.title}</strong><div className="small muted"><span className="code">/legal/{d.slug}</span></div></td>
                <td>{APPLIES[d.applies_to] ?? d.applies_to}</td>
                <td><Badge status={d.status} /></td>
                <td className="small">{formatDateTime(d.updated_at)}</td>
                <td>
                  <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
                    <button className="btn btn-sm" onClick={() => setEditing(d)}>Düzenle</button>
                    {d.status === "draft" ? (
                      <button
                        className="btn btn-sm btn-gold"
                        onClick={async () => {
                          if (await confirm({ title: "Yasal metin yayınlansın mı?", body: "Metnin uygulamayı ve veri akışlarını doğru tanımladığından emin olun (bkz. docs/LEGAL_REVIEW.md).", confirmLabel: "Yayınla" }))
                            act(() => api.post(`/admin/legal/${d.id}/publish`), "Metin yayınlandı.");
                        }}
                      >
                        Yayınla
                      </button>
                    ) : (
                      <button className="btn btn-sm" onClick={() => act(() => api.post(`/admin/legal/${d.id}/unpublish`), "Metin yayından kaldırıldı.")}>Yayından kaldır</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <Modal open={!!editing} onClose={() => setEditing(null)} title={editing?.title ?? ""} wide>
        {editing && (
          <LegalForm
            doc={editing}
            onCancel={() => setEditing(null)}
            onSaved={() => {
              setEditing(null);
              toast("Metin kaydedildi.");
              res.reload();
            }}
          />
        )}
      </Modal>
    </Card>
  );
}

function LegalForm({ doc, onSaved, onCancel }: { doc: LegalDoc; onSaved: () => void; onCancel: () => void }) {
  const [title, setTitle] = useState(doc.title);
  const [body, setBody] = useState(doc.body);
  const [applies, setApplies] = useState(doc.applies_to);
  const [note, setNote] = useState(doc.review_note ?? "");
  const [err, setErr] = useState<string | null>(null);
  return (
    <div className="stack">
      {err && <div className="alert alert-error" role="alert">{err}</div>}
      <Field label="Başlık">{(p) => <input {...p} className="input" value={title} onChange={(e) => setTitle(e.target.value)} />}</Field>
      <Field label="Geçerli olduğu yer">
        {(p) => (
          <select {...p} className="select" value={applies} onChange={(e) => setApplies(e.target.value)}>
            <option value="mobile_app">Mobil uygulama</option>
            <option value="website">Web sitesi</option>
            <option value="all">Tümü</option>
          </select>
        )}
      </Field>
      <Field label="Metin" hint="Paragrafları boş satırla ayırın.">{(p) => <textarea {...p} className="textarea" style={{ minHeight: 320 }} value={body} onChange={(e) => setBody(e.target.value)} />}</Field>
      <Field label="İnceleme notu (yalnızca panel)">{(p) => <textarea {...p} className="textarea" style={{ minHeight: 70 }} value={note} onChange={(e) => setNote(e.target.value)} />}</Field>
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button className="btn" onClick={onCancel}>Vazgeç</button>
        <button
          className="btn btn-primary"
          onClick={async () => {
            try {
              await api.put(`/admin/legal/${doc.id}`, { title, body, applies_to: applies, review_note: note || null });
              onSaved();
            } catch (e) {
              setErr(errorMessage(e));
            }
          }}
        >
          Kaydet
        </button>
      </div>
    </div>
  );
}
