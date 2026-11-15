"use client";

import { useRef, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import { mediaSrc } from "@/lib/media";
import type { MediaItem, Page } from "@/lib/types";
import { useResource } from "@/lib/useResource";
import { Modal } from "./feedback";
import { ErrorBox, Pager, Spinner } from "./ui";

export const ACCEPT = "image/jpeg,image/png,image/webp";
export const MAX_MB = 15;

/** Client-side pre-check for fast feedback; the server re-validates everything. */
export function precheck(file: File): string | null {
  if (!ACCEPT.split(",").includes(file.type)) return `${file.name}: yalnızca JPEG, PNG veya WebP yüklenebilir.`;
  if (file.size > MAX_MB * 1024 * 1024) return `${file.name}: dosya ${MAX_MB} MB'tan büyük olamaz.`;
  return null;
}

export function UploadZone({ onUploaded, multiple = true }: { onUploaded: (items: MediaItem[]) => void; multiple?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [drag, setDrag] = useState(false);

  async function handle(files: FileList | File[]) {
    const list = Array.from(files);
    const errs: string[] = [];
    const done: MediaItem[] = [];
    for (const [i, f] of list.entries()) {
      const pre = precheck(f);
      if (pre) {
        errs.push(pre);
        continue;
      }
      setBusy(`Yükleniyor ${i + 1}/${list.length}: ${f.name}`);
      try {
        done.push(await api.upload<MediaItem>("/admin/media", f));
      } catch (e) {
        errs.push(`${f.name}: ${errorMessage(e)}`);
      }
    }
    setBusy(null);
    setErrors(errs);
    if (done.length) onUploaded(done);
    if (input.current) input.current.value = "";
  }

  return (
    <div className="stack">
      <div
        className={`dropzone ${drag ? "active" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          handle(e.dataTransfer.files);
        }}
      >
        <p style={{ margin: "0 0 10px" }}>Görselleri buraya sürükleyin veya</p>
        <button type="button" className="btn btn-primary" onClick={() => input.current?.click()} disabled={!!busy}>
          Bilgisayardan seç
        </button>
        <input
          ref={input}
          type="file"
          accept={ACCEPT}
          multiple={multiple}
          className="sr-only"
          aria-label="Görsel dosyası seç"
          onChange={(e) => e.target.files && handle(e.target.files)}
        />
        <p className="small" style={{ margin: "10px 0 0" }}>
          JPEG, PNG veya WebP · en fazla {MAX_MB} MB
        </p>
      </div>
      {busy && (
        <div className="alert alert-info" role="status">
          {busy}
        </div>
      )}
      {errors.map((e) => (
        <div key={e} className="alert alert-error" role="alert">
          {e}
        </div>
      ))}
    </div>
  );
}

export function MediaPicker({
  open,
  onClose,
  onPick,
  multiple = false,
  title,
}: {
  open: boolean;
  onClose: () => void;
  onPick: (ids: string[]) => void | Promise<void>;
  multiple?: boolean;
  title: string;
}) {
  const [page, setPage] = useState(1);
  const lib = useResource<Page<MediaItem>>(open ? `/admin/media?page=${page}&page_size=24` : null);
  const [selected, setSelected] = useState<string[]>([]);

  const toggle = (id: string) =>
    setSelected((s) => (multiple ? (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]) : [id]));

  const finish = async (ids: string[]) => {
    await onPick(ids);
    setSelected([]);
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      wide
      footer={
        <>
          <button className="btn" onClick={onClose}>
            Vazgeç
          </button>
          <button className="btn btn-primary" disabled={!selected.length} onClick={() => finish(selected)}>
            {multiple ? `Seçilenleri ekle (${selected.length})` : "Seç"}
          </button>
        </>
      }
    >
      <div className="stack">
        <UploadZone
          multiple={multiple}
          onUploaded={(items) => {
            if (!multiple) return finish([items[0].id]);
            lib.reload();
            setSelected((s) => [...s, ...items.map((i) => i.id).filter((id) => !s.includes(id))]);
          }}
        />
        <h3>Kütüphaneden seç</h3>
        {lib.error && <ErrorBox message={lib.error.message} onRetry={lib.reload} />}
        {lib.loading && !lib.data && <Spinner />}
        {lib.data && (
          <>
            <div className="media-grid">
              {lib.data.items.map((m) => (
                <button
                  type="button"
                  key={m.id}
                  className={`media-tile selectable ${selected.includes(m.id) ? "selected" : ""}`}
                  aria-pressed={selected.includes(m.id)}
                  onClick={() => toggle(m.id)}
                  style={{ padding: 0, textAlign: "left" }}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={mediaSrc(m.sm?.url ?? m.url)} alt={m.alt ?? m.original_filename ?? ""} loading="lazy" />
                  <div className="meta">
                    {m.original_filename ?? "görsel"} · {formatBytes(m.byte_size)}
                  </div>
                </button>
              ))}
            </div>
            <Pager page={page} pageSize={24} total={lib.data.total} onPage={setPage} />
          </>
        )}
      </div>
    </Modal>
  );
}
