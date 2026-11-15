import { describe, expect, it } from "vitest";
import { mediaSrc } from "./media";

describe("mediaSrc", () => {
  it("loads local media through the panel's own origin whatever host the API wrote", () => {
    const path = "/media/images/2026/10/b5a43672_sm.webp";
    expect(mediaSrc(`http://192.168.1.208:8100${path}`)).toBe(path);
    expect(mediaSrc(`http://localhost:8100${path}`)).toBe(path);
    expect(mediaSrc(`https://api.example.com${path}`)).toBe(path);
    expect(mediaSrc(path)).toBe(path);
  });

  it("leaves bucket and CDN addresses alone", () => {
    const cdn = "https://cdn.example.com/images/2026/10/b5a43672_sm.webp";
    expect(mediaSrc(cdn)).toBe(cdn);
  });

  it("has nothing to show without an address", () => {
    expect(mediaSrc(null)).toBeUndefined();
    expect(mediaSrc(undefined)).toBeUndefined();
    expect(mediaSrc("")).toBeUndefined();
  });
});
