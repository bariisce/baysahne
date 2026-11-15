import { Link } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import type { ProductionCard as Card } from "@/lib/types";
import { colors, fonts, radius, space } from "@/theme";
import { Poster } from "./poster";

function a11yLabel(p: Card) {
  const parts = [p.title, p.genres.join(", ")];
  if (p.next_performance) parts.push(`Sıradaki temsil ${p.next_performance.local_date}, saat ${p.next_performance.local_time}`);
  return parts.filter(Boolean).join(". ");
}

/** Tall poster tile for horizontal carousels. */
export function PosterTile({ p, width = 150 }: { p: Card; width?: number }) {
  return (
    <Link href={`/oyun/${p.slug}`} asChild>
      <Pressable accessibilityRole="link" accessibilityLabel={a11yLabel(p)} style={{ width, marginRight: space.md }}>
        <Poster image={p.poster} title={p.title} />
        <Text style={styles.tileTitle} numberOfLines={2}>
          {p.title}
        </Text>
        {p.next_performance ? (
          <Text style={styles.tileMeta}>
            {p.next_performance.local_day} {p.next_performance.local_month} · {p.next_performance.local_time}
          </Text>
        ) : (
          p.genres.length > 0 && <Text style={styles.tileMeta}>{p.genres.join(" · ")}</Text>
        )}
      </Pressable>
    </Link>
  );
}

/** Row card for the catalogue list. */
export function ProductionRow({ p }: { p: Card }) {
  return (
    <Link href={`/oyun/${p.slug}`} asChild>
      <Pressable accessibilityRole="link" accessibilityLabel={a11yLabel(p)} style={styles.row}>
        <Poster image={p.poster} title={p.title} style={{ width: 96 }} />
        <View style={styles.rowBody}>
          <View style={styles.badges}>
            {p.genres.map((g) => (
              <Text key={g} style={styles.genre}>
                {g}
              </Text>
            ))}
            {p.on_stage && <Text style={[styles.genre, styles.onStage]}>Sahnede</Text>}
          </View>
          <Text style={styles.rowTitle} numberOfLines={2}>
            {p.title}
          </Text>
          {(p.author || p.duration_label) && (
            <Text style={styles.rowMeta} numberOfLines={1}>
              {[p.author, p.duration_label].filter(Boolean).join(" · ")}
            </Text>
          )}
          {p.excerpt && (
            <Text style={styles.excerpt} numberOfLines={2}>
              {p.excerpt}
            </Text>
          )}
          {p.next_performance && (
            <Text style={styles.next}>
              Sıradaki temsil: {p.next_performance.local_day} {p.next_performance.local_month}, {p.next_performance.local_time}
            </Text>
          )}
        </View>
      </Pressable>
    </Link>
  );
}

const styles = StyleSheet.create({
  tileTitle: { fontFamily: fonts.display, color: colors.cream, fontSize: 16, marginTop: space.sm, lineHeight: 21 },
  tileMeta: { fontFamily: fonts.text, color: colors.muted, fontSize: 12, marginTop: 2 },
  row: { flexDirection: "row", paddingHorizontal: space.lg, paddingVertical: space.md, gap: space.lg, borderRadius: radius.md },
  rowBody: { flex: 1, justifyContent: "center" },
  badges: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginBottom: 6 },
  genre: { fontFamily: fonts.textSemi, color: colors.gold, fontSize: 11, letterSpacing: 1.2, textTransform: "uppercase" },
  onStage: { color: colors.success },
  rowTitle: { fontFamily: fonts.display, color: colors.cream, fontSize: 20, lineHeight: 25 },
  rowMeta: { fontFamily: fonts.text, color: colors.muted, fontSize: 13, marginTop: 4 },
  excerpt: { fontFamily: fonts.text, color: colors.text, fontSize: 14, lineHeight: 20, marginTop: 6 },
  next: { fontFamily: fonts.textMedium, color: colors.goldBright, fontSize: 13, marginTop: 8 },
});
