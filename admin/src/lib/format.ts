const TZ = "Europe/Istanbul";

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("tr-TR", {
    timeZone: TZ,
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function formatRelative(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "az önce";
  if (diff < 3600) return `${Math.floor(diff / 60)} dk önce`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} sa önce`;
  return formatDateTime(iso);
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function leadLabel(minutes: number): string {
  if (minutes % 1440 === 0) return `${minutes / 1440} gün önce`;
  if (minutes % 60 === 0) return `${minutes / 60} saat önce`;
  return `${minutes} dakika önce`;
}

/** Today's date (YYYY-MM-DD) in Istanbul, used as the minimum for date pickers. */
export function todayInIstanbul(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(new Date());
}

export const STATUS_LABELS: Record<string, string> = {
  draft: "Taslak",
  published: "Yayında",
  archived: "Arşivde",
  scheduled: "Planlandı",
  cancelled: "İptal edildi",
  pending: "Bekliyor",
  processing: "Gönderiliyor",
  sent: "Gönderildi",
  failed: "Başarısız",
  skipped: "Atlandı",
};

export const CREDIT_ROLE_LABELS: Record<string, string> = {
  author: "Yazar",
  director: "Yönetmen",
  assistant_director: "Yönetmen Yardımcısı",
  translator: "Çeviri",
  adaptation: "Uyarlama",
  poster_design: "Afiş Tasarım",
  cast: "Oyuncu",
  other: "Diğer",
};

export const CANCEL_REASON_LABELS: Record<string, string> = {
  category_disabled: "Bildirim türü kapatıldı",
  production_not_published: "Oyun yayında değil",
  performance_deleted: "Temsil silindi",
  performance_started: "Temsil zamanı geçti",
  performance_cancelled: "Temsil iptal edildi",
  performance_unpublished: "Temsil yayından kaldırıldı",
  performance_rescheduled: "Temsil tarihi değişti",
  lead_time_removed: "Hatırlatma süresi kaldırıldı",
  performance_restored: "İptal geri alındı",
  performance_not_active: "Temsil etkin değil",
  superseded_by_newer_reschedule: "Daha yeni bir tarih değişikliği var",
  admin_cancelled: "Yönetici iptal etti",
};
