"use client";

import { useId, type ReactNode } from "react";
import { STATUS_LABELS } from "@/lib/format";
import { mediaSrc } from "@/lib/media";

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="actions">{actions}</div>}
    </div>
  );
}

export function Card({ title, actions, children }: { title?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      {(title || actions) && (
        <div className="card-head">
          {title && <h2>{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

type FieldProps = {
  label: string;
  hint?: ReactNode;
  error?: string;
  required?: boolean;
  children: (props: { id: string; "aria-invalid": boolean; "aria-describedby"?: string }) => ReactNode;
};

/** Accessible label + hint + error wiring for any input. */
export function Field({ label, hint, error, required, children }: FieldProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errId = error ? `${id}-err` : undefined;
  return (
    <div className="field">
      <label htmlFor={id}>
        {label}
        {required && <span aria-hidden="true" style={{ color: "var(--danger)" }}> *</span>}
      </label>
      {children({ id, "aria-invalid": !!error, "aria-describedby": [hintId, errId].filter(Boolean).join(" ") || undefined })}
      {hint && <span id={hintId} className="hint">{hint}</span>}
      {error && <span id={errId} className="error" role="alert">{error}</span>}
    </div>
  );
}

export function Badge({ status, children }: { status?: string; children?: ReactNode }) {
  return <span className={`badge ${status ? `badge-${status}` : ""}`}>{children ?? (status ? STATUS_LABELS[status] ?? status : "")}</span>;
}

export function Spinner({ label = "Yükleniyor…" }: { label?: string }) {
  return (
    <div className="empty" role="status" aria-live="polite">
      {label}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      {children}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="alert alert-error row" role="alert" style={{ justifyContent: "space-between" }}>
      <span>{message}</span>
      {onRetry && (
        <button type="button" className="btn btn-sm" onClick={onRetry}>
          Tekrar dene
        </button>
      )}
    </div>
  );
}

export function Thumb({ src, alt }: { src?: string | null; alt: string }) {
  // Plain <img>: media URLs are same-origin (proxied) or a configured CDN; no Next image optimiser needed.
  // eslint-disable-next-line @next/next/no-img-element
  return src ? <img className="thumb" src={mediaSrc(src)} alt={alt} loading="lazy" /> : <div className="thumb-empty" aria-label="Afiş yok" />;
}

export function Pager({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages <= 1) return null;
  return (
    <nav className="row" aria-label="Sayfalama" style={{ justifyContent: "flex-end", marginTop: 12 }}>
      <button className="btn btn-sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Önceki
      </button>
      <span className="small muted">
        {page} / {pages}
      </span>
      <button className="btn btn-sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Sonraki
      </button>
    </nav>
  );
}
