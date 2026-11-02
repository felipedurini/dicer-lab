import { NextRequest, NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/lib/supabase/server";

export const maxDuration = 60;
const BACKEND_REQUEST_TIMEOUT_MS = 45_000;

const allowed = /^(epsilon-profile|trajectories|design\/references|design\/jobs|design\/jobs\/[0-9a-f-]{36}\/candidates\/[0-9a-f]{64}\/simulate|ncbi\/search|ncbi\/sequences|ncbi\/references|jobs(?:\/[0-9a-f-]{36}(?:\/results|\/cancel|\/exports\/(?:results\.json|configuration\.json|metrics\.csv|manifest-[A-Za-z][A-Za-z0-9_-]{0,47}\.json|design-manifest\.json|kmers\.jsonl|candidates\.fasta|ranking\.csv))?)?)$/;

function isLoopbackHost(host: string) {
  return /^(localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$/i.test(host);
}

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (path[0] !== "v1") return NextResponse.json({ error: { code: "not_found", message: "Versión de API no disponible" } }, { status: 404 });
  const relative = path.slice(1).join("/");
  if (!allowed.test(relative)) return NextResponse.json({ error: { code: "not_found", message: "Ruta no disponible" } }, { status: 404 });

  const appEnv = process.env.APP_ENV ?? (process.env.NODE_ENV === "development" ? "development" : "production");
  const authMode = process.env.AUTH_MODE ?? (appEnv === "development" ? "local" : "supabase");
  const localMode = authMode === "local" && appEnv !== "production" &&
    !process.env.VERCEL && !process.env.RENDER && isLoopbackHost(request.headers.get("host") ?? "");
  let accessToken: string | undefined;
  if (!localMode) {
    try {
      const supabase = await createSupabaseServerClient();
      const [{ data: { user } }, { data: { session } }] = await Promise.all([supabase.auth.getUser(), supabase.auth.getSession()]);
      const allowed = (process.env.ALLOWED_USER_IDS ?? "").split(",").map((id) => id.trim().toLowerCase()).filter(Boolean);
      if (!user || !allowed.includes(user.id.toLowerCase()) || !session?.access_token) {
        return NextResponse.json({ error: { code: "unauthorized", message: "La sesión no autoriza el acceso al laboratorio" } }, { status: 401 });
      }
      accessToken = session.access_token;
    } catch {
      return NextResponse.json({ error: { code: "auth_not_configured", message: "La autenticación requiere configuración Supabase" } }, { status: 503 });
    }
  }

  const base = process.env.SIMULATOR_API_URL ?? "http://127.0.0.1:8000";
  const url = new URL(`/v1/${relative}`, base);
  if ((relative === "jobs" || relative === "ncbi/search") && request.nextUrl.search) url.search = request.nextUrl.search;
  const headers = new Headers({ origin: process.env.APP_ORIGIN ?? "http://127.0.0.1:3000" });
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const idempotency = request.headers.get("idempotency-key");
  if (idempotency) headers.set("idempotency-key", idempotency);
  if (accessToken) headers.set("authorization", `Bearer ${accessToken}`);
  try {
    const response = await fetch(url, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
      cache: "no-store",
      signal: AbortSignal.timeout(BACKEND_REQUEST_TIMEOUT_MS),
    });
    const responseHeaders = new Headers({ "content-type": response.headers.get("content-type") ?? "application/json", "cache-control": "private, no-store" });
    for (const key of ["location", "retry-after", "x-request-id", "idempotency-replayed", "content-disposition"]) {
      const value = response.headers.get(key);
      if (value) responseHeaders.set(key, value);
    }
    return new NextResponse(response.body, { status: response.status, headers: responseHeaders });
  } catch (error) {
    if (error instanceof Error && error.name === "TimeoutError") {
      return NextResponse.json({ error: { code: "simulator_timeout", message: "El backend tardó más de 45 segundos en responder" } }, { status: 504 });
    }
    return NextResponse.json({ error: { code: "simulator_unavailable", message: "No se pudo conectar con el motor local" } }, { status: 503 });
  }
}

export const GET = forward;
export const POST = forward;
export const DELETE = forward;
