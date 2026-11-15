import { Link } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import type { Performance } from "@/lib/types";
import { colors, fonts, radius, space } from "@/theme";

/**
 * One dated showing. Cancelled performances are clearly struck through and labelled — they are kept
 * visible so audiences learn about the cancellation, but are never presented as available.
 */
export function PerformanceRow({ perf, showProduction = true }: { perf: Performance; showProduction?: boolean }) {
  const cancelled = perf.is_cancelled;
  const label = [
    showProduction ? perf.production?.title : null,
    `${perf.local_date} ${perf.local_weekday}, saat ${perf.local_time}`,
    perf.venue.name,
    cancelled ? "İptal edildi" : null,
    perf.is_rescheduled ? "Tarihi değişti" : null,
  ]
    .filter(Boolean)
    .join(". ");

  const body = (
    <View style={[styles.row, cancelled && styles.rowCancelled]} accessible accessibilityLabel={label}>
      <View style={[styles.date, cancelled && { borderColor: colors.line }]}>
        <Text style={[styles.day, cancelled && styles.struck]}>{perf.local_day}</Text>
        <Text style={styles.month}>{perf.local_month.slice(0, 3).toLocaleUpperCase("tr-TR")}</Text>
      </View>
      <View style={{ flex: 1 }}>
        {showProduction && perf.production && (
          <Text style={[styles.title, cancelled && styles.struck]} numberOfLines={1}>
            {perf.production.title}
          </Text>
        )}
        <Text style={[styles.when, cancelled && styles.struck]}>
          {perf.local_weekday} · {perf.local_time}
        </Text>
        <Text style={styles.venue} numberOfLines={1}>
          {perf.venue.name}
        </Text>
        {cancelled && (
          <Text style={styles.cancelBadge}>
            İPTAL EDİLDİ{perf.cancellation_note ? ` — ${perf.cancellation_note}` : ""}
          </Text>
        )}
        {!cancelled && perf.is_rescheduled && perf.rescheduled_from_local && (
          <Text style={styles.reschedule}>
            Tarihi değişti (önceki: {perf.rescheduled_from_local.local_date}, {perf.rescheduled_from_local.local_time})
          </Text>
        )}
        {perf.public_note && !cancelled && <Text style={styles.note}>{perf.public_note}</Text>}
      </View>
    </View>
  );

  if (!showProduction || !perf.production) return body;
  return (
    <Link href={`/oyun/${perf.production.slug}`} asChild>
      <Pressable accessibilityRole="link">{body}</Pressable>
    </Link>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    gap: space.lg,
    padding: space.md,
    marginHorizontal: space.lg,
    marginBottom: space.sm,
    borderRadius: radius.md,
    backgroundColor: colors.stage,
    borderWidth: 1,
    borderColor: colors.line,
  },
  rowCancelled: { backgroundColor: colors.ink },
  date: { width: 58, alignItems: "center", justifyContent: "center", borderRightWidth: 1, borderColor: colors.gold, paddingRight: space.md },
  day: { fontFamily: fonts.displayBold, color: colors.gold, fontSize: 28, lineHeight: 32 },
  month: { fontFamily: fonts.textSemi, color: colors.muted, fontSize: 11, letterSpacing: 1.4 },
  title: { fontFamily: fonts.display, color: colors.cream, fontSize: 17 },
  when: { fontFamily: fonts.textMedium, color: colors.text, fontSize: 14, marginTop: 2 },
  venue: { fontFamily: fonts.text, color: colors.muted, fontSize: 13, marginTop: 2 },
  struck: { textDecorationLine: "line-through", color: colors.muted },
  cancelBadge: { fontFamily: fonts.textSemi, color: colors.danger, fontSize: 12, marginTop: 6, letterSpacing: 0.4 },
  reschedule: { fontFamily: fonts.textMedium, color: colors.goldBright, fontSize: 12, marginTop: 6 },
  note: { fontFamily: fonts.text, color: colors.text, fontSize: 12, marginTop: 6 },
});
