"use client"

import { FormEvent, useEffect, useState } from "react"
import { CheckCircle2, Database, Link2, RefreshCcw, Sheet, ShieldCheck, UserPlus, XCircle } from "lucide-react"

import { AppSidebar } from "@/components/app-sidebar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { useToast } from "@/hooks/use-toast"
import { createWorkerLogin, fetchCurrentWorkerProfile, fetchHealth, fetchSettingsStatus, getApiErrorMessage } from "@/lib/api"

const backendUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000"

export default function SettingsPage() {
  const { toast } = useToast()
  const [health, setHealth] = useState<{
    status: string
    database: string
  } | null>(null)
  const [settings, setSettings] = useState<{
    backend_url_hint: string
    google_sheets_configured: boolean
    google_service_account_file_present: boolean
    google_sheets_tab_name: string
    google_sheets_spreadsheet_id: string | null
  } | null>(null)
  const [isCurrentAdmin, setIsCurrentAdmin] = useState(false)
  const [newUsername, setNewUsername] = useState("")
  const [newFullName, setNewFullName] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [newIsAdmin, setNewIsAdmin] = useState(false)
  const [creatingWorker, setCreatingWorker] = useState(false)

  useEffect(() => {
    async function load() {
      try {
        const [healthResponse, settingsResponse, workerProfile] = await Promise.all([
          fetchHealth(),
          fetchSettingsStatus(),
          fetchCurrentWorkerProfile(),
        ])
        setHealth({
          status: healthResponse.status,
          database: healthResponse.database,
        })
        setSettings(settingsResponse)
        setIsCurrentAdmin(workerProfile.is_admin)
      } catch {
        setHealth({
          status: "offline",
          database: "unknown",
        })
      }
    }

    load()
  }, [])

  const statusIcon = health?.status === "ok" ? (
    <CheckCircle2 className="h-5 w-5 text-success" />
  ) : (
    <XCircle className="h-5 w-5 text-destructive" />
  )

  function reloadFrontend() {
    window.location.reload()
  }

  async function handleCreateWorker(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setCreatingWorker(true)

    try {
      const created = await createWorkerLogin({
        username: newUsername.trim(),
        password: newPassword,
        full_name: newFullName.trim() || undefined,
        is_admin: newIsAdmin,
      })
      toast({
        title: "Login created",
        description: `${created.username} can now sign in.`,
      })
      setNewUsername("")
      setNewFullName("")
      setNewPassword("")
      setNewIsAdmin(false)
    } catch (error) {
      toast({
        title: "Could not create login",
        description: getApiErrorMessage(error),
        variant: "destructive",
      })
    } finally {
      setCreatingWorker(false)
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <AppSidebar />
      <main className="pt-16 lg:pl-64 lg:pt-0">
        <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="mb-8">
            <h1 className="text-2xl font-semibold text-foreground">Settings</h1>
            <p className="text-muted-foreground mt-1">
              Connection details for the frontend, backend, and Google Sheets sync
            </p>
          </div>

          <div className="grid gap-6 max-w-4xl">
            {isCurrentAdmin && (
              <section className="rounded-lg border border-border bg-card p-6">
                <div className="mb-5 flex items-center gap-3">
                  <UserPlus className="h-5 w-5 text-primary" />
                  <h2 className="text-lg font-semibold text-card-foreground">
                    Create Worker Login
                  </h2>
                </div>
                <form onSubmit={handleCreateWorker} className="grid gap-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="grid gap-2">
                      <Label htmlFor="new-worker-username">Username</Label>
                      <Input
                        id="new-worker-username"
                        value={newUsername}
                        onChange={(event) => setNewUsername(event.target.value)}
                        autoComplete="off"
                        required
                        minLength={3}
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="new-worker-name">Full name</Label>
                      <Input
                        id="new-worker-name"
                        value={newFullName}
                        onChange={(event) => setNewFullName(event.target.value)}
                        autoComplete="name"
                      />
                    </div>
                  </div>

                  <div className="grid gap-2">
                    <Label htmlFor="new-worker-password">Temporary password</Label>
                    <Input
                      id="new-worker-password"
                      type="password"
                      value={newPassword}
                      onChange={(event) => setNewPassword(event.target.value)}
                      autoComplete="new-password"
                      required
                      minLength={8}
                    />
                  </div>

                  <div className="flex items-center justify-between gap-4 rounded-lg border border-border px-4 py-3">
                    <div className="flex items-center gap-3">
                      <ShieldCheck className="h-5 w-5 text-primary" />
                      <div>
                        <Label htmlFor="new-worker-admin">Admin access</Label>
                        <p className="text-sm text-muted-foreground">
                          Allows this worker to create more logins.
                        </p>
                      </div>
                    </div>
                    <Switch
                      id="new-worker-admin"
                      checked={newIsAdmin}
                      onCheckedChange={setNewIsAdmin}
                    />
                  </div>

                  <div className="flex justify-end">
                    <Button type="submit" disabled={creatingWorker} className="gap-2">
                      <UserPlus className="h-4 w-4" />
                      {creatingWorker ? "Creating..." : "Create Login"}
                    </Button>
                  </div>
                </form>
              </section>
            )}

            <section className="rounded-lg border border-border bg-card p-6">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="flex items-center gap-3">
                    <RefreshCcw className="h-5 w-5 text-primary" />
                    <h2 className="text-lg font-semibold text-card-foreground">
                      Frontend Runtime
                    </h2>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Reload the browser app after UI changes or when the page is showing old frontend code.
                  </p>
                </div>
                <Button onClick={reloadFrontend} className="shrink-0 gap-2">
                  <RefreshCcw className="h-4 w-4" />
                  Reload Frontend
                </Button>
              </div>
            </section>

            <section className="rounded-xl border border-border bg-card p-6">
              <div className="flex items-center gap-3 mb-4">
                <Link2 className="h-5 w-5 text-primary" />
                <h2 className="text-lg font-semibold text-card-foreground">
                  Frontend Connection
                </h2>
              </div>
              <div className="grid gap-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Backend URL</span>
                  <span className="font-medium text-card-foreground">
                    {backendUrl}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Backend hint</span>
                  <span className="font-medium text-card-foreground">
                    {settings?.backend_url_hint || "Unavailable"}
                  </span>
                </div>
              </div>
            </section>

            <section className="rounded-xl border border-border bg-card p-6">
              <div className="flex items-center gap-3 mb-4">
                <Database className="h-5 w-5 text-primary" />
                <h2 className="text-lg font-semibold text-card-foreground">
                  Backend Health
                </h2>
              </div>
              <div className="grid gap-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">API status</span>
                  <span className="font-medium text-card-foreground inline-flex items-center gap-2">
                    {statusIcon}
                    {health?.status || "Checking..."}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Database</span>
                  <span className="font-medium text-card-foreground">
                    {health?.database || "Unknown"}
                  </span>
                </div>
              </div>
            </section>

            <section className="rounded-xl border border-border bg-card p-6">
              <div className="flex items-center gap-3 mb-4">
                <Sheet className="h-5 w-5 text-primary" />
                <h2 className="text-lg font-semibold text-card-foreground">
                  Google Sheets
                </h2>
              </div>
              <div className="grid gap-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Configured</span>
                  <span className="font-medium text-card-foreground">
                    {settings?.google_sheets_configured ? "Yes" : "No"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Credentials file found</span>
                  <span className="font-medium text-card-foreground">
                    {settings?.google_service_account_file_present ? "Yes" : "No"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Tab name</span>
                  <span className="font-medium text-card-foreground">
                    {settings?.google_sheets_tab_name || "Unknown"}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-muted-foreground">Spreadsheet ID</span>
                  <span className="font-medium text-card-foreground break-all text-right">
                    {settings?.google_sheets_spreadsheet_id || "Not set"}
                  </span>
                </div>
              </div>
            </section>
          </div>
        </div>
      </main>
    </div>
  )
}
