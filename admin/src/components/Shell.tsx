"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { useAuth } from "./auth";

type Item = { href: string; label: string; adminOnly?: boolean };

const GROUPS: { title: string; items: Item[] }[] = [
  { title: "İçerik", items: [
    { href: "/", label: "Genel bakış" },
    { href: "/oyunlar", label: "Oyunlar" },
    { href: "/temsiller", label: "Program / Temsiller" },
    { href: "/salonlar", label: "Salonlar" },
    { href: "/duyurular", label: "Duyurular" },
    { href: "/medya", label: "Görseller" },
  ] },
  { title: "Bildirimler", items: [{ href: "/bildirimler", label: "Bildirimler" }] },
  { title: "Yönetim", items: [
    { href: "/ekip", label: "Ekip ve erişim", adminOnly: true },
    { href: "/ayarlar", label: "Kurum ve yasal metinler", adminOnly: true },
    { href: "/kayitlar", label: "İşlem kayıtları", adminOnly: true },
  ] },
];

export const ROLE_LABELS = { admin: "Yönetici", editor: "İçerik editörü" } as const;

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <div className="shell">
      <div className="mobile-bar">
        <button className="btn btn-sm btn-on-dark" aria-expanded={open} aria-controls="sidebar" onClick={() => setOpen(!open)}>
          Menü
        </button>
        <strong>Bay Sahne Yönetim</strong>
      </div>
      <aside id="sidebar" className={`sidebar ${open ? "open" : ""}`} onClick={(e) => (e.target as HTMLElement).tagName === "A" && setOpen(false)}>
        <div className="brand">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.png" alt="Bay Sahne" />
        </div>
        <nav className="nav" aria-label="Ana menü">
          {GROUPS.map((g) => {
            const items = g.items.filter((i) => !i.adminOnly || user.role === "admin");
            if (!items.length) return null;
            return (
              <div key={g.title}>
                <div className="nav-group">{g.title}</div>
                {items.map((i) => (
                  <Link key={i.href} href={i.href} aria-current={isActive(i.href) ? "page" : undefined}>
                    {i.label}
                  </Link>
                ))}
              </div>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          <div style={{ fontWeight: 600, color: "#fff" }}>{user.full_name}</div>
          <div>{ROLE_LABELS[user.role]}</div>
          <div className="row" style={{ marginTop: 8 }}>
            <Link className="btn btn-sm btn-on-dark" href="/hesabim">
              Hesabım
            </Link>
            <button className="btn btn-sm btn-on-dark" onClick={logout}>
              Çıkış yap
            </button>
          </div>
        </div>
      </aside>
      <main className="main" id="icerik">
        {children}
      </main>
    </div>
  );
}
