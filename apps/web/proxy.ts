import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

function localDevelopment() {
  const env = process.env.APP_ENV ?? (process.env.NODE_ENV === "development" ? "development" : "production");
  const auth = process.env.AUTH_MODE ?? (env === "development" ? "local" : "supabase");
  return auth === "local" && env !== "production" && !process.env.VERCEL && !process.env.RENDER;
}

export async function proxy(request: NextRequest) {
  if (localDevelopment() || request.nextUrl.pathname === "/login") return NextResponse.next();
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) return NextResponse.redirect(new URL("/login?reason=configuration", request.url));

  let response = NextResponse.next({ request });
  const supabase = createServerClient(url, key, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (values) => {
        values.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        values.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
      },
    },
  });
  const { data: { user } } = await supabase.auth.getUser();
  const allowed = (process.env.ALLOWED_USER_IDS ?? "").split(",").map((id) => id.trim().toLowerCase()).filter(Boolean);
  if (!user || !allowed.includes(user.id.toLowerCase())) {
    const redirect = NextResponse.redirect(new URL("/login", request.url));
    response.cookies.getAll().forEach((cookie) => redirect.cookies.set(cookie));
    return redirect;
  }
  return response;
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};
