"use client"

/**
 * SessionGuard — wraps the app to handle:
 *   1. Idle timeout (auto-logout after 30 min inactivity).
 *   2. Shows a dismissible warning dialog 2 minutes before logout.
 *
 * Rendered inside RootLayout so it covers every authenticated page.
 * The guard is a no-op on the /login page (no session to time out).
 */
import { usePathname, useRouter } from "next/navigation"
import { useCallback, useEffect } from "react"
import { LogOut, Timer } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useIdleTimeout } from "@/hooks/use-idle-timeout"
import { hasWorkerSession, logoutWorker } from "@/lib/api"

export function SessionGuard() {
  const router = useRouter()
  const pathname = usePathname()

  const isLoginPage = pathname === "/login"

  const handleLogout = useCallback(() => {
    logoutWorker()
    router.replace("/login")
  }, [router])

  const { isWarning, secondsLeft, resetTimer } = useIdleTimeout({
    idleMs: 30 * 60 * 1000,   // 30 minutes
    warningMs: 2 * 60 * 1000, // warn 2 min before
    onIdle: handleLogout,
  })

  // If the user navigates to a protected page but has no session cookie,
  // the middleware handles the redirect. This is a belt-and-suspenders
  // client-side check for when the cookie expires mid-session.
  useEffect(() => {
    if (!isLoginPage && !hasWorkerSession()) {
      router.replace("/login")
    }
  }, [pathname, isLoginPage, router])

  // Don't render the dialog on the login page — there's nothing to time out.
  if (isLoginPage) return null

  const minutes = Math.floor(secondsLeft / 60)
  const seconds = secondsLeft % 60
  const countdownText = minutes > 0
    ? `${minutes}m ${seconds.toString().padStart(2, "0")}s`
    : `${seconds}s`

  return (
    <Dialog open={isWarning}>
      <DialogContent
        // Prevent closing by clicking outside — the only options are "Stay signed in" or timeout.
        onInteractOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
        className="max-w-sm"
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Timer className="h-5 w-5 text-amber-500" />
            Session expiring soon
          </DialogTitle>
          <DialogDescription>
            You&apos;ve been inactive for a while. You&apos;ll be signed out automatically in{" "}
            <span className="font-semibold tabular-nums text-foreground">
              {countdownText}
            </span>
            .
          </DialogDescription>
        </DialogHeader>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="ghost" size="sm" onClick={handleLogout} className="gap-1.5">
            <LogOut className="h-3.5 w-3.5" />
            Sign out now
          </Button>
          <Button onClick={resetTimer}>
            Stay signed in
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
