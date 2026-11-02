import { describe, expect, it } from "vitest";
import { contentSecurityPolicy } from "../lib/security";

describe("Content Security Policy by environment", () => {
  it("allows eval only for development diagnostics", () => {
    expect(contentSecurityPolicy("development")).toContain("script-src 'self' 'unsafe-inline' 'unsafe-eval'");
    const production = contentSecurityPolicy("production");
    expect(production).toContain("script-src 'self' 'unsafe-inline'");
    expect(production).not.toContain("unsafe-eval");
    expect(production).toContain("object-src 'none'");
    expect(production).toContain("upgrade-insecure-requests");
  });
});
