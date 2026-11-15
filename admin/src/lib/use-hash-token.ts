"use client";

import { useSyncExternalStore } from "react";

/**
 * Reads a one-time token from the URL fragment (`/davet#<token>`). Fragments are never sent to servers,
 * so the token does not appear in proxy or access logs. Returns undefined during SSR and "" if absent.
 */
export function useHashToken(): string | undefined {
  return useSyncExternalStore(
    (cb) => {
      window.addEventListener("hashchange", cb);
      return () => window.removeEventListener("hashchange", cb);
    },
    () => decodeURIComponent(window.location.hash.replace(/^#/, "")).trim(),
    () => undefined,
  );
}
