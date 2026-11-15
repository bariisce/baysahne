"use client";

import { Suspense, type ReactNode } from "react";
import { AuthProvider } from "@/components/auth";
import { Shell } from "@/components/Shell";

export default function PanelLayout({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <Shell>
        <Suspense fallback={null}>{children}</Suspense>
      </Shell>
    </AuthProvider>
  );
}
