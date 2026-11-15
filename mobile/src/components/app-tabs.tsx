import { NativeTabs } from "expo-router/native-tabs";
import { colors } from "@/theme";

/** Platform-native tab bar (UITabBar on iOS, Material 3 navigation bar on Android). */
export function AppTabs() {
  return (
    <NativeTabs tintColor={colors.gold} backgroundColor={colors.ink} iconColor={colors.muted}>
      <NativeTabs.Trigger name="index">
        <NativeTabs.Trigger.Icon sf={{ default: "theatermasks", selected: "theatermasks.fill" }} md="theater_comedy" />
        <NativeTabs.Trigger.Label>Ana Sayfa</NativeTabs.Trigger.Label>
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="oyunlar">
        <NativeTabs.Trigger.Icon sf={{ default: "square.grid.2x2", selected: "square.grid.2x2.fill" }} md="grid_view" />
        <NativeTabs.Trigger.Label>Oyunlar</NativeTabs.Trigger.Label>
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="program">
        <NativeTabs.Trigger.Icon sf="calendar" md="calendar_month" />
        <NativeTabs.Trigger.Label>Program</NativeTabs.Trigger.Label>
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="hakkimizda">
        <NativeTabs.Trigger.Icon sf={{ default: "info.circle", selected: "info.circle.fill" }} md="info" />
        <NativeTabs.Trigger.Label>Hakkımızda</NativeTabs.Trigger.Label>
      </NativeTabs.Trigger>
    </NativeTabs>
  );
}
