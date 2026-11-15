# Legal & Privacy Review — open questions

**Status: requires review by Bay Sahne and, where noted, a qualified legal professional.** This document makes no claim that any legal requirement (KVKK, GDPR, store policies) has been satisfied. It records what the software actually does and where the supplied texts do not match it.

## 1. What the mobile app and backend actually process

| Data | When | Why | Where stored | Processors |
|---|---|---|---|---|
| Expo push token, random installation id, platform, app version, permission state | Only after the user enables notifications | Deliver notifications; avoid duplicates | Project PostgreSQL (`push_devices`) | Hosting/DB provider (TBD); Expo (push relay); Google FCM (Android delivery); Apple APNs (iOS delivery) |
| Delivery log (job, device, status, provider ticket) | Each notification | Duplicate prevention, troubleshooting | PostgreSQL (`notification_deliveries`) | Hosting/DB provider |
| IP address, user agent | Every API request (web server logs); admin logins (`admin_sessions`, `audit_logs`) | Security, rate limiting, audit | Hosting logs; PostgreSQL | Hosting provider |
| Staff name, e-mail, password hash, login history | Staff accounts only | Admin access | PostgreSQL | Hosting/DB provider; SMTP provider (invitation/reset e-mails) |

The app has **no** audience accounts, no profiles, no comments or ratings, no analytics, no advertising SDKs, no location access, and no Firebase Authentication or Firestore. On the device it stores the installation id, the notification-prompt dismissal and cached public content (AsyncStorage).

## 2. Mismatches in the supplied texts (`BAY SAHNE BİLGİLER.docx`)

The four texts were imported verbatim as **draft** `legal_documents` and are **not published**. Issues found:

| Text | Issue |
|---|---|
| Gizlilik Politikası | Describes membership, profile photos, birth dates, a comment and review system and team management. None of these exist in the app. It states data is stored on **Google Firebase (Database and Authentication)**; this system uses its own PostgreSQL and no Firebase Auth/Firestore (Firebase is used only as the FCM project for Android push). It does not mention push tokens, Expo or APNs. The data controller is called “Baysahne Tiyatro Topluluğu”, while the organisation profile says “Baysahne Performans Atölyesi”: **confirm the legal entity name**. |
| Kullanım Şartları | Refers to “Baysahne.com”, membership, team applications and a review/scoring system. It needs a mobile-app version (or a scope statement) if it is to be shown in the app. |
| Çerez Politikası | Applies to the **website** only (it mentions Firebase Auth cookies and dark-mode preferences). The native app uses no cookies. It is marked `applies_to = website` and must not be presented as describing the app. |
| KVKK Aydınlatma Metni | Purposes (membership, team organisation, 5651 logs) and the transfer section (“Google Firebase”) do not match the app. It does not cover push notifications or overseas transfer to Expo/Google/Apple servers (KVKK Art. 9 implications need assessment). |
| All | Some line breaks and spacing are glued in the source (e.g. “GizlilikSafari: …”). Kept verbatim in the drafts. |

## 3. Decisions needed from the organisation

1. Exact legal name and address of the data controller (*veri sorumlusu*), and whether VERBİS registration applies.
2. Legal basis for processing push tokens (consent through the OS permission vs. legitimate interest). Needs a lawyer's view.
3. Cross-border transfer of push tokens to Expo (USA), Google and Apple, and the KVKK Art. 9 mechanism. Needs a lawyer's view.
4. **Retention periods** for: inactive device records, delivery logs, audit logs, admin sessions and web server logs. `python -m app.cli prune` implements deletion, but the periods have deliberately been left for you to decide.
5. Hosting and e-mail providers and their locations (not yet chosen).
6. Contact channel for data-subject requests (KVKK Art. 11) and an internal process to delete a device record on request. The `installation_id` is not visible to users. Suggested approach: a user who turns notifications off has their device deactivated automatically; full deletion runs through the prune schedule.
7. Whether minors are a target audience (store age rating, content rating questionnaire).

## 4. What has been prepared

- A `legal_documents` system with draft/published status, `applies_to` scope and review notes. Admins can edit and publish in **Kurum ve yasal metinler**.
- Public HTML pages at `/legal` and `/legal/{slug}` (only published documents). Use one of them as the store privacy URL (`PRIVACY_POLICY_URL`).
- The app shows an honest empty state (“Yasal metinler hazırlanıyor…”) until a text is published.
- The About screen states in plain Turkish what is stored for notifications.

## 5. Suggested next step

Draft a short **Mobil Uygulama Gizlilik Bildirimi** that covers only §1 above, have it reviewed, publish it with `applies_to = mobile_app`, and use its URL in both stores. Revise the website texts separately.
