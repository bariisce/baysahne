import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { Link } from "expo-router";
import { useMemo } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { NotificationPrompt } from "@/components/notification-prompt";
import { PerformanceRow } from "@/components/performance-row";
import { Poster } from "@/components/poster";
import { PosterTile } from "@/components/production-card";
import { Screen } from "@/components/screen";
import { Body, Button, EmptyState, ErrorState, Eyebrow, Loading, SectionHeader } from "@/components/ui";
import { liveCard, upcomingOnly, useNow } from "@/lib/time";
import type { Home, ProductionCard } from "@/lib/types";
import { useQuery } from "@/lib/use-query";
import { colors, fonts, radius, space } from "@/theme";

const FEATURED_LABEL = { featured: "Öne çıkan", on_stage: "Sahnede", upcoming: "Yakında sahnede" } as const;

export default function HomeScreen() {
  const q = useQuery<Home>("/home", { persist: true });
  const now = useNow();
  // Cached content can be days old: nothing that has already started is shown as upcoming.
  const d = useMemo(
    () =>
      q.data && {
        ...q.data,
        featured: q.data.featured.map((p) => liveCard(p, now)),
        new_productions: q.data.new_productions.map((p) => liveCard(p, now)),
        upcoming: upcomingOnly(q.data.upcoming, now),
      },
    [q.data, now],
  );

  return (
    <Screen refreshing={q.refreshing} onRefresh={q.refresh}>
      <View style={styles.brand}>
        <Image source={require("../../../assets/logo.png")} style={styles.logo} contentFit="contain" accessibilityLabel="Bay Sahne" accessible />
      </View>

      {q.loading && !d && <Loading />}
      {q.error && !d && <ErrorState message={q.error.message} onRetry={q.refresh} />}

      {d && (
        <>
          {d.featured.length > 0 && <Hero p={d.featured[0]} label={FEATURED_LABEL[d.featured_source]} />}
          {d.featured.length > 1 && (
            <FlatList
              horizontal
              data={d.featured.slice(1)}
              keyExtractor={(p) => p.id}
              renderItem={({ item }) => <PosterTile p={item} width={132} />}
              contentContainerStyle={{ paddingHorizontal: space.lg, paddingTop: space.lg }}
              showsHorizontalScrollIndicator={false}
            />
          )}

          <NotificationPrompt />

          <SectionHeader
            title="Yaklaşan temsiller"
            action={
              d.upcoming.length > 0 ? (
                <Link href="/program" style={styles.more}>
                  Tüm program
                </Link>
              ) : undefined
            }
          />
          {d.upcoming.length === 0 ? (
            <EmptyState
              title="Yeni tarihler yakında"
              message="Şu anda planlanmış bir temsil bulunmuyor. Yeni tarihler açıklandığında burada göreceksiniz."
              action={
                <Link href="/oyunlar" asChild>
                  <Button label="Repertuvarı keşfet" variant="ghost" onPress={() => {}} />
                </Link>
              }
            />
          ) : (
            d.upcoming.slice(0, 5).map((p) => <PerformanceRow key={p.id} perf={p} />)
          )}

          {d.new_productions.length > 0 && (
            <>
              <SectionHeader
                title="Repertuvar"
                action={
                  <Link href="/oyunlar" style={styles.more}>
                    Tüm oyunlar
                  </Link>
                }
              />
              <FlatList
                horizontal
                data={d.new_productions}
                keyExtractor={(p) => p.id}
                renderItem={({ item }) => <PosterTile p={item} />}
                contentContainerStyle={{ paddingHorizontal: space.lg }}
                showsHorizontalScrollIndicator={false}
              />
            </>
          )}

          {d.articles.length > 0 && (
            <>
              <SectionHeader title="Duyurular" />
              {d.articles.map((a) => (
                <Link key={a.id} href={`/duyuru/${a.slug}`} asChild>
                  <Pressable accessibilityRole="link" style={styles.article}>
                    {a.published_local && <Eyebrow>{a.published_local.local_date}</Eyebrow>}
                    <Text style={styles.articleTitle}>{a.title}</Text>
                    {a.excerpt && (
                      <Body muted numberOfLines={2}>
                        {a.excerpt}
                      </Body>
                    )}
                  </Pressable>
                </Link>
              ))}
            </>
          )}

          <Link href="/hakkimizda" asChild>
            <Pressable accessibilityRole="link" style={styles.aboutLink}>
              <Text style={styles.aboutText}>Bay Sahne’yi tanıyın</Text>
              <Text style={styles.more}>Hakkımızda ›</Text>
            </Pressable>
          </Link>
        </>
      )}
    </Screen>
  );
}

function Hero({ p, label }: { p: ProductionCard; label: string }) {
  return (
    <Link href={`/oyun/${p.slug}`} asChild>
      <Pressable accessibilityRole="link" accessibilityLabel={`${label}: ${p.title}`} style={styles.hero}>
        <Poster image={p.poster} title={p.title} size="lg" rounded={false} style={StyleSheet.absoluteFill} />
        <LinearGradient colors={["transparent", "rgba(12,10,9,0.75)", colors.ink]} locations={[0.35, 0.7, 1]} style={StyleSheet.absoluteFill} />
        <View style={styles.heroBody}>
          <Eyebrow>{label}</Eyebrow>
          <Text style={styles.heroTitle}>{p.title}</Text>
          {p.genres.length > 0 && <Text style={styles.heroMeta}>{[p.genres.join(" · "), p.duration_label].filter(Boolean).join("  ·  ")}</Text>}
          {p.excerpt && (
            <Body numberOfLines={3} style={{ marginTop: space.sm }}>
              {p.excerpt}
            </Body>
          )}
          {p.next_performance && (
            <Text style={styles.heroNext}>
              Sıradaki temsil · {p.next_performance.local_day} {p.next_performance.local_month} {p.next_performance.local_weekday}, {p.next_performance.local_time}
            </Text>
          )}
        </View>
      </Pressable>
    </Link>
  );
}

const styles = StyleSheet.create({
  brand: { alignItems: "center", paddingBottom: space.lg },
  logo: { width: 150, height: 50 },
  hero: { marginHorizontal: space.lg, aspectRatio: 3 / 4, maxHeight: 560, borderRadius: radius.lg, overflow: "hidden", justifyContent: "flex-end", backgroundColor: colors.surface },
  heroBody: { padding: space.xl },
  heroTitle: { fontFamily: fonts.displayBold, color: colors.cream, fontSize: 36, lineHeight: 42, marginTop: space.sm },
  heroMeta: { fontFamily: fonts.textMedium, color: colors.muted, fontSize: 13, marginTop: 4 },
  heroNext: { fontFamily: fonts.textSemi, color: colors.goldBright, fontSize: 13, marginTop: space.md },
  more: { fontFamily: fonts.textMedium, color: colors.gold, fontSize: 14 },
  article: { marginHorizontal: space.lg, marginBottom: space.md, padding: space.lg, borderRadius: radius.md, backgroundColor: colors.stage, borderWidth: 1, borderColor: colors.line },
  articleTitle: { fontFamily: fonts.display, color: colors.cream, fontSize: 18, marginVertical: 4 },
  aboutLink: {
    marginHorizontal: space.lg,
    marginTop: space.xxl,
    padding: space.lg,
    borderTopWidth: 1,
    borderColor: colors.line,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  aboutText: { fontFamily: fonts.displayItalic, color: colors.cream, fontSize: 18 },
});
