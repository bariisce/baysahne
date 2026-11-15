import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";
import { Alert, Platform } from "react-native";

/** Only these schemes are ever opened. Anything else from content is ignored. */
const SAFE = /^(https:|tel:|mailto:)/i;

export async function openExternal(url: string | null | undefined, opts: { inApp?: boolean } = {}) {
  if (!url || !SAFE.test(url)) return;
  try {
    if (opts.inApp && url.startsWith("https:") && Platform.OS !== "web") {
      await WebBrowser.openBrowserAsync(url, { controlsColor: "#C4973F", toolbarColor: "#0C0A09" });
    } else {
      await Linking.openURL(url);
    }
  } catch {
    Alert.alert("Bağlantı açılamadı", "Lütfen daha sonra tekrar deneyin.");
  }
}

export const telUrl = (phone: string) => `tel:${phone.replace(/[^\d+]/g, "")}`;
export const mailUrl = (email: string) => `mailto:${email}`;

export function youtubeUrl(id: string) {
  return `https://www.youtube.com/watch?v=${encodeURIComponent(id)}`;
}

export function youtubeThumb(id: string) {
  return `https://i.ytimg.com/vi/${encodeURIComponent(id)}/hqdefault.jpg`;
}
