"use client"

import { useEffect, useState, useSyncExternalStore } from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { cn } from "@/lib/utils"
import {
  LayoutDashboard,
  LogOut,
  Menu,
  Search,
  Upload,
  Users,
  Settings,
  FileText,
  Activity,
  X,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { fetchCurrentWorkerProfile, getCurrentWorker, hasWorkerSession, logoutWorker } from "@/lib/api"

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Upload CVs", href: "/upload", icon: Upload },
  { name: "Candidates", href: "/candidates", icon: Users },
  { name: "Match Jobs", href: "/match", icon: Search },
  { name: "Worker Logs", href: "/activity", icon: Activity },
]

function subscribeToWorkerSession(onStoreChange: () => void) {
  window.addEventListener("storage", onStoreChange)
  return () => window.removeEventListener("storage", onStoreChange)
}

function getServerWorkerSnapshot() {
  return null
}

export function AppSidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [isAdmin, setIsAdmin] = useState(false)
  const worker = useSyncExternalStore(
    subscribeToWorkerSession,
    getCurrentWorker,
    getServerWorkerSnapshot
  )

  useEffect(() => {
    if (!hasWorkerSession()) {
      router.replace("/login")
      return
    }
  }, [router])

  useEffect(() => {
    async function loadWorkerProfile() {
      try {
        const profile = await fetchCurrentWorkerProfile()
        setIsAdmin(profile.is_admin)
      } catch {
        setIsAdmin(false)
      }
    }

    if (hasWorkerSession()) {
      loadWorkerProfile()
    }
  }, [worker])

  function handleLogout() {
    logoutWorker()
    setMobileOpen(false)
    router.replace("/login")
  }

  const sidebar = (
    <div className="flex h-full flex-col">
        <div className="flex h-16 items-center gap-2 border-b border-sidebar-border px-6">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <FileText className="h-4 w-4" />
          </div>
          <span className="text-lg font-semibold text-sidebar-foreground">
            CVParser
          </span>
        </div>
        <nav className="flex-1 px-3 py-4">
          <ul className="flex flex-col gap-1">
            {navigation
              .filter((item) => item.href !== "/activity" || isAdmin)
              .map((item) => {
              const isActive =
                item.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(item.href)
              return (
                <li key={item.name}>
                  <Link
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    className={cn(
                      "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-sidebar-accent text-sidebar-primary"
                        : "text-sidebar-foreground hover:bg-sidebar-accent/50"
                    )}
                  >
                    <item.icon className="h-5 w-5" />
                    {item.name}
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>
        <div className="border-t border-sidebar-border p-3">
          {worker && (
            <div className="mb-2 rounded-lg bg-sidebar-accent/50 px-3 py-2">
              <p className="text-xs text-muted-foreground">Signed in as</p>
              <p className="truncate text-sm font-semibold text-sidebar-foreground">
                {worker}
              </p>
            </div>
          )}
          <Link
            href="/settings"
            onClick={() => setMobileOpen(false)}
            className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-sidebar-foreground hover:bg-sidebar-accent/50 transition-colors"
          >
            <Settings className="h-5 w-5" />
            Settings
          </Link>
          <button
            onClick={handleLogout}
            className="mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-sidebar-foreground transition-colors hover:bg-sidebar-accent/50"
          >
            <LogOut className="h-5 w-5" />
            Log out
          </button>
        </div>
      </div>
  )

  return (
    <>
      <header className="fixed left-0 right-0 top-0 z-50 flex h-16 items-center justify-between border-b border-sidebar-border bg-sidebar px-4 lg:hidden">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <FileText className="h-4 w-4" />
          </div>
          <span className="text-lg font-semibold text-sidebar-foreground">
            CVParser
          </span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setMobileOpen((open) => !open)}
          aria-label={mobileOpen ? "Close navigation" : "Open navigation"}
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </Button>
      </header>

      <aside className="fixed left-0 top-0 z-40 hidden h-screen w-64 border-r border-sidebar-border bg-sidebar lg:block">
        {sidebar}
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            className="absolute inset-0 bg-background/70 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation"
          />
          <aside className="relative h-full w-72 border-r border-sidebar-border bg-sidebar shadow-xl">
            {sidebar}
          </aside>
        </div>
      )}
    </>
  )
}
