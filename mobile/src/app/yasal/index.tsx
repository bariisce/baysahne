import { Link } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Screen } from "@/components/screen";
import { Body, EmptyState, ErrorState, Loading } from "@/components/ui";
import { config } from "@/lib/config";
import { openExternal } from "@/lib/links";
import type { LegalDoc } from "@/lib/types";
import { useQuery } from "@/lib/use-query";
import { colors, fonts, MIN_TOUCH, space } from "@/theme";

export default function LegalIndex() {
  const q = useQuery<{ items: LegalDoc[] }>("/legal");
  return (
    <Screen refreshing={q.refreshing} onRefresh={q.refresh} topInset={false}>
      {q.loading && !q.data && <Loading />}
      {q.error && !q.data && <ErrorState message={q.error.message} onRetry={q.refresh} />}
      {q.data && q.data.items.length === 0 && (
        <EmptyState
          title="Yasal metinler hazırlanıyor"
          message="Bu uygulamaya ilişkin gizlilik ve kullanım metinleri kurum tarafından gözden geçirildikten sonra burada yayınlanacak. Sorularınız için baysahne@gmail.com adresine yazabilirsiniz."
        />
      )}
      {q.data?.items.map((d) => (
        <Link key={d.slug} href={`/yasal/${d.slug}`} asChild>
          <Pressable accessibilityRole="link" style={styles.row}>
            <Text style={styles.title}>{d.title}</Text>
            <Text style={styles.chev}>›</Text>
          </Pressable>
        </Link>
      ))}
      {config.privacyPolicyUrl && q.data && q.data.items.length > 0 && (
        <View style={{ padding: space.lg }}>
          <Pressable accessibilityRole="link" onPress={() => openExternal(config.privacyPolicyUrl, { inApp: true })}>
            <Body muted>Metinlerin web sürümü</Body>
          </Pressable>
        </View>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { minHeight: MIN_TOUCH + 12, flexDirection: "row", alignItems: "center", paddingHorizontal: space.lg, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: colors.line },
  title: { flex: 1, fontFamily: fonts.textMedium, color: colors.cream, fontSize: 16 },
  chev: { color: colors.muted, fontSize: 24 },
});
