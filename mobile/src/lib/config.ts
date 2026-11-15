import Constants from "expo-constants";

type Extra = { variant?: string; apiUrl?: string; privacyPolicyUrl?: string; eas?: { projectId?: string } };

const extra = (Constants.expoConfig?.extra ?? {}) as Extra;
const variant = extra.variant ?? "development";

/**
 * In development an API on localhost means "the computer running Metro". A phone reaches that computer at
 * the address it loaded the bundle from (`hostUri`), so the API follows it: no LAN IP is hard-coded, and a
 * changed network (Wi-Fi ↔ hotspot) needs no reconfiguration. Tunnel hosts are skipped (no API behind them).
 */
export function resolveApiUrl(raw: string, hostUri: string | undefined, appVariant: string): string {
  const url = raw.replace(/\/$/, "");
  if (appVariant !== "development" || !hostUri) return url;
  const host = hostUri.replace(/:\d+$/, "");
  if (!host || host.endsWith(".exp.direct")) return url;
  return url.replace(/^(https?:\/\/)(localhost|127\.0\.0\.1)(?=[:/]|$)/, `$1${host}`);
}

export const config = {
  variant,
  apiUrl: resolveApiUrl(
    process.env.EXPO_PUBLIC_API_URL ?? extra.apiUrl ?? "http://localhost:8100",
    Constants.expoConfig?.hostUri,
    variant,
  ),
  privacyPolicyUrl: extra.privacyPolicyUrl ? resolveApiUrl(extra.privacyPolicyUrl, Constants.expoConfig?.hostUri, variant) : null,
  easProjectId: extra.eas?.projectId ?? null,
  appVersion: Constants.expoConfig?.version ?? "0.0.0",
};
