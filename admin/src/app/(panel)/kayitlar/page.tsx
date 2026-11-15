"use client";

import { useState } from "react";
import { AdminOnly } from "@/components/auth";
import { EmptyState, ErrorBox, PageHeader, Pager, Spinner } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import type { Page } from "@/lib/types";
import { useResource } from "@/lib/useResource";

type Entry = { id: number; at: string; actor: string | null; action: string; entity_type: string | null; summary: string | null; ip: string | null };

const FILTERS: [string, string][] = [
  ["", "Tümü"],
  ["auth.", "Giriş / güvenlik"],
  ["admin.", "Ekip"],
  ["production.", "Oyunlar"],
  ["performance.", "Temsiller"],
  ["media.", "Görseller"],
  ["notifications.", "Bildirimler"],
  ["legal.", "Yasal metinler"],
];

export default function AuditPage() {
  return (
    <AdminOnly fallback={<div className="alert alert-warn">Bu sayfaya yalnızca yöneticiler erişebilir.</div>}>
      <Audit />
    </AdminOnly>
  );
}

function Audit() {
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const res = useResource<Page<Entry>>(`/admin/audit?page=${page}&page_size=50${action ? `&action=${encodeURIComponent(action)}` : ""}`);
  return (
    <>
      <PageHeader title="İşlem kayıtları" description="Paneldeki önemli işlemlerin değiştirilemez kaydı. Parola veya bağlantı anahtarı içermez." />
      <div className="card">
        <div className="row" style={{ marginBottom: 12 }}>
          <label className="sr-only" htmlFor="flt">Filtre</label>
          <select id="flt" className="select" style={{ maxWidth: 240 }} value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }}>
            {FILTERS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        {res.error && <ErrorBox message={res.error.message} onRetry={res.reload} />}
        {res.loading && !res.data && <Spinner />}
        {res.data?.items.length === 0 && <EmptyState title="Kayıt yok" />}
        {res.data && res.data.items.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Zaman</th><th>Kişi</th><th>İşlem</th><th>Özet</th><th>IP</th></tr></thead>
              <tbody>
                {res.data.items.map((a) => (
                  <tr key={a.id}>
                    <td className="small">{formatDateTime(a.at)}</td>
                    <td className="small">{a.actor ?? "—"}</td>
                    <td><span className="code">{a.action}</span></td>
                    <td className="small">{a.summary}</td>
                    <td className="small muted">{a.ip ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {res.data && <Pager page={page} pageSize={50} total={res.data.total} onPage={setPage} />}
      </div>
    </>
  );
}
