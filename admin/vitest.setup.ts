import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

vi.mock("next/navigation", () => {
  const push = vi.fn();
  const replace = vi.fn();
  return {
    useRouter: () => ({ push, replace, refresh: vi.fn(), back: vi.fn() }),
    usePathname: () => "/",
    useParams: () => ({}),
    useSearchParams: () => new URLSearchParams(),
  };
});
