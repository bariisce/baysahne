import { useMemo, useState } from "react";
import { ScrollView, StyleSheet, TextInput, View } from "react-native";
import { ProductionRow } from "@/components/production-card";
import { Screen } from "@/components/screen";
import { Chip, Display, EmptyState, ErrorState, Loading } from "@/components/ui";
import { liveCard, useNow } from "@/lib/time";
import type { Page, ProductionCard } from "@/lib/types";
import { useQuery } from "@/lib/use-query";
import { colors, fonts, radius, space } from "@/theme";

type Availability = "all" | "upcoming" | "on_stage";

export default function CatalogScreen() {
  const [q, setQ] = useState("");
  const [genre, setGenre] = useState<string | null>(null);
  const [availability, setAvailability] = useState<Availability>("all");

  // The whole catalogue is loaded once (it is small) and every filter runs on the device: choosing a genre
  // or an availability is instant, works offline, and cannot fail on its own request.
  const list = useQuery<Page<ProductionCard>>("/productions?page_size=100", { persist: true });
  const now = useNow();
  const all = useMemo(() => (list.data?.items ?? []).map((p) => liveCard(p, now)), [list.data, now]);
  const genres = useMemo(
    () => Array.from(new Set(all.flatMap((p) => p.genres))).sort((a, b) => fold(a).localeCompare(fold(b))),
    [all],
  );
  // A genre that left the catalogue after a refresh must not keep filtering everything out.
  const activeGenre = genre && genres.includes(genre) ? genre : null;

  const items = useMemo(() => {
    const needle = fold(q.trim());
    return all.filter(
      (p) =>
        (!activeGenre || p.genres.includes(activeGenre)) &&
        (availability !== "upcoming" || p.next_performance !== null) &&
        (availability !== "on_stage" || p.on_stage) &&
        (!needle || fold([p.title, p.author, p.director, ...p.genres].filter(Boolean).join(" ")).includes(needle)),
    );
  }, [all, q, activeGenre, availability]);

  return (
    <Screen refreshing={list.refreshing} onRefresh={list.refresh}>
      <View style={{ paddingHorizontal: space.lg }}>
        <Display>Oyunlar</Display>
        <TextInput
          value={q}
          onChangeText={setQ}
          placeholder="Oyun, yazar veya yönetmen ara"
          placeholderTextColor={colors.muted}
          style={styles.search}
          accessibilityLabel="Oyun ara"
          returnKeyType="search"
          clearButtonMode="while-editing"
          autoCorrect={false}
        />
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
        <Chip label="Tümü" selected={availability === "all"} onPress={() => setAvailability("all")} />
        <Chip label="Yaklaşan temsili olanlar" selected={availability === "upcoming"} onPress={() => setAvailability("upcoming")} />
        <Chip label="Sahnede" selected={availability === "on_stage"} onPress={() => setAvailability("on_stage")} />
      </ScrollView>
      {genres.length > 0 && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={[styles.chips, { paddingTop: 0 }]}>
          <Chip label="Tüm türler" selected={!activeGenre} onPress={() => setGenre(null)} />
          {genres.map((g) => (
            <Chip key={g} label={g} selected={activeGenre === g} onPress={() => setGenre(activeGenre === g ? null : g)} />
          ))}
        </ScrollView>
      )}

      {list.loading && !list.data && <Loading />}
      {list.error && !list.data && <ErrorState message={list.error.message} onRetry={list.refresh} />}
      {list.data && items.length === 0 && (
        <EmptyState
          title="Sonuç bulunamadı"
          message={availability === "upcoming" && !q ? "Şu anda yaklaşan temsili olan oyun yok. Yeni tarihler yakında duyurulacak." : "Arama veya filtreleri değiştirmeyi deneyin."}
        />
      )}
      {items.map((p) => (
        <ProductionRow key={p.id} p={p} />
      ))}
    </Screen>
  );
}

function fold(s: string) {
  return s
    .replace(/İ/g, "i")
    .replace(/I/g, "ı")
    .toLocaleLowerCase("tr-TR")
    .replace(/ç/g, "c")
    .replace(/ğ/g, "g")
    .replace(/ı/g, "i")
    .replace(/ö/g, "o")
    .replace(/ş/g, "s")
    .replace(/ü/g, "u");
}

const styles = StyleSheet.create({
  search: {
    marginTop: space.lg,
    minHeight: 46,
    paddingHorizontal: space.lg,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    color: colors.cream,
    fontFamily: fonts.text,
    fontSize: 16,
    borderWidth: 1,
    borderColor: colors.line,
  },
  chips: { paddingHorizontal: space.lg, paddingVertical: space.md },
});
