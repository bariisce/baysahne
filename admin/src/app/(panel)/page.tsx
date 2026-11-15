"use client";

import Link from "next/link";
import { useAuth } from "@/components/auth";
import { Badge, Card, EmptyState, ErrorBox, PageHeader, Spinner } from "@/components/ui";
import { formatRelative } from "@/lib/format";
import type { Issue, Performance } from "@/lib/types";
import { useResource } from "@/lib/useResource";

type Dashboard = {
  productions: { total: number; published: number; draft: number; archived: number };
  performances: { upcoming: number; upcoming_public: number; upcoming_draft: number };
  next_performances: Performance[];
  incomplete_productions: { id: string; title: string; status: string; issues: Issue[] }[];
  recent_activity: { at: string; actor: string | null; summary: string | null; action: string }[];
  notifications: { pending: number; failed_7d: number; active_devices: number };
  articles: { draft: number };
  tasks: { kind: string; message: string }[];
};

function Stat({ value, label, href }: { value: number; label: string; href?: string }) {
  const body = (
    <>
      <div className="stat">{value}</div>
      <div className="stat-label">{label}</div>
    </>
  );
  return <div className="card">{href ? <Link href={href} style={{ color: "inherit", textDecoration: "none" }}>{body}</Link> : body}</div>;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useResource<Dashboard>("/admin/dashboard");

  return (
    <>
      <PageHeader
        title={`Hoş geldiniz, ${user.full_name.split(" ")[0]}`}
        description="Bay Sahne içeriğinin güncel durumu."
        actions={
          <>
            <Link className="btn" href="/temsiller?yeni=1">
              Temsil ekle
            </Link>
            <Link className="btn btn-primary" href="/oyunlar/yeni">
              Yeni oyun
            </Link>
          </>
        }
      />
      {error && <ErrorBox message={error.message} onRetry={reload} />}
      {loading && !data && <Spinner />}
      {data && (
        <div className="stack">
          <div className="grid grid-4">
            <Stat value={data.productions.total} label="Toplam oyun" href="/oyunlar" />
            <Stat value={data.productions.published} label="Yayındaki oyun" href="/oyunlar?durum=published" />
            <Stat value={data.productions.draft} label="Taslak oyun" href="/oyunlar?durum=draft" />
            <Stat value={data.performances.upcoming_public} label="Uygulamada görünen yaklaşan temsil" href="/temsiller" />
          </div>

          {data.tasks.length > 0 && (
            <Card title="Yapılacaklar">
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {data.tasks.map((t) => (
                  <li key={t.kind} style={{ marginBottom: 6 }}>
                    {t.message}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <div className="grid grid-2">
            <Card title="Yaklaşan temsiller" actions={<Link href="/temsiller">Tümü</Link>}>
              {data.next_performances.length === 0 ? (
                <EmptyState title="Planlanmış temsil yok">
                  <p>Gerçek tarihler girildiğinde burada görünür.</p>
                </EmptyState>
              ) : (
                <ul style={{ listStyle: "none", margin: 0, padding: 0 }} className="stack">
                  {data.next_performances.map((p) => (
                    <li key={p.id} className="row" style={{ justifyContent: "space-between" }}>
                      <span>
                        <strong>{p.production.title}</strong>
                        <br />
                        <span className="small muted">
                          {p.local_date} {p.local_weekday}, {p.local_time} · {p.venue.name}
                        </span>
                      </span>
                      <Badge status={p.visibility} />
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card title="Eksik bilgisi olan oyunlar">
              {data.incomplete_productions.length === 0 ? (
                <EmptyState title="Her şey tamam" />
              ) : (
                <ul style={{ listStyle: "none", margin: 0, padding: 0 }} className="stack">
                  {data.incomplete_productions.map((p) => (
                    <li key={p.id}>
                      <Link href={`/oyunlar/${p.id}`} style={{ fontWeight: 600 }}>
                        {p.title}
                      </Link>{" "}
                      <span className="small muted">— {p.issues.map((i) => i.message).join(", ")}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <div className="grid grid-2">
            <Card title="Son değişiklikler">
              {data.recent_activity.length === 0 ? (
                <EmptyState title="Henüz değişiklik yok" />
              ) : (
                <ul style={{ listStyle: "none", margin: 0, padding: 0 }} className="stack">
                  {data.recent_activity.map((a, i) => (
                    <li key={i} className="small">
                      <strong>{a.summary ?? a.action}</strong>
                      <br />
                      <span className="muted">
                        {a.actor ?? "sistem"} · {formatRelative(a.at)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <Card title="Bildirimler" actions={<Link href="/bildirimler">Ayrıntılar</Link>}>
              <div className="grid grid-3">
                <div>
                  <div className="stat">{data.notifications.active_devices}</div>
                  <div className="stat-label">Bildirim izni veren cihaz</div>
                </div>
                <div>
                  <div className="stat">{data.notifications.pending}</div>
                  <div className="stat-label">Bekleyen bildirim</div>
                </div>
                <div>
                  <div className="stat" style={{ color: data.notifications.failed_7d ? "var(--danger)" : undefined }}>
                    {data.notifications.failed_7d}
                  </div>
                  <div className="stat-label">Başarısız (7 gün)</div>
                </div>
              </div>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
