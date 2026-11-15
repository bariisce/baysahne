# App Store & Google Play Release Preparation

Nothing has been submitted and no store or EAS resource has been created. Each step below happens in **your** accounts and needs your go-ahead.

## 1. Identifiers (decision needed)

The app does not invent permanent identifiers. `app.config.ts` reads:

| Variable | Used for | Example format (do not copy) |
|---|---|---|
| `IOS_BUNDLE_ID` | App Store Connect bundle id | `com.<owner>.<app>` |
| `ANDROID_PACKAGE` | Google Play application id (cannot change after first upload) | `com.<owner>.<app>` |
| `EAS_PROJECT_ID` | Expo project (push tokens, EAS builds) | created by `eas init` |
| `API_URL` | Production API (`https://…`) | — |
| `PRIVACY_POLICY_URL` | In-app link + store listing | e.g. `https://api.<domain>/legal/<slug>` |

Development builds use clearly non-final placeholders (`placeholder.baysahne.dev`, app name “Bay Sahne (Dev)”). Staging and production builds **fail to configure** unless the identifiers are set, `API_URL` is https, and `API_URL` is not a LAN or localhost address. A dev build therefore cannot point at production by accident, and vice versa.

Build variants (`mobile/eas.json`):

| Profile | `APP_VARIANT` | Purpose |
|---|---|---|
| `development` | development | Dev client for local testing (push works on real devices) |
| `staging` | staging | Internal distribution against a staging API |
| `production` | production | Store builds |

## 2. Accounts and one-time setup

- **Apple Developer Program** (paid yearly) → App Store Connect: create the app with the final bundle id and primary language Turkish.
- **Google Play Console** (one-time fee) → create the app; complete *App content* (privacy policy, data safety, content rating, target audience, ads = none).
- **Expo**: `cd mobile && npx eas-cli@latest init`, then set `EAS_PROJECT_ID`.
- **Push credentials**: see NOTIFICATIONS.md (FCM v1 service-account key and `google-services.json` for Android; APNs key for iOS) via `eas credentials`.
- **Signing**: let EAS manage the iOS certificates/profiles and the Android upload keystore (`eas credentials`). Back up the Android keystore. Never commit keystores or `.p8` files (git-ignored).

## 3. Build and submit

```bash
cd mobile
APP_VARIANT=development npx eas-cli@latest build --profile development --platform all
npx eas-cli@latest build --profile staging --platform all
npx eas-cli@latest build --profile production --platform all
npx eas-cli@latest submit --profile production --platform ios
npx eas-cli@latest submit --profile production --platform android
```

The `submit` commands require your explicit approval. Set the required env vars in the EAS project environments (`development`, `preview`, `production`) rather than in shell history. Version and build numbers are managed remotely (`appVersionSource: remote`, `autoIncrement`).

## 4. Store listing material (to prepare)

- **Name**: “Bay Sahne” (confirm with the organisation). **Subtitle / short description** in Turkish.
- **Description**: tell readers what the app does (the repertoire, performance dates, notifications) and what it does not do. No ticket sales.
- **Category**: Entertainment (or Lifestyle).
- **Screenshots**: iPhone 6.9" and 6.5", iPad if `supportsTablet` stays true, and Android phone. Capture from a production-like build with real content and real dates.
- **App icon**: `mobile/assets/icon.png` is derived from the official wordmark on the brand's ink colour. It is **provisional** until the organisation approves it. The Android adaptive icon and splash are generated from the same wordmark.
- **Support URL and contact e-mail**: the organisation's (baysahne@gmail.com is in the source document; confirm it may be published).
- **Privacy policy URL**: required by both stores. It must point to a reviewed, **published** text (see LEGAL_REVIEW). The legal documents are currently drafts.

## 5. Privacy disclosures (based on what the app actually does)

| Data | Collected? | Purpose | Linked to identity? | Tracking? |
|---|---|---|---|---|
| Push token (Expo/FCM/APNs) | Yes, only after opt-in | Sending notifications | No (no accounts) | No |
| Random installation id | Yes, only after opt-in | Avoid duplicate registrations | No | No |
| Platform (iOS/Android), app version | Yes, only after opt-in | Delivery and support | No | No |
| IP address | Seen by the API/hosting in request logs | Security, operations | No | No |
| Name, e-mail, location, contacts, photos, analytics, ads | **No** | — | — | — |

- **Apple** App Privacy: “Identifiers → Device ID” (push token / installation id) for *App Functionality*, not linked, not tracking.
- **Google Data Safety**: “Device or other IDs”, collected, not shared, for app functionality, encrypted in transit, deletable on request (organisation process, see LEGAL_REVIEW).

Re-check these answers if analytics, crash reporting or accounts are ever added.

## 6. Pre-submission checklist

- [ ] Identifiers decided and set; staging build tested on real iOS and Android devices
- [ ] Push received on both platforms (new production, reminder, cancellation) from staging
- [ ] Notification tap opens the right production
- [ ] Legal texts reviewed and published; privacy URL reachable over https
- [ ] Production API live with real content; at least one real performance date, or the empty state reviewed
- [ ] Icon and splash approved by Bay Sahne
- [ ] TestFlight / Play internal testing round with staff
- [ ] Apple review notes: no login required; notifications are optional
