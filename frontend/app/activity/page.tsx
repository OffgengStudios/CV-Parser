"use client"

import { useEffect, useMemo, useState } from "react"
import { Activity, CheckCircle2, Search, XCircle } from "lucide-react"

import { AppSidebar } from "@/components/app-sidebar"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { useToast } from "@/hooks/use-toast"
import {
  fetchActivityLogs,
  fetchCurrentWorkerProfile,
  getApiErrorMessage,
  type ApiActivityLog,
} from "@/lib/api"

function formatAction(action: string) {
  return action
    .split("_")
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(" ")
}

export default function ActivityPage() {
  const { toast } = useToast()
  const [logs, setLogs] = useState<ApiActivityLog[]>([])
  const [loading, setLoading] = useState(true)
  const [isAdmin, setIsAdmin] = useState(false)
  const [checkedAdmin, setCheckedAdmin] = useState(false)
  const [query, setQuery] = useState("")

  useEffect(() => {
    async function loadLogs() {
      setLoading(true)
      try {
        const profile = await fetchCurrentWorkerProfile()
        setIsAdmin(profile.is_admin)
        setCheckedAdmin(true)
        if (!profile.is_admin) {
          setLogs([])
          return
        }
        setLogs(await fetchActivityLogs(200))
      } catch (error) {
        toast({
          title: "Could not load worker logs",
          description: getApiErrorMessage(error),
          variant: "destructive",
        })
      } finally {
        setLoading(false)
        setCheckedAdmin(true)
      }
    }

    loadLogs()
  }, [toast])

  const filteredLogs = useMemo(() => {
    const value = query.trim().toLowerCase()
    if (!value) return logs

    return logs.filter((log) =>
      [
        log.worker,
        log.action,
        log.status,
        log.target_label,
        log.details,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(value)
    )
  }, [logs, query])

  return (
    <div className="min-h-screen bg-background">
      <AppSidebar />
      <main className="pt-16 lg:pl-64 lg:pt-0">
        <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">
                Worker Logs
              </h1>
              <p className="text-muted-foreground mt-1">
                Review worker actions across uploads, deletions, login, and matching
              </p>
            </div>
            <div className="relative w-full sm:w-80">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search logs..."
                className="pl-9"
              />
            </div>
          </div>

          {!loading && checkedAdmin && !isAdmin ? (
            <div className="rounded-lg border border-border bg-card p-5 text-sm text-muted-foreground">
              Worker logs are only available to admins.
            </div>
          ) : (
          <div className="rounded-lg border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border p-5">
              <div className="flex items-center gap-2">
                <Activity className="h-5 w-5 text-primary" />
                <h2 className="text-lg font-semibold text-card-foreground">
                  Activity
                </h2>
              </div>
              <span className="text-sm text-muted-foreground">
                {filteredLogs.length} log{filteredLogs.length === 1 ? "" : "s"}
              </span>
            </div>

            {loading ? (
              <div className="p-5 text-sm text-muted-foreground">
                Loading worker logs...
              </div>
            ) : filteredLogs.length === 0 ? (
              <div className="p-5 text-sm text-muted-foreground">
                No activity logs found.
              </div>
            ) : (
              <div className="divide-y divide-border">
                {filteredLogs.map((log) => (
                  <div
                    key={log.id}
                    className="grid grid-cols-1 gap-3 p-5 md:grid-cols-[180px_1fr_160px]"
                  >
                    <div>
                      <p className="text-sm font-semibold text-card-foreground">
                        {log.worker}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(log.created_at).toLocaleString()}
                      </p>
                    </div>

                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-medium text-card-foreground">
                          {formatAction(log.action)}
                        </p>
                        {log.target_label && (
                          <Badge variant="outline" className="font-normal">
                            {log.target_label}
                          </Badge>
                        )}
                      </div>
                      {log.details && (
                        <p className="mt-1 text-sm text-muted-foreground">
                          {log.details}
                        </p>
                      )}
                    </div>

                    <div className="flex items-start justify-start md:justify-end">
                      <Badge
                        variant={log.status === "success" ? "secondary" : "destructive"}
                        className="gap-1"
                      >
                        {log.status === "success" ? (
                          <CheckCircle2 className="h-3 w-3" />
                        ) : (
                          <XCircle className="h-3 w-3" />
                        )}
                        {log.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          )}
        </div>
      </main>
    </div>
  )
}
