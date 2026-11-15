import { resolveApiUrl } from "@/lib/config";

describe("API URL in development", () => {
  it("follows the address the phone loaded the app from", () => {
    expect(resolveApiUrl("http://localhost:8100", "172.20.10.4:8081", "development")).toBe("http://172.20.10.4:8100");
    expect(resolveApiUrl("http://127.0.0.1:8100/", "192.168.1.39:8081", "development")).toBe("http://192.168.1.39:8100");
    expect(resolveApiUrl("http://127.0.0.1:8100/", "192.168.1.208:8081", "development")).toBe("http://192.168.1.208:8100");

  });

  it("keeps an explicitly configured server", () => {
    expect(resolveApiUrl("https://api.example.com", "172.20.10.4:8081", "development")).toBe("https://api.example.com");
  });

  it("never rewrites staging or production builds, or tunnel hosts", () => {
    expect(resolveApiUrl("http://localhost:8100", "172.20.10.4:8081", "production")).toBe("http://localhost:8100");
    expect(resolveApiUrl("http://localhost:8100", undefined, "development")).toBe("http://localhost:8100");
    expect(resolveApiUrl("http://localhost:8100", "abc-anonymous-8081.exp.direct", "development")).toBe("http://localhost:8100");
  });
});
