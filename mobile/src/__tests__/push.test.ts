import AsyncStorage from "@react-native-async-storage/async-storage";
import * as Notifications from "expo-notifications";

jest.mock("expo-device", () => ({ isDevice: true }));
jest.mock("expo-crypto", () => ({ randomUUID: jest.fn(() => "1b6f6b2e-0d7b-4c1a-9f7e-3a2b1c0d9e8f") }));
jest.mock("expo-constants", () => ({
  __esModule: true,
  default: { expoConfig: { version: "1.0.0", extra: { apiUrl: "https://api.example.com", eas: { projectId: "test-project" } } } },
}));
jest.mock("expo-notifications", () => ({
  getPermissionsAsync: jest.fn(),
  requestPermissionsAsync: jest.fn(),
  getExpoPushTokenAsync: jest.fn(),
  getDevicePushTokenAsync: jest.fn(),
  setNotificationChannelAsync: jest.fn(),
  setNotificationHandler: jest.fn(),
  AndroidImportance: { DEFAULT: 3 },
  IosAuthorizationStatus: { PROVISIONAL: 3 },
}));

// eslint-disable-next-line import/first
import { getInstallationId, isNewDeviceToken, routeForNotificationData, syncPushRegistration } from "@/lib/push";

const N = Notifications as jest.Mocked<typeof Notifications>;
const granted = { granted: true, canAskAgain: true, status: "granted" } as never;
const undetermined = { granted: false, canAskAgain: true, status: "undetermined" } as never;
const denied = { granted: false, canAskAgain: false, status: "denied" } as never;

let fetchMock: jest.Mock;

beforeEach(async () => {
  await AsyncStorage.clear();
  jest.clearAllMocks();
  fetchMock = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ active: true }) });
  globalThis.fetch = fetchMock as never;
  N.getExpoPushTokenAsync.mockResolvedValue({ data: "ExponentPushToken[abcdefghijklmno]", type: "expo" });
  N.getDevicePushTokenAsync.mockResolvedValue({ data: "apns-device-token-1", type: "ios" });
});

afterEach(() => jest.restoreAllMocks());

function postedBodies() {
  return fetchMock.mock.calls.map(([url, init]: [string, { body: string }]) => ({ url, body: JSON.parse(init.body) }));
}

describe("push registration", () => {
  it("never prompts or contacts the server before the user decides", async () => {
    N.getPermissionsAsync.mockResolvedValue(undetermined);
    expect(await syncPushRegistration()).toBe("undetermined");
    expect(N.requestPermissionsAsync).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("registers the Expo token when the user opts in", async () => {
    N.getPermissionsAsync.mockResolvedValue(undetermined);
    N.requestPermissionsAsync.mockResolvedValue(granted);
    expect(await syncPushRegistration({ prompt: true })).toBe("granted");
    const [{ url, body }] = postedBodies();
    expect(url).toBe("https://api.example.com/api/v1/devices");
    expect(body).toMatchObject({
      installation_id: "1b6f6b2e-0d7b-4c1a-9f7e-3a2b1c0d9e8f",
      permission: "granted",
      push_token: "ExponentPushToken[abcdefghijklmno]",
      app_version: "1.0.0",
    });
    expect(N.getExpoPushTokenAsync).toHaveBeenCalledWith({
      projectId: "test-project",
      devicePushToken: { data: "apns-device-token-1", type: "ios" },
    });
  });

  it("keeps one installation id across launches (no duplicate registrations)", async () => {
    const a = await getInstallationId();
    const b = await getInstallationId();
    expect(a).toBe(b);
  });

  it("re-registers when the token changes so refreshed tokens reach the server", async () => {
    N.getPermissionsAsync.mockResolvedValue(granted);
    await syncPushRegistration();
    N.getExpoPushTokenAsync.mockResolvedValue({ data: "ExponentPushToken[newtoken1234567]", type: "expo" });
    await syncPushRegistration();
    const bodies = postedBodies().map((b: { body: Record<string, unknown> }) => b.body);
    expect(bodies.map((b: Record<string, unknown>) => b.push_token)).toEqual(["ExponentPushToken[abcdefghijklmno]", "ExponentPushToken[newtoken1234567]"]);
    expect(new Set(bodies.map((b: Record<string, unknown>) => b.installation_id)).size).toBe(1);
  });

  it("does not re-send an unchanged token, but refreshes it after a day", async () => {
    N.getPermissionsAsync.mockResolvedValue(granted);
    const t0 = Date.now();
    const now = jest.spyOn(Date, "now").mockReturnValue(t0);
    await syncPushRegistration();
    await syncPushRegistration(); // foreground, same token
    expect(fetchMock).toHaveBeenCalledTimes(1);
    now.mockReturnValue(t0 + 25 * 60 * 60 * 1000);
    await syncPushRegistration();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shares one round trip between concurrent syncs", async () => {
    N.getPermissionsAsync.mockResolvedValue(granted);
    const results = await Promise.all([syncPushRegistration(), syncPushRegistration(), syncPushRegistration()]);
    expect(results).toEqual(["granted", "granted", "granted"]);
    expect(N.getExpoPushTokenAsync).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("ignores the token event caused by its own token request (no registration loop)", async () => {
    N.getPermissionsAsync.mockResolvedValue(granted);
    let eventDuringSync: boolean | undefined;
    N.getDevicePushTokenAsync.mockImplementation(async () => {
      eventDuringSync = isNewDeviceToken("apns-device-token-1"); // iOS emits while the request resolves
      return { data: "apns-device-token-1", type: "ios" };
    });
    await syncPushRegistration();
    expect(eventDuringSync).toBe(false);
    expect(isNewDeviceToken("apns-device-token-1")).toBe(false); // late echo of the same token
    expect(isNewDeviceToken("apns-device-token-2")).toBe(true); // a real rotation
    expect(isNewDeviceToken("apns-device-token-2")).toBe(false);
  });

  it("deactivates a previously registered installation after permission is revoked", async () => {
    N.getPermissionsAsync.mockResolvedValueOnce(granted);
    await syncPushRegistration();
    N.getPermissionsAsync.mockResolvedValueOnce(denied);
    expect(await syncPushRegistration()).toBe("denied");
    const last = postedBodies().at(-1)!.body;
    expect(last).toMatchObject({ permission: "denied", push_token: null });
    // and stays silent afterwards
    N.getPermissionsAsync.mockResolvedValueOnce(denied);
    await syncPushRegistration();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("returns error instead of crashing when the server is unreachable", async () => {
    N.getPermissionsAsync.mockResolvedValue(granted);
    fetchMock.mockRejectedValue(new TypeError("Network request failed"));
    jest.spyOn(console, "warn").mockImplementation(() => {});
    expect(await syncPushRegistration()).toBe("error");
  });

  it("only routes notification taps to well-formed production slugs", () => {
    expect(routeForNotificationData({ production_slug: "sefiller" })).toBe("/oyun/sefiller");
    expect(routeForNotificationData({ production_slug: "../../evil" })).toBeNull();
    expect(routeForNotificationData({ url: "https://evil.example" })).toBeNull();
    expect(routeForNotificationData(null)).toBeNull();
  });
});
