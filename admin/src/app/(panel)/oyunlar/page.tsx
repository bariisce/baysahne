"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Badge, EmptyState, ErrorBox, PageHeader, Pager, Spinner, Thumb } from "@/components/ui";
import { formatRelative } from "@/lib/format";
import type { Page, ProductionSummary } from "@/lib/types";
import { useResource } from "@/lib/useResource";

export default function ProductionsPage() {
  const params = useSearchParams();
  const router = useRouter();
  const status = params.get("durum") ?? "";
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const qs = new URLSearchParams({ page: String(page), page_size: "50" });
  if (status) qs.set("status", status);
  if (query) qs.set("q", query);
  const { data, error, loading, reload } = useResource<Page<ProductionSummary>>(`/admin/productions?${qs}`);

  return (
    <>
      <PageHeader
        title="Oyunlar"
        description="Repertuvar. Yayındaki oyunlar uygulamada görünür; tarihler Program bölümünden ayrıca yönetilir."
        actions={
          <Link className="btn btn-primary" href="/oyunlar/yeni">
            Yeni oyun
          </Link>
        }
      />
      <div className="card">
        <form
          className="row"
          style={{ marginBottom: 14 }}
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            setQuery(q.trim());
          }}
        >
          <label className="sr-only" htmlFor="q">
            Oyun ara
          </label>
          <input id="q" className="input" style={{ maxWidth: 320 }} placeholder="Oyun adı ara" value={q} onChange={(e) => setQ(e.target.value)} />
          <label className="sr-only" htmlFor="durum">
            Durum
          </label>
          <select
            id="durum"
            className="select"
            style={{ maxWidth: 200 }}
            value={status}
            onChange={(e) => {
              setPage(1);
              router.replace(e.target.value ? `/oyunlar?durum=${e.target.value}` : "/oyunlar");
            }}
          >
            <option value="">Tüm durumlar</option>
            <option value="published">Yayında</option>
            <option value="draft">Taslak</option>
            <option value="archived">Arşivde</option>
          </select>
          <button className="btn">Ara</button>
        </form>
        {error && <ErrorBox message={error.message} onRetry={reload} />}
        {loading && !data && <Spinner />}
        {data && data.items.length === 0 && (
          <EmptyState title="Oyun bulunamadı">
            <p>Arama ölçütlerini değiştirin veya yeni bir oyun ekleyin.</p>
          </EmptyState>
        )}
        {data && data.items.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th aria-label="Afiş" />
                  <th>Oyun</th>
                  <th>Durum</th>
                  <th>Tür</th>
                  <th>Eksikler</th>
                  <th>Güncellendi</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((p) => (
                  <tr key={p.id}>
                    <td style={{ width: 56 }}>
                      <Thumb src={p.poster?.sm?.url} alt={`${p.title} afişi`} />
                    </td>
                    <td>
                      <Link className="rowlink" href={`/oyunlar/${p.id}`}>
                        {p.title}
                      </Link>
                      <div className="row small" style={{ gap: 6, marginTop: 4 }}>
                        {p.on_stage && <Badge status="gold">Sahnede</Badge>}
                        {p.is_featured && <Badge status="gold">Öne çıkan</Badge>}
                      </div>
                    </td>
                    <td>
                      <Badge status={p.status} />
                    </td>
                    <td className="small">{p.genres.join(", ") || "—"}</td>
                    <td className="small muted">{p.issues.length ? p.issues.map((i) => i.message).join(", ") : "—"}</td>
                    <td className="small muted">{formatRelative(p.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pager page={page} pageSize={50} total={data.total} onPage={setPage} />}
      </div>
    </>
  );
}
