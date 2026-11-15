import type { ReactNode } from "react";

export function AuthLayout({ title, lead, children }: { title: string; lead?: string; children: ReactNode }) {
  return (
    <main className="auth">
      <div style={{ width: "min(420px, 100%)" }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo.png" alt="Bay Sahne" style={{ display: "block", height: 48, margin: "0 auto 22px" }} />
        <div className="auth-card">
          <h1>{title}</h1>
          {lead && <p className="lead">{lead}</p>}
          {children}
        </div>
      </div>
    </main>
  );
}
