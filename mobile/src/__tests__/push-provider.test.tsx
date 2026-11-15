import { render, screen, waitFor } from "@testing-library/react-native";
import { isRunningInExpoGo } from "expo";
import * as Notifications from "expo-notifications";
import { Platform, Text } from "react-native";

jest.mock("expo", () => ({ isRunningInExpoGo: jest.fn(() => false) }));
jest.mock("expo-device", () => ({ isDevice: true }));
jest.mock("expo-crypto", () => ({ randomUUID: jest.fn(() => "1b6f6b2e-0d7b-4c1a-9f7e-3a2b1c0d9e8f") }));
jest.mock("expo-router", () => ({ router: { push: jest.fn() } }));
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
  addPushTokenListener: jest.fn(() => ({ remove: jest.fn() })),
  addNotificationResponseReceivedListener: jest.fn(() => ({ remove: jest.fn() })),
  getLastNotificationResponse: jest.fn(() => null),
  AndroidImportance: { DEFAULT: 3 },
  IosAuthorizationStatus: { PROVISIONAL: 3 },
}));

// eslint-disable-next-line import/first
import { PushProvider, usePush } from "@/components/push-provider";

const N = Notifications as jest.Mocked<typeof Notifications>;
const inExpoGo = isRunningInExpoGo as jest.Mock;

function State() {
  return <Text>state:{usePush().state}</Text>;
}

beforeEach(() => jest.clearAllMocks());
afterEach(() => jest.restoreAllMocks());

describe("PushProvider", () => {
  it("starts in Expo Go on Android without touching the push-token calls that throw there", async () => {
    jest.replaceProperty(Platform, "OS", "android");
    inExpoGo.mockReturnValue(true);
    // What expo-notifications really does in Expo Go on Android.
    const removed = new Error("Android Push notifications … was removed from Expo Go with the release of SDK 53.");
    N.addPushTokenListener.mockImplementation(() => {
      throw removed;
    });
    N.getDevicePushTokenAsync.mockRejectedValue(removed);

    await render(
      <PushProvider>
        <State />
      </PushProvider>,
    );

    await waitFor(() => expect(screen.getByText("state:unsupported")).toBeTruthy());
    expect(N.addPushTokenListener).not.toHaveBeenCalled();
    expect(N.getDevicePushTokenAsync).not.toHaveBeenCalled();
    // Tapping a notification still routes: that listener does not depend on remote push.
    expect(N.addNotificationResponseReceivedListener).toHaveBeenCalled();
  });

  it("keeps push working in a real Android build", async () => {
    jest.replaceProperty(Platform, "OS", "android");
    inExpoGo.mockReturnValue(false);
    N.addPushTokenListener.mockImplementation(() => ({ remove: jest.fn() }));
    N.getPermissionsAsync.mockResolvedValue({ granted: false, canAskAgain: true, status: "undetermined" } as never);

    await render(
      <PushProvider>
        <State />
      </PushProvider>,
    );

    await waitFor(() => expect(screen.getByText("state:undetermined")).toBeTruthy());
    expect(N.addPushTokenListener).toHaveBeenCalledTimes(1);
  });

  it("keeps push working in Expo Go on iOS", async () => {
    inExpoGo.mockReturnValue(true);
    N.addPushTokenListener.mockImplementation(() => ({ remove: jest.fn() }));
    N.getPermissionsAsync.mockResolvedValue({ granted: false, canAskAgain: true, status: "undetermined" } as never);

    await render(
      <PushProvider>
        <State />
      </PushProvider>,
    );

    await waitFor(() => expect(screen.getByText("state:undetermined")).toBeTruthy());
    expect(N.addPushTokenListener).toHaveBeenCalledTimes(1);
  });
});
