import * as Notifications from "expo-notifications";
import { router } from "expo-router";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { AppState, Platform } from "react-native";
import {
  configureForegroundPresentation,
  isNewDeviceToken,
  isPushSupported,
  routeForNotificationData,
  syncPushRegistration,
  type PushState,
} from "@/lib/push";

type Ctx = { state: PushState | "loading"; enable: () => Promise<PushState> };
const PushContext = createContext<Ctx>({ state: "unsupported", enable: async () => "unsupported" });

export const usePush = () => useContext(PushContext);

export function PushProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<PushState | "loading">("loading");

  const sync = useCallback(async (prompt: boolean) => {
    const s = await syncPushRegistration({ prompt });
    setState(s);
    return s;
  }, []);

  useEffect(() => {
    configureForegroundPresentation();
    syncPushRegistration().then(setState);
    if (Platform.OS === "web") return;

    // Real token rotation → re-register; returning to the app → pick up permission changes from settings.
    // Only where remote push exists: in Expo Go on Android this call throws and would take the app down.
    const tokenSub = isPushSupported()
      ? Notifications.addPushTokenListener((t) => {
          if (typeof t.data === "string" && isNewDeviceToken(t.data)) void sync(false);
        })
      : null;
    const appSub = AppState.addEventListener("change", (s) => s === "active" && sync(false));
    const openSub = Notifications.addNotificationResponseReceivedListener((r) => {
      const route = routeForNotificationData(r.notification.request.content.data);
      if (route) router.push(route as never);
    });
    // Cold start from a notification tap.
    const last = Notifications.getLastNotificationResponse();
    const initial = last ? routeForNotificationData(last.notification.request.content.data) : null;
    if (initial) setTimeout(() => router.push(initial as never), 0);

    return () => {
      tokenSub?.remove();
      appSub.remove();
      openSub.remove();
    };
  }, [sync]);

  return <PushContext.Provider value={{ state, enable: () => sync(true) }}>{children}</PushContext.Provider>;
}
