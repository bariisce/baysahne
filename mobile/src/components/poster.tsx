import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";
import type { Img } from "@/lib/types";
import { colors, fonts, radius } from "@/theme";

/**
 * Production poster with disk/memory caching (expo-image) and size-appropriate variants.
 * When no official poster exists we show a typographic card with the title — never invented artwork.
 */
export function Poster({
  image,
  title,
  size = "sm",
  style,
  rounded = true,
}: {
  image: Img | null;
  title: string;
  size?: "sm" | "lg";
  style?: StyleProp<ViewStyle>;
  rounded?: boolean;
}) {
  const src = image ? (size === "lg" ? image.lg?.url ?? image.url : image.sm?.url ?? image.url) : null;
  return (
    <View style={[styles.box, rounded && { borderRadius: radius.md }, style]}>
      {src ? (
        <Image
          source={{ uri: src }}
          style={StyleSheet.absoluteFill}
          contentFit="cover"
          transition={200}
          cachePolicy="memory-disk"
          accessibilityLabel={`${title} afişi`}
          accessible
        />
      ) : (
        <LinearGradient colors={[colors.surfaceRaised, colors.stage]} style={[StyleSheet.absoluteFill, styles.placeholder]}>
          <View style={styles.rule} />
          <Text style={styles.placeholderTitle} numberOfLines={4} accessibilityLabel={`${title} — afiş yok`}>
            {title}
          </Text>
          <View style={styles.rule} />
        </LinearGradient>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  box: { aspectRatio: 3 / 4, overflow: "hidden", backgroundColor: colors.surface },
  placeholder: { alignItems: "center", justifyContent: "center", padding: 14 },
  placeholderTitle: { fontFamily: fonts.displayItalic, color: colors.cream, fontSize: 20, textAlign: "center", marginVertical: 10 },
  rule: { width: 28, height: 1, backgroundColor: colors.gold },
});
