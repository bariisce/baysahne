import { Link } from "expo-router";
import * as Linking from "expo-linking";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { usePush } from "@/components/push-provider";
import { Screen } from "@/components/screen";
import { Body, Button, Display, ErrorState, Eyebrow, Loading, SectionHeader } from "@/components/ui";
import { mailUrl, openExternal, telUrl } from "@/lib/links";
import type { Organization } from "@/lib/types";
import { useQuery } from "@/lib/use-query";
import { colors, fonts, MIN_TOUCH, radius, space } from "@/theme";

export default function AboutScreen() {
  const q = useQuery<Organization>("/organization", { persist: true });
  const o = q.data;
  const a = o?.about;

  return (
    <Screen refreshing={q.refreshing} onRefresh={q.refresh}>
      {q.loading && !o && <Loading />}
      {q.error && !o && <ErrorState message={q.error.message} onRetry={q.refresh} />}
      {o && (
        <>
          <View style={styles.pad}>
            <Eyebrow>Hakkımızda</Eyebrow>
            <Display style={{ marginTop: space.sm }}>{o.short_name ?? o.name}</Display>
            {a?.motto && <Text style={styles.motto}>{a.motto}</Text>}
          </View>

          {a?.story && (
            <View style={styles.pad}>
              {a.story_title && <Text style={styles.h2}>{a.story_title}</Text>}
              {a.story.split(/\n\s*\n/).map((para, i) => (
                <Body key={i} style={{ marginTop: space.md }}>
                  {para.trim()}
                </Body>
              ))}
            </View>
          )}

          {a?.quote && (
            <View style={styles.quote}>
              <Text style={styles.quoteText}>“{a.quote}”</Text>
              {a.quote_author && <Text style={styles.quoteAuthor}>— {a.quote_author}</Text>}
            </View>
          )}

          {!!a?.values?.length && (
            <>
              <SectionHeader title="Bizi biz yapanlar" />
              {a.values.map((v) => (
                <View key={v.title} style={styles.value}>
                  <Text style={styles.valueTitle}>{v.title}</Text>
                  <Body muted>{v.text}</Body>
                </View>
              ))}
            </>
          )}

          {(a?.mission || a?.vision) && (
            <View style={[styles.pad, { gap: space.lg }]}>
              {a.mission && (
                <View>
                  <Eyebrow>Misyon</Eyebrow>
                  <Body style={{ marginTop: space.sm }}>{a.mission}</Body>
                </View>
              )}
              {a.vision && (
                <View>
                  <Eyebrow>Vizyon</Eyebrow>
                  <Body style={{ marginTop: space.sm }}>{a.vision}</Body>
                </View>
              )}
            </View>
          )}

          <SectionHeader title="İletişim" />
          <View style={styles.card}>
            {o.address && <ContactRow label="Adres" value={o.address} />}
            {o.phones.map((p) => (
              <ContactRow key={p} label="Telefon" value={p} onPress={() => openExternal(telUrl(p))} hint="Arama başlatır" />
            ))}
            {o.email && <ContactRow label="E-posta" value={o.email} onPress={() => openExternal(mailUrl(o.email!))} hint="E-posta uygulamasını açar" />}
            {o.website_url && <ContactRow label="Web" value={o.website_url.replace(/^https:\/\/(www\.)?/, "").replace(/\/$/, "")} onPress={() => openExternal(o.website_url, { inApp: true })} />}
          </View>
          <View style={styles.socials}>
            {o.instagram_url && <Social label="Instagram" url={o.instagram_url} />}
            {o.x_url && <Social label="X" url={o.x_url} />}
            {o.youtube_url && <Social label="YouTube" url={o.youtube_url} />}
          </View>

          <NotificationSettings />

          <SectionHeader title="Yasal" />
          <View style={styles.card}>
            <Link href="/yasal" asChild>
              <Pressable accessibilityRole="link" style={styles.contactRow}>
                <Text style={[styles.contactValue, { flex: 1 }]}>Gizlilik ve yasal bilgiler</Text>
                <Text style={styles.chev}>›</Text>
              </Pressable>
            </Link>
          </View>
        </>
      )}
    </Screen>
  );
}

function ContactRow({ label, value, onPress, hint }: { label: string; value: string; onPress?: () => void; hint?: string }) {
  const content = (
    <>
      <View style={{ flex: 1 }}>
        <Text style={styles.contactLabel}>{label}</Text>
        <Text style={[styles.contactValue, onPress && { color: colors.goldBright }]}>{value}</Text>
      </View>
      {onPress && <Text style={styles.chev}>›</Text>}
    </>
  );
  if (!onPress) return <View style={styles.contactRow}>{content}</View>;
  return (
    <Pressable accessibilityRole="link" accessibilityLabel={`${label}: ${value}`} accessibilityHint={hint} onPress={onPress} style={styles.contactRow}>
      {content}
    </Pressable>
  );
}

function Social({ label, url }: { label: string; url: string }) {
  return (
    <Pressable accessibilityRole="link" accessibilityLabel={`${label} hesabı`} onPress={() => openExternal(url)} style={styles.social}>
      <Text style={styles.socialText}>{label}</Text>
    </Pressable>
  );
}

const PUSH_TEXT: Record<string, string> = {
  granted: "Açık. Yeni oyunlar, temsil hatırlatmaları ve program değişiklikleri için bildirim alırsınız.",
  denied: "Kapalı. Açmak için cihaz ayarlarından Bay Sahne bildirimlerine izin verin.",
  undetermined: "Henüz seçim yapılmadı.",
  unsupported: "Bu cihazda bildirimler desteklenmiyor.",
  error: "Bildirim kaydı şu anda yapılamadı. Daha sonra tekrar denenecek.",
  loading: "Kontrol ediliyor…",
};

function NotificationSettings() {
  const { state, enable } = usePush();
  return (
    <>
      <SectionHeader title="Bildirimler" />
      <View style={[styles.card, { padding: space.lg }]}>
        <Body>{PUSH_TEXT[state]}</Body>
        {state === "undetermined" && <Button label="Bildirimleri aç" onPress={() => enable()} style={{ marginTop: space.md, alignSelf: "flex-start" }} />}
        {state === "denied" && <Button label="Ayarları aç" variant="ghost" onPress={() => Linking.openSettings()} style={{ marginTop: space.md, alignSelf: "flex-start" }} />}
        <Body muted style={{ marginTop: space.md, fontSize: 13, lineHeight: 18 }}>
          Bildirim için hesap gerekmez. Yalnızca bildirim anahtarı, platform (iOS/Android), uygulama sürümü ve uygulamanın ürettiği rastgele bir kurulum kimliği saklanır.
        </Body>
      </View>
    </>
  );
}

const styles = StyleSheet.create({
  pad: { paddingHorizontal: space.lg, marginTop: space.xl },
  motto: { fontFamily: fonts.displayItalic, color: colors.gold, fontSize: 20, marginTop: space.sm },
  h2: { fontFamily: fonts.display, color: colors.cream, fontSize: 22 },
  quote: { marginHorizontal: space.lg, marginTop: space.xxl, paddingLeft: space.lg, borderLeftWidth: 2, borderColor: colors.gold },
  quoteText: { fontFamily: fonts.displayItalic, color: colors.cream, fontSize: 22, lineHeight: 30 },
  quoteAuthor: { fontFamily: fonts.textMedium, color: colors.muted, fontSize: 14, marginTop: space.sm },
  value: { marginHorizontal: space.lg, marginBottom: space.md, padding: space.lg, borderRadius: radius.md, backgroundColor: colors.stage, borderWidth: 1, borderColor: colors.line },
  valueTitle: { fontFamily: fonts.display, color: colors.gold, fontSize: 18, marginBottom: 4 },
  card: { marginHorizontal: space.lg, borderRadius: radius.md, backgroundColor: colors.stage, borderWidth: 1, borderColor: colors.line, overflow: "hidden" },
  contactRow: { minHeight: MIN_TOUCH + 12, flexDirection: "row", alignItems: "center", paddingHorizontal: space.lg, paddingVertical: space.md, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: colors.line },
  contactLabel: { fontFamily: fonts.textSemi, color: colors.muted, fontSize: 11, letterSpacing: 1.2, textTransform: "uppercase" },
  contactValue: { fontFamily: fonts.text, color: colors.text, fontSize: 15, marginTop: 2 },
  chev: { color: colors.muted, fontSize: 24, marginLeft: space.sm },
  socials: { flexDirection: "row", flexWrap: "wrap", gap: space.sm, paddingHorizontal: space.lg, marginTop: space.md },
  social: { minHeight: MIN_TOUCH, paddingHorizontal: space.lg, borderRadius: 999, borderWidth: 1, borderColor: colors.gold, justifyContent: "center" },
  socialText: { fontFamily: fonts.textSemi, color: colors.gold, fontSize: 14 },
});
