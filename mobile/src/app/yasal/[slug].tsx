import { Stack, useLocalSearchParams } from "expo-router";
import { View } from "react-native";
import { Screen } from "@/components/screen";
import { Body, Display, EmptyState, ErrorState, Loading } from "@/components/ui";
import type { LegalDoc } from "@/lib/types";
import { useQuery } from "@/lib/use-query";
import { space } from "@/theme";

export default function LegalDocScreen() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const q = useQuery<LegalDoc>(slug ? `/legal/${encodeURIComponent(slug)}` : null);
  const d = q.data;
  return (
    <Screen refreshing={q.refreshing} onRefresh={q.refresh} topInset={false}>
      <Stack.Screen options={{ title: d?.title ?? "" }} />
      {q.loading && !d && <Loading />}
      {q.error && !d && (q.error.status === 404 ? <EmptyState title="Belge bulunamadı" /> : <ErrorState message={q.error.message} onRetry={q.refresh} />)}
      {d && (
        <View style={{ padding: space.lg }}>
          <Display style={{ fontSize: 24, lineHeight: 30 }}>{d.title}</Display>
          {(d.body ?? "").split(/\n\s*\n/).map((p, i) => (
            <Body key={i} style={{ marginTop: space.md }}>
              {p.trim()}
            </Body>
          ))}
        </View>
      )}
    </Screen>
  );
}
