"use client";

import { useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api";
import type { Me } from "@/lib/types";

const AuthContext = createContext<{ user: Me; logout: () => Promise<void> } | null>(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}

export function useIsAdmin(): boolean {
  return useAuth().user.role === "admin";
}

/**
 * Loads the current admin from the backend. This is a UX guard only — every API call is authorised
 * server-side, so hiding a menu item never grants or removes a permission.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<Me | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<{ user: Me }>("/admin/auth/me")
      .then((r) => setUser(r.user))
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) router.replace("/giris");
        else setFailed(e instanceof ApiError ? e.message : "Oturum doğrulanamadı.");
      });
    const onUnauthorized = () => router.replace("/giris");
    window.addEventListener("baysahne:unauthorized", onUnauthorized);
    return () => window.removeEventListener("baysahne:unauthorized", onUnauthorized);
  }, [router]);

  const logout = async () => {
    try {
      await api.post("/admin/auth/logout");
    } finally {
      router.replace("/giris");
    }
  };

  if (failed)
    return (
      <div className="auth">
        <div className="auth-card">
          <div className="alert alert-error">{failed}</div>
          <button className="btn" style={{ marginTop: 12 }} onClick={() => window.location.reload()}>
            Tekrar dene
          </button>
        </div>
      </div>
    );
  if (!user)
    return (
      <div className="auth" role="status" aria-live="polite">
        <span style={{ color: "var(--cream)" }}>Yükleniyor…</span>
      </div>
    );
  return <AuthContext.Provider value={{ user, logout }}>{children}</AuthContext.Provider>;
}

/** Renders children only for admins (UI convenience; the backend enforces the same rule). */
export function AdminOnly({ children, fallback = null }: { children: ReactNode; fallback?: ReactNode }) {
  return useIsAdmin() ? <>{children}</> : <>{fallback}</>;
}
