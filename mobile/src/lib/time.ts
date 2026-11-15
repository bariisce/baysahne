import { useEffect, useState } from "react";
import { AppState } from "react-native";
import type { Performance, ProductionCard } from "./types";

/**
 * The current time, re-read every minute and whenever the app returns to the foreground, so screens that
 * stay mounted (tabs) drop a performance as soon as it has started — without a refresh or a restart.
 */
export function useNow(intervalMs = 60_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const tick = () => setNow(Date.now());
    const timer = setInterval(tick, intervalMs);
    const sub = AppState.addEventListener("change", (s) => {
      if (s === "active") tick();
    });
    return () => {
      clearInterval(timer);
      sub.remove();
    };
  }, [intervalMs]);
  return now;
}

/**
 * The API only returns performances that have not started yet, but the app also shows content cached on
 * the device (offline, or while the API is unreachable) that can be days old. The same rule is therefore
 * applied here against the device clock. An unparsable date is left to the server's judgement.
 */
export function isUpcoming(perf: Pick<Performance, "starts_at">, now: number): boolean {
  const t = Date.parse(perf.starts_at);
  return Number.isNaN(t) || t > now;
}

export function upcomingOnly<T extends Pick<Performance, "starts_at">>(perfs: T[], now: number): T[] {
  return perfs.filter((p) => isUpcoming(p, now));
}

/** A card whose cached "next performance" has already started no longer advertises it. */
export function liveCard<T extends ProductionCard>(card: T, now: number): T {
  if (!card.next_performance || isUpcoming(card.next_performance, now)) return card;
  return { ...card, next_performance: null, upcoming_count: Math.max(0, card.upcoming_count - 1) };
}
