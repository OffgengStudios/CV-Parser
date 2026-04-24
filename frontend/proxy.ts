/**
 * proxy.ts — Next.js edge proxy (formerly "middleware") for route-level auth guarding.
 *
 * Why a cookie instead of the JWT?
 * - localStorage is inaccessible in edge middleware (no DOM, no window).
 * - We set a lightweight "cvparser_session=1" cookie on login (in api.ts) that
 *   middleware can read. The actual JWT stays in localStorage for security.
 * - This gives us a fast server-side redirect before React even boots, preventing
 *   a flash of protected content for unauthenticated users.
 *
 * Protected routes: everything except /login and Next.js internals (_next, favicon, icons).
 *
 * Note: In Next.js 16.2+, "middleware.ts" was renamed to "proxy.ts".
 */
import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

const SESSION_COOKIE = "cvparser_session"

/** Paths that don't require authentication */
const PUBLIC_PREFIXES = ["/login", "/_next", "/favicon", "/icon", "/apple-icon"]

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix))
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl

  if (isPublicPath(pathname)) {
    return NextResponse.next()
  }

  const sessionCookie = request.cookies.get(SESSION_COOKIE)
  if (!sessionCookie?.value) {
    // No session cookie → redirect to login, preserving the intended URL so
    // we can redirect back after a successful login in the future.
    const loginUrl = request.nextUrl.clone()
    loginUrl.pathname = "/login"
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  /**
   * Match all routes except static files that Next.js handles internally.
   * The negative lookahead avoids matching _next/static, _next/image, and
   * direct file references (e.g. .png, .svg, .ico).
   */
  matcher: ["/((?!_next/static|_next/image|.*\\.(?:png|svg|ico|jpg|jpeg|webp|gif|woff2?|ttf|otf|css|js)$).*)"],
}
