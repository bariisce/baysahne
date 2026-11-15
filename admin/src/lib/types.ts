export type Role = "admin" | "editor";
export type Me = { id: string; email: string; full_name: string; role: Role };

export type ImageVariant = { url: string; width: number; height: number } | null;
export type Img = {
  id: string;
  url: string;
  width: number | null;
  height: number | null;
  alt: string | null;
  sm: ImageVariant;
  lg: ImageVariant;
};
export type MediaItem = Img & {
  original_filename: string | null;
  content_type: string;
  byte_size: number;
  source: string;
  created_at: string;
  usage?: { type: string; id: string; label: string }[];
  duplicate?: boolean;
};

export type LocalTime = {
  local_iso: string;
  local_date: string;
  local_weekday: string;
  local_time: string;
};

export type Venue = {
  id: string;
  name: string;
  address: string | null;
  district: string | null;
  city: string | null;
  maps_url: string | null;
  public_info: string | null;
  timezone: string;
  is_active?: boolean;
};

export type Performance = LocalTime & {
  id: string;
  starts_at: string;
  status: "scheduled" | "cancelled";
  is_cancelled: boolean;
  cancellation_note: string | null;
  is_rescheduled: boolean;
  rescheduled_from_local: LocalTime | null;
  public_note: string | null;
  venue: Venue;
  production: { id: string; slug: string; title: string; poster: Img | null };
  visibility: "draft" | "published";
  internal_notes: string | null;
  first_published_at: string | null;
  production_status: "draft" | "published" | "archived";
  is_past: boolean;
  warnings?: string[];
  notification_job_id?: string | null;
};

export type CreditRole =
  | "author"
  | "director"
  | "assistant_director"
  | "translator"
  | "adaptation"
  | "poster_design"
  | "cast"
  | "other";

export type Credit = { role: CreditRole; label?: string; role_label?: string | null; name: string };
export type Video = { url: string; title: string | null; youtube_id?: string | null };
export type Issue = { field: string; message: string };

export type ProductionStatus = "draft" | "published" | "archived";

export type ProductionSummary = {
  id: string;
  slug: string;
  title: string;
  status: ProductionStatus;
  genres: string[];
  is_featured: boolean;
  on_stage: boolean;
  poster: Img | null;
  updated_at: string;
  issues: Issue[];
};

export type Production = ProductionSummary & {
  short_description: string | null;
  description: string | null;
  duration_minutes: number | null;
  act_count: number | null;
  duration_text: string | null;
  duration_label: string | null;
  sort_order: number;
  /** Position in the home screen's "Repertuvar" strip; null = not shown there. */
  home_order: number | null;
  credits: Credit[];
  videos: Video[];
  gallery: (Img & { image_id: string; caption: string | null })[];
  first_published_at: string | null;
  upcoming_performances: Record<string, number>;
  notification_job_id?: string | null;
  notification_skipped_reason?: string | null;
};

export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export type Article = {
  id: string;
  slug: string;
  title: string;
  body: string;
  excerpt: string | null;
  image: Img | null;
  image_id: string | null;
  status: "draft" | "published";
  published_at: string | null;
  updated_at: string;
};

export type JobStatus = "pending" | "processing" | "sent" | "failed" | "cancelled" | "skipped";
export type NotificationJob = {
  id: string;
  category: string;
  category_label: string;
  status: JobStatus;
  scheduled_for: string;
  attempts: number;
  max_attempts: number;
  title: string | null;
  body: string | null;
  lead_minutes: number | null;
  last_error: string | null;
  cancel_reason: string | null;
  stats: { targeted?: number; ok?: number; error?: number; rate_limited?: number };
  created_at: string;
  completed_at: string | null;
  triggered_by: string;
};

export type CategorySetting = {
  category: string;
  label: string;
  enabled: boolean;
  title_template: string;
  body_template: string;
  placeholders: { name: string; label: string }[];
};

export type NotificationSettings = {
  categories: CategorySetting[];
  policy: { reminder_lead_minutes: number[]; max_per_device_per_day: number; broadcast_cooldown_minutes: number };
  devices: Record<string, number>;
  provider: string;
};
