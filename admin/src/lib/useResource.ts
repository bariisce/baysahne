"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api";

export type Resource<T> = {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
  setData: (d: T) => void;
};

type State<T> = { key: string | null; data: T | null; error: ApiError | null };

/**
 * Minimal data loader: fetches on mount / path change, exposes reload and optimistic setData.
 * `loading` is derived (the latest request key has not resolved yet); previous data stays visible
 * during a reload so tables do not flash.
 */
export function useResource<T>(path: string | null): Resource<T> {
  const [nonce, setNonce] = useState(0);
  const key = path ? `${path}#${nonce}` : null;
  const [state, setState] = useState<State<T>>({ key: null, data: null, error: null });

  useEffect(() => {
    if (!path || !key) return;
    const ctrl = new AbortController();
    api
      .get<T>(path, { signal: ctrl.signal })
      .then((data) => setState({ key, data, error: null }))
      .catch((e) => {
        if ((e as Error).name === "AbortError") return;
        const error = e instanceof ApiError ? e : new ApiError(0, "error", String(e));
        setState((s) => ({ key, data: s.data, error }));
      });
    return () => ctrl.abort();
  }, [path, key]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  const setData = useCallback((data: T) => setState((s) => ({ ...s, data, error: null })), []);
  return { data: state.data, error: state.error, loading: !!key && state.key !== key, reload, setData };
}
