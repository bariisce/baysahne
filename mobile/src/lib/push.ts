/**
 * Push registration.
 *
 * - No account is needed. The app identifies itself with a random installation id that is generated
 *   locally (not a hardware identifier) and kept in app storage.
 * - Nothing is sent to the server until the user has decided. Granting permission registers the Expo
 *   push token. Revoking it later (in system settings) deactivates the installation on the next launch
 *   or foreground.
 * - The operating system's permission state is always respected; we never re-prompt after a denial.
 * - Registration is idempotent and quiet: concurrent syncs share one round trip, an unchanged token is
 *   not re-sent (only refreshed once a day), and the token event that iOS emits for our *own*
 *   token request is ignored — reacting to it re-requested the token in an endless loop.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";
import { isRunningInExpoGo } from "expo";
import * as Crypto from "expo-crypto";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import { api } from "./api";
import { config } from "./config";

export type PushState = "unsupported" | "undetermined" | "denied" | "granted" | "error";

const INSTALLATION_KEY = "bs-installation-id";
/** JSON `{ token, appVersion, at }` of the last successful opt-in registration (legacy value: "1"). */
const REGISTERED_KEY = "bs-push-registered";
/** Re-send an unchanged registration at most this often, so `last_seen_at` stays current server-side. */
const REFRESH_MS = 24 * 60 * 60 * 1000;

type Registration = { token: string; appVersion: string; at: number };

let inFlight: Promise<PushState> | null = null;
let lastDeviceToken: string | null = null;

export async function getInstallationId(): Promise<string> {
  const existing = await AsyncStorage.getItem(INSTALLATION_KEY);
  if (existing) return existing;
  const id = Crypto.randomUUID();
  await AsyncStorage.setItem(INSTALLATION_KEY, id);
  return id;
}

/**
 * Whether this run of the app can receive remote push at all.
 * Expo Go on Android cannot (removed in SDK 53): there expo-notifications *throws* from its push-token
 * calls, so they must not be reached. Expo Go on iOS still can, and only logs a recommendation to use a
 * development build. Development and store builds are unaffected on both platforms.
 */
export function isPushSupported(): boolean {
  if (Platform.OS === "web" || !Device.isDevice) return false;
  return !(Platform.OS === "android" && isRunningInExpoGo());
}

export function configureForegroundPresentation() {
  if (Platform.OS === "web") return;
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: false,
      shouldSetBadge: false,
    }),
  });
}

async function ensureAndroidChannel() {
  if (Platform.OS !== "android") return;
  await Notifications.setNotificationChannelAsync("default", {
    name: "Bay Sahne duyuruları",
    importance: Notifications.AndroidImportance.DEFAULT,
    lightColor: "#C4973F",
  });
}

function mapPermission(p: Notifications.NotificationPermissionsStatus): Exclude<PushState, "unsupported" | "error"> {
  if (p.granted || p.ios?.status === Notifications.IosAuthorizationStatus.PROVISIONAL) return "granted";
  return p.canAskAgain ? "undetermined" : "denied";
}

async function readRegistration(): Promise<Registration | null> {
  try {
    const v = JSON.parse((await AsyncStorage.getItem(REGISTERED_KEY)) ?? "null");
    return v && typeof v === "object" && typeof v.token === "string" ? (v as Registration) : null;
  } catch {
    return null;
  }
}

/**
 * Whether a device-token event from `addPushTokenListener` needs a re-registration.
 * iOS emits the event for every token request, including the one a sync makes itself, so events
 * during a sync and events repeating the token we already hold are not real rotations.
 */
export function isNewDeviceToken(deviceToken: string): boolean {
  if (inFlight || deviceToken === lastDeviceToken) return false;
  lastDeviceToken = deviceToken;
  return true;
}

/**
 * Reconcile the OS permission with the backend registration.
 * Calls made while one is running share its result (launch, foreground and token events often coincide);
 * a user-initiated prompt waits for the running sync and then runs its own.
 * @param prompt ask the OS for permission if it has not been decided yet (user-initiated only).
 */
export async function syncPushRegistration({ prompt = false } = {}): Promise<PushState> {
  if (inFlight) {
    if (!prompt) return inFlight;
    await inFlight.catch(() => undefined);
  }
  const run = doSync(prompt);
  inFlight = run;
  try {
    return await run;
  } finally {
    if (inFlight === run) inFlight = null;
  }
}

async function doSync(prompt: boolean): Promise<PushState> {
  if (!isPushSupported()) return "unsupported";
  try {
    await ensureAndroidChannel();
    let perm = await Notifications.getPermissionsAsync();
    if (mapPermission(perm) === "undetermined" && prompt) {
      perm = await Notifications.requestPermissionsAsync();
    }
    const state = mapPermission(perm);
    const installation_id = await getInstallationId();
    const platform = Platform.OS === "ios" ? "ios" : "android";

    if (state === "granted") {
      if (!config.easProjectId) {
        console.warn("[push] EAS project id is not configured; cannot obtain an Expo push token.");
        return "error";
      }
      // Fetch the device token ourselves so the event iOS emits for this request is recognised as ours.
      const devicePushToken = await Notifications.getDevicePushTokenAsync();
      if (typeof devicePushToken.data === "string") lastDeviceToken = devicePushToken.data;
      const token = (await Notifications.getExpoPushTokenAsync({ projectId: config.easProjectId, devicePushToken })).data;

      const previous = await readRegistration();
      const unchanged = previous?.token === token && previous.appVersion === config.appVersion;
      if (unchanged && Date.now() - previous.at < REFRESH_MS) return "granted";

      await api.post("/devices", { installation_id, platform, permission: "granted", push_token: token, app_version: config.appVersion });
      const registration: Registration = { token, appVersion: config.appVersion, at: Date.now() };
      await AsyncStorage.setItem(REGISTERED_KEY, JSON.stringify(registration));
      return "granted";
    }

    // Only tell the server about a non-granted state if this installation was registered before,
    // so a user who never opted in never sends anything.
    if ((await AsyncStorage.getItem(REGISTERED_KEY)) !== null) {
      await api.post("/devices", { installation_id, platform, permission: state, push_token: null, app_version: config.appVersion });
      await AsyncStorage.removeItem(REGISTERED_KEY);
    }
    return state;
  } catch (e) {
    console.warn("[push] registration failed", e);
    return "error";
  }
}

/** Route opened by tapping a notification, derived only from our own payload fields. */
export function routeForNotificationData(data: unknown): string | null {
  const d = (data ?? {}) as { production_slug?: unknown };
  if (typeof d.production_slug === "string" && /^[a-z0-9-]{1,160}$/.test(d.production_slug)) {
    return `/oyun/${d.production_slug}`;
  }
  return null;
}
