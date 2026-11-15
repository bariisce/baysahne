import { Tabs } from "expo-router";
import { colors, fonts } from "@/theme";

/** Web fallback (used for browser previews only; the store apps use native tabs). */
export function AppTabs() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.gold,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: { backgroundColor: colors.ink, borderTopColor: colors.line },
        tabBarLabelStyle: { fontFamily: fonts.textMedium, fontSize: 12 },
        tabBarIconStyle: { display: "none" },
        sceneStyle: { backgroundColor: colors.ink },
      }}
    >
      <Tabs.Screen name="index" options={{ title: "Ana Sayfa" }} />
      <Tabs.Screen name="oyunlar" options={{ title: "Oyunlar" }} />
      <Tabs.Screen name="program" options={{ title: "Program" }} />
      <Tabs.Screen name="hakkimizda" options={{ title: "Hakkımızda" }} />
    </Tabs>
  );
}
