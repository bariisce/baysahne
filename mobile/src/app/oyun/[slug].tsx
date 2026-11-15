import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { router, Stack, useLocalSearchParams } from "expo-router";
import { useMemo, useState } from "react";
import { FlatList, Modal, Pressable, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { PerformanceRow } from "@/components/performance-row";
import { Poster } from "@/components/poster";
import { Screen } from "@/components/screen";
import { Body, Button, EmptyState, ErrorState, Eyebrow, Loading, SectionHeader } from "@/components/ui";
import { openExternal, youtubeThumb, youtubeUrl } from "@/lib/links";
import { upcomingOnly, useNow } from "@/lib/time";
import type { ProductionDetail } from "@/lib/types";
import { useQuery } from "@/lib/use-query";
import { colors, fonts, MIN_TOUCH, radius, space } from "@/theme";

export default function ProductionScreen() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const q = useQuery<ProductionDetail>(slug ? `/productions/${encodeURIComponent(slug)}` : null, { persist: true });
  const now = useNow();
  // Cached content can be days old: performances that have already started are not listed.
  const p = useMemo(() => q.data && { ...q.data, performances: upcomingOnly(q.data.performances, now) }, [q.data, now]);
  const [viewer, setViewer] = useState<number | null>(null);
  const [expanded, setExpanded] = useState(false);
  const insets = useSafeAreaInsets();

  if (q.loading && !p) return <View style={styles.fill}><Loading /></View>;
  if (q.error && !p)
    return (
      <View style={[styles.fill, { paddingTop: insets.top + 60 }]}>
        {q.error.status === 404 ? (
          <EmptyState
            title="Oyun bulunamadı"
            message="Bu oyun artık yayında olmayabilir."
            action={<Button label="Ana sayfaya dön" variant="ghost" onPress={() => router.replace("/")} />}
          />
        ) : (
          <ErrorState message={q.error.message} onRetry={q.refresh} />
        )}
      </View>
    );
  if (!p) return null;

  const upcoming = p.performances.filter((x) => !x.is_cancelled);
  const longText = (p.description?.length ?? 0) > 420;
  const venues = Array.from(new Map(p.performances.map((x) => [x.venue.id, x.venue])).values());

  return (
    <>
      <Stack.Screen options={{ title: "" }} />
      <Screen refreshing={q.refreshing} onRefresh={q.refresh} topInset={false}>
        <View>
          <Poster image={p.poster} title={p.title} size="lg" rounded={false} style={{ width: "100%" }} />
          <LinearGradient colors={["rgba(12,10,9,0.55)", "transparent", "transparent", colors.ink]} locations={[0, 0.2, 0.6, 1]} style={StyleSheet.absoluteFill} />
        </View>

        <View style={styles.head}>
          <View style={styles.badges}>
            {p.genres.map((g) => <Eyebrow key={g}>{g}</Eyebrow>)}
            {p.on_stage && <Eyebrow style={{ color: colors.success }}>Sahnede</Eyebrow>}
          </View>
          <Text style={styles.title} accessibilityRole="header">
            {p.title}
          </Text>
          {p.duration_label && <Text style={styles.meta}>{p.duration_label}</Text>}
        </View>

        {p.description && (
          <View style={styles.pad}>
            {(p.short_description && p.short_description !== p.description) && <Text style={styles.lede}>{p.short_description}</Text>}
            <Body numberOfLines={longText && !expanded ? 8 : undefined}>{p.description}</Body>
            {longText && (
              <Pressable accessibilityRole="button" onPress={() => setExpanded(!expanded)} style={styles.more}>
                <Text style={styles.moreText}>{expanded ? "Daha az göster" : "Devamını oku"}</Text>
              </Pressable>
            )}
          </View>
        )}

        <SectionHeader title="Temsiller" />
        {p.performances.length === 0 ? (
          <EmptyState title="Planlanmış temsil yok" message="Bu oyun için yeni tarihler açıklandığında burada görünecek." />
        ) : (
          <>
            {upcoming.length === 0 && <Body muted style={styles.padText}>Yaklaşan tüm temsiller iptal edildi.</Body>}
            {p.performances.map((x) => <PerformanceRow key={x.id} perf={x} showProduction={false} />)}
          </>
        )}
        {venues.map((v) => (
          <View key={v.id} style={styles.venue}>
            <Text style={styles.venueName}>{v.name}</Text>
            {(v.address || v.city) && <Body muted>{[v.address, v.district, v.city].filter(Boolean).join(", ")}</Body>}
            {v.public_info && <Body muted style={{ marginTop: 4 }}>{v.public_info}</Body>}
            {v.maps_url && (
              <Pressable accessibilityRole="link" onPress={() => openExternal(v.maps_url)} style={styles.more}>
                <Text style={styles.moreText}>Haritada aç</Text>
              </Pressable>
            )}
          </View>
        ))}

        {p.credits.length > 0 && (
          <>
            <SectionHeader title="Künye" />
            <View style={styles.credits}>
              {p.credits.map((c, i) => (
                <View key={i} style={styles.creditRow} accessible accessibilityLabel={`${c.label}: ${c.name}`}>
                  <Text style={styles.creditLabel}>{c.label}</Text>
                  <Text style={styles.creditName}>{c.name}</Text>
                </View>
              ))}
            </View>
          </>
        )}

        {p.gallery.length > 0 && (
          <>
            <SectionHeader title="Oyundan kareler" />
            <FlatList
              horizontal
              data={p.gallery}
              keyExtractor={(g) => g.id}
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={{ paddingHorizontal: space.lg, gap: space.sm }}
              renderItem={({ item, index }) => (
                <Pressable accessibilityRole="imagebutton" accessibilityLabel={item.caption ?? `${p.title}, kare ${index + 1} / ${p.gallery.length}`} onPress={() => setViewer(index)}>
                  <Image
                    source={{ uri: item.sm?.url ?? item.url }}
                    style={{ width: 220, aspectRatio: (item.sm?.width ?? 4) / (item.sm?.height ?? 3), borderRadius: radius.md, backgroundColor: colors.surface }}
                    contentFit="cover"
                    cachePolicy="memory-disk"
                    transition={150}
                  />
                </Pressable>
              )}
            />
          </>
        )}

        {p.videos.length > 0 && (
          <>
            <SectionHeader title="Video" />
            {p.videos.map((v) => (
              <Pressable
                key={v.url}
                accessibilityRole="link"
                accessibilityLabel={`${v.title ?? "Video"} — YouTube'da açılır`}
                onPress={() => openExternal(v.youtube_id ? youtubeUrl(v.youtube_id) : v.url)}
                style={styles.video}
              >
                {v.youtube_id && <Image source={{ uri: youtubeThumb(v.youtube_id) }} style={StyleSheet.absoluteFill} contentFit="cover" />}
                <View style={styles.videoShade} />
                <View style={styles.play}>
                  <Text style={styles.playIcon}>▶</Text>
                </View>
                <Text style={styles.videoTitle}>{v.title ?? "Videoyu izle"}</Text>
              </Pressable>
            ))}
          </>
        )}
      </Screen>

      <Gallery images={p.gallery} index={viewer} onClose={() => setViewer(null)} title={p.title} />
    </>
  );
}

function Gallery({ images, index, onClose, title }: { images: ProductionDetail["gallery"]; index: number | null; onClose: () => void; title: string }) {
  const { width, height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={index !== null} animationType="fade" onRequestClose={onClose} transparent={false} supportedOrientations={["portrait", "landscape"]}>
      <View style={{ flex: 1, backgroundColor: "#000" }}>
        {index !== null && (
          <FlatList
            horizontal
            pagingEnabled
            data={images}
            initialScrollIndex={index}
            getItemLayout={(_, i) => ({ length: width, offset: width * i, index: i })}
            keyExtractor={(g) => g.id}
            renderItem={({ item, index: i }) => (
              <Image
                source={{ uri: item.lg?.url ?? item.url }}
                placeholder={{ uri: item.sm?.url }}
                style={{ width, height }}
                contentFit="contain"
                cachePolicy="memory-disk"
                accessibilityLabel={item.caption ?? `${title}, kare ${i + 1}`}
              />
            )}
          />
        )}
        <View style={{ position: "absolute", top: insets.top + space.sm, right: space.lg }}>
          <Button label="Kapat" variant="ghost" onPress={onClose} />
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, backgroundColor: colors.ink, justifyContent: "center" },
  head: { paddingHorizontal: space.lg, marginTop: -space.xxl },
  badges: { flexDirection: "row", flexWrap: "wrap", gap: space.md },
  title: { fontFamily: fonts.displayBold, color: colors.cream, fontSize: 38, lineHeight: 44, marginTop: space.sm },
  meta: { fontFamily: fonts.textMedium, color: colors.muted, fontSize: 14, marginTop: space.xs },
  pad: { paddingHorizontal: space.lg, marginTop: space.xl },
  padText: { paddingHorizontal: space.lg, marginBottom: space.sm },
  lede: { fontFamily: fonts.displayItalic, color: colors.cream, fontSize: 18, lineHeight: 26, marginBottom: space.md },
  more: { minHeight: MIN_TOUCH, justifyContent: "center", alignSelf: "flex-start" },
  moreText: { fontFamily: fonts.textSemi, color: colors.gold, fontSize: 14 },
  venue: { marginHorizontal: space.lg, marginTop: space.sm, paddingTop: space.md },
  venueName: { fontFamily: fonts.textSemi, color: colors.cream, fontSize: 15 },
  credits: { marginHorizontal: space.lg, borderTopWidth: 1, borderColor: colors.line },
  creditRow: { flexDirection: "row", paddingVertical: space.md, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: colors.line, gap: space.lg },
  creditLabel: { width: 140, fontFamily: fonts.textMedium, color: colors.muted, fontSize: 14 },
  creditName: { flex: 1, fontFamily: fonts.textSemi, color: colors.cream, fontSize: 15 },
  video: { marginHorizontal: space.lg, aspectRatio: 16 / 9, borderRadius: radius.md, overflow: "hidden", backgroundColor: colors.surface, justifyContent: "center", alignItems: "center" },
  videoShade: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(0,0,0,0.35)" },
  play: { width: 64, height: 64, borderRadius: 32, backgroundColor: colors.gold, alignItems: "center", justifyContent: "center" },
  playIcon: { color: colors.ink, fontSize: 24, marginLeft: 4 },
  videoTitle: { position: "absolute", left: space.lg, bottom: space.md, fontFamily: fonts.textSemi, color: "#fff", fontSize: 14 },
});
