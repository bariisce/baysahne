export type Variant = { url: string; width: number; height: number } | null;
export type Img = { id: string; url: string; width: number | null; height: number | null; alt: string | null; sm: Variant; lg: Variant };

export type LocalTime = {
  local_iso: string;
  local_date: string;
  local_day: number;
  local_month: string;
  local_year: number;
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
  production?: { id: string; slug: string; title: string; genres: string[]; poster: Img | null };
};

export type ProductionCard = {
  id: string;
  slug: string;
  title: string;
  genres: string[];
  excerpt: string | null;
  poster: Img | null;
  author: string | null;
  director: string | null;
  duration_label: string | null;
  is_featured: boolean;
  on_stage: boolean;
  upcoming_count: number;
  next_performance: Performance | null;
};

export type ProductionDetail = ProductionCard & {
  short_description: string | null;
  description: string | null;
  credits: { role: string; label: string; name: string }[];
  gallery: (Img & { caption: string | null })[];
  videos: { url: string; title: string | null; youtube_id: string | null }[];
  performances: Performance[];
};

export type ArticleSummary = {
  id: string;
  slug: string;
  title: string;
  excerpt: string | null;
  image: Img | null;
  published_at: string | null;
  published_local: LocalTime | null;
  body?: string;
};

export type Home = {
  featured: ProductionCard[];
  featured_source: "featured" | "on_stage" | "upcoming";
  upcoming: Performance[];
  new_productions: ProductionCard[];
  articles: ArticleSummary[];
};

export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export type Organization = {
  name: string;
  short_name: string | null;
  address: string | null;
  phones: string[];
  email: string | null;
  website_url: string | null;
  instagram_url: string | null;
  x_url: string | null;
  youtube_url: string | null;
  about: {
    motto?: string;
    story_title?: string;
    story?: string;
    quote?: string;
    quote_author?: string;
    values?: { title: string; text: string }[];
    mission?: string;
    vision?: string;
  };
  logo: Img | null;
};

export type LegalDoc = { slug: string; title: string; body?: string; updated_at: string };
