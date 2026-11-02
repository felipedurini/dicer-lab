/** CSP shared by Next headers with narrowly scoped development diagnostics. */
export function contentSecurityPolicy(environment: string | undefined): string {
  const scriptEval = environment === "development" ? " 'unsafe-eval'" : "";
  const directives = [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "style-src 'self' 'unsafe-inline'",
    `script-src 'self' 'unsafe-inline'${scriptEval}`,
    "connect-src 'self' https://*.supabase.co wss://*.supabase.co",
  ];
  if (environment === "production") directives.push("upgrade-insecure-requests");
  return directives.join("; ");
}
