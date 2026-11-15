/**
 * Visual identity taken from the official site (baysahne.com): deep ink stage-black, warm cream text,
 * and the gold of the "Bay Sahne" wordmark disc. Display type is Playfair Display, text is Inter.
 */
export const colors = {
  ink: "#0C0A09",
  stage: "#151210",
  surface: "#1C1814",
  surfaceRaised: "#26201A",
  line: "#3A322A",
  cream: "#F5F0E8",
  text: "#EDE6DA",
  muted: "#A8977E", // ≥ 4.5:1 on ink for small text
  gold: "#C4973F",
  goldBright: "#D9AE58",
  danger: "#F08A7E",
  dangerBg: "#3A1714",
  success: "#8FD3A9",
} as const;

export const fonts = {
  display: "PlayfairDisplay_600SemiBold",
  displayBold: "PlayfairDisplay_700Bold",
  displayItalic: "PlayfairDisplay_400Regular_Italic",
  text: "Inter_400Regular",
  textMedium: "Inter_500Medium",
  textSemi: "Inter_600SemiBold",
} as const;

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;
export const radius = { sm: 6, md: 10, lg: 16 } as const;
export const MIN_TOUCH = 44;
