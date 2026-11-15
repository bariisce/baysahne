import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import type { ReactNode } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { clearQueryCache } from "@/lib/use-query";

jest.mock("expo-router", () => {
  const { Text } = jest.requireActual("react-native");
  return {
    Link: ({ children, asChild }: { children: ReactNode; asChild?: boolean }) => (asChild ? children : <Text>{children}</Text>),
    router: { push: jest.fn(), replace: jest.fn() },
    Stack: { Screen: () => null },
    useLocalSearchParams: () => ({ slug: "sefiller" }),
  };
});
jest.mock("react-native-safe-area-context", () => ({ useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) }));
jest.mock("@/components/push-provider", () => ({ usePush: () => ({ state: "granted", enable: jest.fn() }) }));
jest.mock("expo-constants", () => ({ __esModule: true, default: { expoConfig: { extra: { apiUrl: "https://api.example.com" } } } }));

const venue = { id: "v1", name: "Ana Salon", address: "Toros Mah.", district: "Çukurova", city: "Adana", maps_url: null, public_info: null };
const time = (day: number, t = "20:30") => ({
  local_iso: "", local_date: `${day} Kasım 2026`, local_day: day, local_month: "Kasım", local_year: 2026, local_weekday: "Cuma", local_time: t,
});
const card = (over: object = {}) => ({
  id: "p1", slug: "sefiller", title: "Sefiller", genres: ["Dram"], excerpt: "Suç işlemek, suçlu olmak mıdır?", poster: null,
  author: "Victor Hugo", director: "S. Çağrı Pepesöyler", duration_label: "150 dakika · 2 perde", is_featured: false,
  on_stage: true, upcoming_count: 0, next_performance: null, ...over,
});

const DAY = 24 * 60 * 60 * 1000;
const PAST = new Date(Date.now() - 5 * DAY).toISOString();
const FUTURE = new Date(Date.now() + 4 * DAY).toISOString();
const perf = (id: string, startsAt: string, day = 14) => ({
  id, starts_at: startsAt, ...time(day), status: "scheduled", is_cancelled: false, cancellation_note: null, is_rescheduled: false,
  rescheduled_from_local: null, public_note: null, venue, production: { id: "p1", slug: "sefiller", title: "Sefiller", genres: [], poster: null },
});

function mockApi(routes: Record<string, unknown>) {
  globalThis.fetch = jest.fn(async (url: string) => {
    const path = String(url).replace("https://api.example.com/api/v1", "");
    const key = Object.keys(routes).find((k) => path.startsWith(k));
    if (!key) return { ok: false, status: 404, json: async () => ({ error: { code: "not_found", message: "İçerik bulunamadı." } }) };
    return { ok: true, status: 200, json: async () => routes[key] };
  }) as never;
}

beforeEach(async () => {
  clearQueryCache();
  await AsyncStorage.clear();
});

describe("Home", () => {
  it("stays useful with no upcoming performances", async () => {
    mockApi({ "/home": { featured: [card()], featured_source: "on_stage", upcoming: [], new_productions: [card()], articles: [] } });
    const Home = require("@/app/(tabs)/index").default;
    await render(<Home />);
    expect(await screen.findByText("Yeni tarihler yakında")).toBeTruthy();
    expect(screen.getByText("Repertuvarı keşfet")).toBeTruthy();
    expect(screen.getAllByText("Sefiller").length).toBeGreaterThan(0);
    expect(screen.getByText("Sahnede")).toBeTruthy();
  });

  it("shows a retryable error when the API is unreachable", async () => {
    globalThis.fetch = jest.fn().mockRejectedValue(new TypeError("offline")) as never;
    const Home = require("@/app/(tabs)/index").default;
    await render(<Home />);
    expect(await screen.findByText("Bir sorun oluştu")).toBeTruthy();
    mockApi({ "/home": { featured: [], featured_source: "featured", upcoming: [], new_productions: [], articles: [] } });
    await fireEvent.press(screen.getByText("Tekrar dene"));
    await waitFor(() => expect(screen.getByText("Yeni tarihler yakında")).toBeTruthy());
  });
});

describe("Production detail", () => {
  it("renders available sections and hides missing ones", async () => {
    mockApi({
      "/productions/sefiller": {
        ...card(), short_description: null, description: "Suç işlemek, suçlu olmak mıdır?", credits: [{ role: "author", label: "Yazar", name: "Victor Hugo" }],
        gallery: [], videos: [], performances: [
          { id: "x1", starts_at: "", ...time(14), status: "scheduled", is_cancelled: false, cancellation_note: null, is_rescheduled: false, rescheduled_from_local: null, public_note: null, venue },
          { id: "x2", starts_at: "", ...time(21), status: "cancelled", is_cancelled: true, cancellation_note: "Teknik nedenlerle", is_rescheduled: false, rescheduled_from_local: null, public_note: null, venue },
        ],
      },
    });
    const Detail = require("@/app/oyun/[slug]").default;
    await render(<Detail />);
    expect(await screen.findByText("Künye")).toBeTruthy();
    expect(screen.getByText("Victor Hugo")).toBeTruthy();
    expect(screen.getByText("İPTAL EDİLDİ — Teknik nedenlerle")).toBeTruthy();
    expect(screen.getByLabelText(/14 Kasım 2026 Cuma, saat 20:30. Ana Salon/)).toBeTruthy();
    expect(screen.queryByText("Oyundan kareler")).toBeNull();
    expect(screen.queryByText("Video")).toBeNull();
  });

  it("shows a not-found state for unpublished productions", async () => {
    mockApi({});
    const Detail = require("@/app/oyun/[slug]").default;
    await render(<Detail />);
    expect(await screen.findByText("Oyun bulunamadı")).toBeTruthy();
  });
});

describe("Schedule", () => {
  it("shows an honest empty state instead of placeholder dates", async () => {
    mockApi({ "/performances": { items: [], total: 0, page: 1, page_size: 100 } });
    const Program = require("@/app/(tabs)/program").default;
    await render(<Program />);
    expect(await screen.findByText("Yeni tarihler yakında")).toBeTruthy();
  });

  it("groups performances by month and labels rescheduled ones", async () => {
    mockApi({
      "/performances": {
        items: [{
          id: "x1", starts_at: "", ...time(14, "21:00"), status: "scheduled", is_cancelled: false, cancellation_note: null, is_rescheduled: true,
          rescheduled_from_local: time(7, "20:00"), public_note: null, venue, production: { id: "p1", slug: "sefiller", title: "Sefiller", genres: [], poster: null },
        }],
        total: 1, page: 1, page_size: 100,
      },
    });
    const Program = require("@/app/(tabs)/program").default;
    await render(<Program />);
    expect(await screen.findByText("Kasım 2026")).toBeTruthy();
    expect(screen.getByText("Tarihi değişti (önceki: 7 Kasım 2026, 20:00)")).toBeTruthy();
  });
});

describe("Catalogue", () => {
  const catalogue = () => {
    const items = [
      card({ next_performance: perf("n1", FUTURE), upcoming_count: 1 }),
      card({ id: "p2", slug: "mufettis", title: "Müfettiş", genres: ["Komedi"], author: "Nikolay Gogol", on_stage: false,
             next_performance: perf("n2", PAST), upcoming_count: 1 }),
    ];
    return { items, total: items.length, page: 1, page_size: 100 };
  };

  it("searches Turkish text locally", async () => {
    mockApi({ "/productions": catalogue() });
    const Catalog = require("@/app/(tabs)/oyunlar").default;
    await render(<Catalog />);
    expect((await screen.findAllByText("Sefiller")).length).toBeGreaterThan(0);

    await fireEvent.changeText(screen.getByLabelText("Oyun ara"), "MUFETTİS");
    expect(screen.queryAllByText("Sefiller")).toHaveLength(0);
    expect(screen.getAllByText("Müfettiş").length).toBeGreaterThan(0);
  });

  it("filters by genre and availability on the device, even when the API has gone away", async () => {
    mockApi({ "/productions": catalogue() });
    const Catalog = require("@/app/(tabs)/oyunlar").default;
    await render(<Catalog />);
    expect((await screen.findAllByText("Sefiller")).length).toBeGreaterThan(0);

    // From here on every request fails, as it does while the database is down.
    const down = jest.fn(async () => ({ ok: false, status: 503, json: async () => ({ error: { code: "service_unavailable", message: "Hizmet geçici olarak kullanılamıyor." } }) }));
    globalThis.fetch = down as never;

    await fireEvent.press(screen.getByRole("button", { name: "Komedi" }));
    expect(screen.getAllByText("Müfettiş").length).toBeGreaterThan(0);
    expect(screen.queryAllByText("Sefiller")).toHaveLength(0);
    expect(screen.queryByText("Bir sorun oluştu")).toBeNull();

    await fireEvent.press(screen.getByRole("button", { name: "Tüm türler" }));
    await fireEvent.press(screen.getByRole("button", { name: "Sahnede" }));
    expect(screen.getAllByText("Sefiller").length).toBeGreaterThan(0);
    expect(screen.queryAllByText("Müfettiş")).toHaveLength(0);

    // "Müfettiş" only has a performance that has already started: it is not "upcoming" any more.
    await fireEvent.press(screen.getByRole("button", { name: "Yaklaşan temsili olanlar" }));
    expect(screen.getAllByText("Sefiller").length).toBeGreaterThan(0);
    expect(screen.queryAllByText("Müfettiş")).toHaveLength(0);
    expect(down).not.toHaveBeenCalled();
  });
});

describe("Past performances", () => {
  it("are dropped from the schedule even when the device only has an old cached copy", async () => {
    await AsyncStorage.setItem(
      "bs-cache:v1:/performances?page_size=100",
      JSON.stringify({ items: [perf("old", PAST, 8), perf("new", FUTURE, 17)], total: 2, page: 1, page_size: 100 }),
    );
    globalThis.fetch = jest.fn().mockRejectedValue(new TypeError("offline")) as never;
    const Program = require("@/app/(tabs)/program").default;
    await render(<Program />);
    expect(await screen.findByLabelText(/17 Kasım 2026/)).toBeTruthy();
    expect(screen.queryByLabelText(/8 Kasım 2026/)).toBeNull();
    expect(screen.queryByText("Saatler Türkiye saatine göredir.")).toBeNull();
  });

  it("leave an honest empty state when nothing upcoming is left", async () => {
    mockApi({ "/performances": { items: [perf("old", PAST, 8)], total: 1, page: 1, page_size: 100 } });
    const Program = require("@/app/(tabs)/program").default;
    await render(<Program />);
    expect(await screen.findByText("Yeni tarihler yakında")).toBeTruthy();
  });

  it("are not offered on the home screen or as a production's next performance", async () => {
    mockApi({
      "/home": {
        featured: [card({ next_performance: perf("old", PAST, 8), upcoming_count: 1 })], featured_source: "on_stage",
        upcoming: [perf("old", PAST, 8)], new_productions: [], articles: [],
      },
    });
    const Home = require("@/app/(tabs)/index").default;
    await render(<Home />);
    expect(await screen.findByText("Yeni tarihler yakında")).toBeTruthy();
    expect(screen.queryByText(/Sıradaki temsil/)).toBeNull();
  });
});
