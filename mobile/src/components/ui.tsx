import type { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type TextProps,
  type TextStyle,
  type ViewStyle,
} from "react-native";
import { colors, fonts, MIN_TOUCH, radius, space } from "@/theme";

export function Display({ style, ...p }: TextProps & { style?: StyleProp<TextStyle> }) {
  return <Text accessibilityRole="header" {...p} style={[styles.display, style]} />;
}

export function Body({ style, muted, ...p }: TextProps & { muted?: boolean; style?: StyleProp<TextStyle> }) {
  return <Text {...p} style={[styles.body, muted && { color: colors.muted }, style]} />;
}

export function Eyebrow({ children, style }: { children: ReactNode; style?: StyleProp<TextStyle> }) {
  return <Text style={[styles.eyebrow, style]}>{children}</Text>;
}

export function SectionHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <View style={styles.sectionHeader}>
      <Text accessibilityRole="header" style={styles.sectionTitle}>
        {title}
      </Text>
      {action}
    </View>
  );
}

export function Button({
  label,
  onPress,
  variant = "primary",
  accessibilityHint,
  style,
}: {
  label: string;
  onPress: () => void;
  variant?: "primary" | "ghost";
  accessibilityHint?: string;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityHint={accessibilityHint}
      onPress={onPress}
      style={({ pressed }) => [styles.button, variant === "ghost" && styles.buttonGhost, pressed && { opacity: 0.75 }, style]}
    >
      <Text style={[styles.buttonText, variant === "ghost" && { color: colors.gold }]}>{label}</Text>
    </Pressable>
  );
}

export function Chip({ label, selected, onPress }: { label: string; selected?: boolean; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: !!selected }}
      onPress={onPress}
      hitSlop={6}
      style={[styles.chip, selected && styles.chipSelected]}
    >
      <Text style={[styles.chipText, selected && { color: colors.ink }]}>{label}</Text>
    </Pressable>
  );
}

export function Loading({ label = "Yükleniyor…" }: { label?: string }) {
  return (
    <View style={styles.center} accessibilityLiveRegion="polite" accessibilityLabel={label}>
      <ActivityIndicator color={colors.gold} />
      <Body muted style={{ marginTop: space.md }}>
        {label}
      </Body>
    </View>
  );
}

export function EmptyState({ title, message, action }: { title: string; message?: string; action?: ReactNode }) {
  return (
    <View style={[styles.center, styles.emptyBox]}>
      <Text style={styles.emptyTitle}>{title}</Text>
      {message && (
        <Body muted style={{ textAlign: "center", marginTop: space.sm }}>
          {message}
        </Body>
      )}
      {action && <View style={{ marginTop: space.lg }}>{action}</View>}
    </View>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <View style={[styles.center, styles.emptyBox]} accessibilityLiveRegion="polite">
      <Text style={styles.emptyTitle}>Bir sorun oluştu</Text>
      <Body muted style={{ textAlign: "center", marginTop: space.sm }}>
        {message}
      </Body>
      <Button label="Tekrar dene" onPress={onRetry} style={{ marginTop: space.lg }} />
    </View>
  );
}

export const styles = StyleSheet.create({
  display: { fontFamily: fonts.display, color: colors.cream, fontSize: 30, lineHeight: 36 },
  body: { fontFamily: fonts.text, color: colors.text, fontSize: 15, lineHeight: 23 },
  eyebrow: { fontFamily: fonts.textSemi, color: colors.gold, fontSize: 11, letterSpacing: 1.6, textTransform: "uppercase" },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
    paddingHorizontal: space.lg,
    marginTop: space.xxl,
    marginBottom: space.md,
  },
  sectionTitle: { fontFamily: fonts.display, color: colors.cream, fontSize: 22 },
  button: {
    minHeight: MIN_TOUCH,
    paddingHorizontal: space.xl,
    borderRadius: 999,
    backgroundColor: colors.gold,
    alignItems: "center",
    justifyContent: "center",
  },
  buttonGhost: { backgroundColor: "transparent", borderWidth: 1, borderColor: colors.gold },
  buttonText: { fontFamily: fonts.textSemi, color: colors.ink, fontSize: 15 },
  chip: {
    minHeight: 36,
    paddingHorizontal: space.lg,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.line,
    justifyContent: "center",
    marginRight: space.sm,
  },
  chipSelected: { backgroundColor: colors.gold, borderColor: colors.gold },
  chipText: { fontFamily: fonts.textMedium, color: colors.text, fontSize: 14 },
  center: { alignItems: "center", justifyContent: "center", padding: space.xl },
  emptyBox: { marginHorizontal: space.lg, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.stage },
  emptyTitle: { fontFamily: fonts.display, color: colors.cream, fontSize: 19, textAlign: "center" },
});
