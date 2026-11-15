import { Image } from "expo-image";
import { useLocalSearchParams } from "expo-router";
import { StyleSheet, View } from "react-native";
import { Screen } from "@/components/screen";
import { Body, Display, EmptyState, ErrorState, Eyebrow, Loading } from "@/components/ui";
import type { ArticleSummary } from "@/lib/types";
import { useQuery } from "@/lib/use-query";
import { radius, space } from "@/theme";

export default function ArticleScreen() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const q = useQuery<ArticleSummary>(slug ? `/articles/${encodeURIComponent(slug)}` : null);
  const a = q.data;
  return (
    <Screen refreshing={q.refreshing} onRefresh={q.refresh} topInset={false}>
      {q.loading && !a && <Loading />}
      {q.error && !a && (q.error.status === 404 ? <EmptyState title="Duyuru bulunamadı" /> : <ErrorState message={q.error.message} onRetry={q.refresh} />)}
      {a && (
        <View style={{ padding: space.lg }}>
          {a.image && (
            <Image source={{ uri: a.image.lg?.url ?? a.image.url }} style={styles.image} contentFit="cover" cachePolicy="memory-disk" accessibilityLabel={a.image.alt ?? ""} />
          )}
          {a.published_local && <Eyebrow>{a.published_local.local_date}</Eyebrow>}
          <Display style={{ marginTop: space.sm }}>{a.title}</Display>
          {(a.body ?? "").split(/\n\s*\n/).map((para, i) => (
            <Body key={i} style={{ marginTop: space.md }}>
              {para.trim()}
            </Body>
          ))}
        </View>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({ image: { width: "100%", aspectRatio: 16 / 9, borderRadius: radius.md, marginBottom: space.lg } });
