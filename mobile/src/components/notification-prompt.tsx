import AsyncStorage from "@react-native-async-storage/async-storage";
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, fonts, radius, space } from "@/theme";
import { usePush } from "./push-provider";
import { Body, Button } from "./ui";

const DISMISS_KEY = "bs-push-prompt-dismissed";

/**
 * Soft opt-in card. The OS permission dialog is only shown after the user taps "Bildirimleri aç",
 * so the system prompt (which can be shown only once on iOS) appears with context.
 */
export function NotificationPrompt() {
  const { state, enable } = usePush();
  const [dismissed, setDismissed] = useState<boolean | null>(null);

  useEffect(() => {
    AsyncStorage.getItem(DISMISS_KEY).then((v) => setDismissed(v === "1")).catch(() => setDismissed(false));
  }, []);

  if (state !== "undetermined" || dismissed !== false) return null;
  return (
    <View style={styles.card}>
      <Text style={styles.title}>Perdeyi kaçırmayın</Text>
      <Body muted style={{ marginTop: 4 }}>
        Yeni oyunlar, temsil hatırlatmaları ve program değişiklikleri için bildirim alın. Hesap gerekmez.
      </Body>
      <View style={styles.actions}>
        <Button label="Bildirimleri aç" onPress={() => enable()} />
        <Pressable
          accessibilityRole="button"
          hitSlop={8}
          onPress={() => {
            setDismissed(true);
            AsyncStorage.setItem(DISMISS_KEY, "1").catch(() => {});
          }}
          style={{ padding: space.md }}
        >
          <Text style={styles.later}>Şimdi değil</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { margin: space.lg, marginTop: space.xl, padding: space.lg, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  title: { fontFamily: fonts.display, color: colors.cream, fontSize: 19 },
  actions: { flexDirection: "row", alignItems: "center", marginTop: space.lg, gap: space.sm },
  later: { fontFamily: fonts.textMedium, color: colors.muted, fontSize: 14 },
});
