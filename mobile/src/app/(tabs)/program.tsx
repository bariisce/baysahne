import { Link } from "expo-router";
import { StyleSheet, Text, View } from "react-native";
import { PerformanceRow } from "@/components/performance-row";
import { Screen } from "@/components/screen";
import { Button, Display, EmptyState, ErrorState, Loading } from "@/components/ui";
import { upcomingOnly, useNow } from "@/lib/time";
import type { Page, Performance } from "@/lib/types";
import { useQuery } from "@/lib/use-query";
import { colors, fonts, space } from "@/theme";

/**
 * Upcoming public schedule, grouped by month, in the venue's local time (Europe/Istanbul).
 * A performance leaves the list by itself once it has started, even when the list comes from the cache.
 */
export default function ScheduleScreen() {
  const q = useQuery<Page<Performance>>("/performances?page_size=100", { persist: true });
  const now = useNow();
  const items = upcomingOnly(q.data?.items ?? [], now);
  const groups: { key: string; label: string; items: Performance[] }[] = [];
  for (const p of items) {
    const key = `${p.local_year}-${p.local_month}`;
    const g = groups.at(-1);
    if (g?.key === key) g.items.push(p);
    else groups.push({ key, label: `${p.local_month} ${p.local_year}`, items: [p] });
  }

  return (
    <Screen refreshing={q.refreshing} onRefresh={q.refresh}>
      <View style={{ paddingHorizontal: space.lg, marginBottom: space.md }}>
        <Display>Program</Display>
      </View>
      {q.loading && !q.data && <Loading />}
      {q.error && !q.data && <ErrorState message={q.error.message} onRetry={q.refresh} />}
      {q.data && items.length === 0 && (
        <EmptyState
          title="Yeni tarihler yakında"
          message="Şu anda planlanmış bir temsil yok. Yeni tarihler açıklandığında burada yer alacak; bildirimleri açtıysanız size haber vereceğiz."
          action={
            <Link href="/oyunlar" asChild>
              <Button label="Oyunlara göz at" variant="ghost" onPress={() => {}} />
            </Link>
          }
        />
      )}
      {groups.map((g) => (
        <View key={g.key}>
          <Text style={styles.month} accessibilityRole="header">
            {g.label}
          </Text>
          {g.items.map((p) => (
            <PerformanceRow key={p.id} perf={p} />
          ))}
        </View>
      ))}
    </Screen>
  );
}

const styles = StyleSheet.create({
  month: {
    fontFamily: fonts.textSemi,
    color: colors.gold,
    fontSize: 12,
    letterSpacing: 1.8,
    textTransform: "uppercase",
    paddingHorizontal: space.lg,
    marginTop: space.xl,
    marginBottom: space.sm,
  },
});
