import type { ExpoConfig } from "expo/config";

/**
 * Environment-driven app configuration.
 *
 * APP_VARIANT     development | staging | production   (default: development)
 * API_URL         Backend base URL. Production must be https and must not point at a dev host.
 * IOS_BUNDLE_ID   Final iOS bundle identifier   (required for staging/production — not invented here)
 * ANDROID_PACKAGE Final Android application id  (required for staging/production — not invented here)
 * EAS_PROJECT_ID  Expo project id (needed for Expo push tokens; set after `eas init`)
 * PRIVACY_POLICY_URL Public privacy-policy page (store listings + in-app link)
 *
 * Development builds use clearly non-final placeholder identifiers with a `.dev` suffix so a dev build
 * can never be confused with, or overwrite, a store build.
 */
const variant = (process.env.APP_VARIANT ?? "development") as "development" | "staging" | "production";
const isProd = variant === "production";

function required(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`[app.config] ${name} must be set for APP_VARIANT=${variant}. See docs/APP_STORE_RELEASE.md.`);
  return v;
}

const apiUrl =
  variant === "development" ? process.env.API_URL ?? "http://localhost:8100" : required("API_URL");
if (variant !== "development") {
  if (!apiUrl.startsWith("https://")) throw new Error("[app.config] API_URL must use https outside development.");
  if (/localhost|127\.0\.0\.1|10\.0\.2\.2|192\.168\./.test(apiUrl))
    throw new Error("[app.config] API_URL points at a development host for a non-development build.");
}

const iosBundle = variant === "development" ? process.env.IOS_BUNDLE_ID ?? "placeholder.baysahne.dev" : required("IOS_BUNDLE_ID");
const androidPackage =
  variant === "development" ? process.env.ANDROID_PACKAGE ?? "placeholder.baysahne.dev" : required("ANDROID_PACKAGE");
const suffix = variant === "production" ? "" : variant === "staging" ? " (Test)" : " (Dev)";

const config: ExpoConfig = {
  name: `Bay Sahne${suffix}`,
  slug: "baysahne",
  scheme: isProd ? "baysahne" : `baysahne-${variant}`,
  version: "1.0.0",
  orientation: "portrait",
  icon: "./assets/icon.png",
  userInterfaceStyle: "dark",
  backgroundColor: "#0C0A09",
  ios: {
    bundleIdentifier: iosBundle,
    supportsTablet: true,
    buildNumber: process.env.IOS_BUILD_NUMBER ?? "1",
    infoPlist: { ITSAppUsesNonExemptEncryption: false },
  },
  android: {
    package: androidPackage,
    versionCode: Number(process.env.ANDROID_VERSION_CODE ?? 1),
    adaptiveIcon: {
      backgroundColor: "#0C0A09",
      foregroundImage: "./assets/android-icon-foreground.png",
      backgroundImage: "./assets/android-icon-background.png",
      monochromeImage: "./assets/android-icon-monochrome.png",
    },
    // Only what push delivery needs. No location, contacts, camera, etc.
    permissions: ["android.permission.POST_NOTIFICATIONS"],
    blockedPermissions: ["android.permission.RECORD_AUDIO", "android.permission.ACCESS_FINE_LOCATION"],
    predictiveBackGestureEnabled: false,
    // google-services.json is supplied at build time via an EAS file secret, never committed.
    googleServicesFile: process.env.GOOGLE_SERVICES_JSON,
  },
  web: { favicon: "./assets/favicon.png", bundler: "metro" },
  plugins: [
    "expo-router",
    "expo-image",
    "expo-web-browser",
    "expo-font",
    [
      "expo-splash-screen",
      { image: "./assets/splash-icon.png", imageWidth: 220, resizeMode: "contain", backgroundColor: "#0C0A09" },
    ],
    ["expo-notifications", { color: "#C4973F", defaultChannel: "default" }],
  ],
  experiments: { typedRoutes: true },
  extra: {
    variant,
    apiUrl,
    privacyPolicyUrl: process.env.PRIVACY_POLICY_URL ?? `${apiUrl}/legal`,
    eas: process.env.EAS_PROJECT_ID ? { projectId: process.env.EAS_PROJECT_ID } : undefined,
  },
};

export default config;
