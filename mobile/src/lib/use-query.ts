import AsyncStorage from "@react-native-async-storage/async-storage";
import { useCallback, useEffect, useState } from "react";
import { AppState } from "react-native";
import { api, ApiError } from "./api";

const memory = new Map<string, unknown>();
const PERSIST_PREFIX = "bs-cache:v1:";
const FOREGROUND_REFRESH_MS = 30_000;

export type Query<T> = {
  data: T | null;
  error: ApiError | null;
  loading: boolean; // first load with nothing to show yet
  refreshing: boolean; // pull-to-refresh in progress
  refresh: () => Promise<void>;
};

type State<T> = { path: string | null; data: T | null; error: ApiError | null; settled: boolean; refreshing: boolean };

/**
 * Stale-while-revalidate GET:
 * shows cached content immediately (memory, then the last successful response persisted on the device),
 * then refreshes from the API, and again each time the app returns to the foreground. When offline, cached
 * content stays visible and the error is exposed so the screen can show a non-blocking notice with a retry
 * action. Cached content can be old: anything time-dependent must be filtered by the caller (see lib/time).
 */
export function useQuery<T>(path: string | null, opts: { persist?: boolean } = {}): Query<T> {
  const persist = !!opts.persist;
  const [state, setState] = useState<State<T>>(() => ({
    path,
    data: path ? ((memory.get(path) as T) ?? null) : null,
    error: null,
    settled: false,
    refreshing: false,
  }));

  const fetchFresh = useCallback(
    async (target: string) => {
      try {
        const fresh = await api.get<T>(target);
        memory.set(target, fresh);
        if (persist) AsyncStorage.setItem(PERSIST_PREFIX + target, JSON.stringify(fresh)).catch(() => {});
        setState((s) => (s.path === target ? { ...s, data: fresh, error: null, settled: true, refreshing: false } : s));
      } catch (e) {
        const error = e instanceof ApiError ? e : new ApiError(0, "error", "Bir sorun oluştu.");
        setState((s) => (s.path === target ? { ...s, error, settled: true, refreshing: false } : s));
      }
    },
    [persist],
  );

  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    Promise.resolve()
      .then(() => {
        // Reset for a new path, seeding from the in-memory cache when available.
        if (!cancelled) setState({ path, data: (memory.get(path) as T) ?? null, error: null, settled: memory.has(path), refreshing: false });
        if (!memory.has(path) && persist) return AsyncStorage.getItem(PERSIST_PREFIX + path);
        return null;
      })
      .then((raw) => {
        if (!cancelled && raw && !memory.has(path)) {
          setState((s) => (s.path === path && !s.data ? { ...s, data: JSON.parse(raw) as T, settled: true } : s));
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) fetchFresh(path);
      });
    return () => {
      cancelled = true;
    };
  }, [path, persist, fetchFresh]);

  // Screens in tabs stay mounted for as long as the app lives, so "fetch on mount" alone would leave
  // days-old content on screen. Returning to the app revalidates quietly: fresh data replaces what is
  // shown, and a failed attempt now clears as soon as the API is reachable again.
  useEffect(() => {
    if (!path) return;
    let last = Date.now();
    const sub = AppState.addEventListener("change", (s) => {
      if (s !== "active" || Date.now() - last < FOREGROUND_REFRESH_MS) return;
      last = Date.now();
      fetchFresh(path);
    });
    return () => sub.remove();
  }, [path, fetchFresh]);

  const refresh = useCallback(async () => {
    if (!path) return;
    setState((s) => ({ ...s, refreshing: true }));
    await fetchFresh(path);
  }, [path, fetchFresh]);

  const current = state.path === path;
  return {
    data: current ? state.data : null,
    error: current ? state.error : null,
    loading: !!path && (!current || (!state.settled && !state.data)),
    refreshing: current && state.refreshing,
    refresh,
  };
}

export function clearQueryCache() {
  memory.clear();
}
