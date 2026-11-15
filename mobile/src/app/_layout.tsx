import { Inter_400Regular, Inter_500Medium, Inter_600SemiBold } from "@expo-google-fonts/inter";
import {
  PlayfairDisplay_400Regular_Italic,
  PlayfairDisplay_600SemiBold,
  PlayfairDisplay_700Bold,
} from "@expo-google-fonts/playfair-display";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { DarkTheme, ThemeProvider } from "expo-router/react-navigation";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { PushProvider } from "@/components/push-provider";
import { colors, fonts } from "@/theme";

SplashScreen.preventAutoHideAsync().catch(() => {});

const theme = {
  ...DarkTheme,
  colors: { ...DarkTheme.colors, background: colors.ink, card: colors.ink, text: colors.cream, primary: colors.gold, border: colors.line },
};

export default function RootLayout() {
  const [loaded, error] = useFonts({
    PlayfairDisplay_600SemiBold,
    PlayfairDisplay_700Bold,
    PlayfairDisplay_400Regular_Italic,
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
  });

  useEffect(() => {
    // Font failure is not fatal: system fonts are used instead.
    if (loaded || error) SplashScreen.hideAsync().catch(() => {});
  }, [loaded, error]);

  if (!loaded && !error) return null;

  return (
    <ThemeProvider value={theme}>
      <PushProvider>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            contentStyle: { backgroundColor: colors.ink },
            headerStyle: { backgroundColor: colors.ink },
            headerTintColor: colors.gold,
            headerTitleStyle: { fontFamily: fonts.display, color: colors.cream },
            headerShadowVisible: false,
            headerBackButtonDisplayMode: "minimal",
          }}
        >
          <Stack.Screen name="(tabs)" options={{ headerShown: false, title: "Bay Sahne" }} />
          {/* The poster runs under the header; the shared ink headerStyle would otherwise paint over its top. */}
          <Stack.Screen
            name="oyun/[slug]"
            options={{ headerTransparent: true, headerStyle: { backgroundColor: "transparent" }, title: "" }}
          />
          <Stack.Screen name="duyuru/[slug]" options={{ title: "Duyuru" }} />
          <Stack.Screen name="yasal/index" options={{ title: "Yasal bilgiler" }} />
          <Stack.Screen name="yasal/[slug]" options={{ title: "" }} />
        </Stack>
      </PushProvider>
    </ThemeProvider>
  );
}
