"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  Search,
  Upload,
  Users,
  XCircle,
} from "lucide-react"

import { AppSidebar } from "@/components/app-sidebar"
import { CandidateCard, type Candidate } from "@/components/candidate-card"
import { StatsCard } from "@/components/stats-card"
import { SystemStatus } from "@/components/system-status"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useToast } from "@/hooks/use-toast"
import {
  deleteCandidate,
  fetchCandidates,
  fetchHealth,
  fetchUploadLogs,
  getApiErrorMessage,
  type ApiUploadLog,
} from "@/lib/api"

function formatTimeAgo(value: string): string {
  const date = new Date(value)
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000)
  if (seconds < 60) return "Just now"
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function getStatusBadge(status: string) {
  switch (status) {
    case "success":
      return (
        <Badge className="gap-1 bg-success text-success-foreground hover:bg-success/90">
          <CheckCircle2 className="h-3 w-3" />
          Completed
        </Badge>
      )
    case "failed":
    case "invalid":
      return (
        <Badge variant="destructive" className="gap-1">
          <XCircle className="h-3 w-3" />
          Failed
        </Badge>
      )
    default:
      return (
        <Badge variant="secondary" className="gap-1">
          <AlertCircle className="h-3 w-3" />
          Unknown
        </Badge>
      )
  }
}

function mapLogStatus(logs: ApiUploadLog[]) {
  const failed = logs.filter((log) => log.status !== "success").length
  const completed = logs.filter((log) => log.status === "success").length
  return { failed, completed }
}

export default function DashboardPage() {
  const { toast } = useToast()
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [candidateTotal, setCandidateTotal] = useState(0)
  const [logs, setLogs] = useState<ApiUploadLog[]>([])
  const [health, setHealth] = useState<{
    status: string
    database: string
  } | null>(null)
  const [loading, setLoading] = useState(true)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<Candidate | null>(null)

  useEffect(() => {
    async function loadDashboard() {
      try {
        const [candidateResponse, logResponse, healthResponse] = await Promise.all([
          fetchCandidates(),
          fetchUploadLogs(500),
          fetchHealth(),
        ])

        setCandidateTotal(candidateResponse.total)
        setCandidates(
          candidateResponse.candidates.map((candidate) => ({
            id: candidate.id,
            name: candidate.name || "Unnamed Candidate",
            email: candidate.email || "No email",
            phone: candidate.phone || "Not provided",
            skills: candidate.skills,
            category: candidate.category || "Unknown",
            subcategory: candidate.subcategory,
            confidence: candidate.confidence,
            createdAt: candidate.created_at,
            sourceFilename: candidate.source_filename,
          }))
        )
        setLogs(logResponse)
        setHealth({
          status: healthResponse.status,
          database: healthResponse.database,
        })
      } catch (error) {
        toast({
          title: "Dashboard unavailable",
          description: getApiErrorMessage(error),
          variant: "destructive",
        })
      } finally {
        setLoading(false)
      }
    }

    loadDashboard()
  }, [])

  async function handleDeleteCandidate(id: string) {
    const target = candidates.find((candidate) => candidate.id === id)
    if (!target) return
    setPendingDelete(target)
  }

  async function confirmDeleteCandidate() {
    if (!pendingDelete) return
    setDeletingId(pendingDelete.id)
    try {
      await deleteCandidate(pendingDelete.id)
      setCandidates((prev) =>
        prev.filter((candidate) => candidate.id !== pendingDelete.id)
      )
      setLogs((prev) =>
        prev.filter((log) => log.candidate_id !== pendingDelete.id)
      )
      toast({
        title: "Candidate deleted",
        description: `${pendingDelete.name} was removed successfully.`,
      })
      setPendingDelete(null)
    } catch {
      toast({
        title: "Delete failed",
        description: "The candidate could not be removed.",
        variant: "destructive",
      })
    } finally {
      setDeletingId(null)
    }
  }

  const stats = useMemo(() => {
    const { failed, completed } = mapLogStatus(logs)
    return {
      totalUploads: logs.length,
      parsedCandidates: candidateTotal,
      failed,
      completed,
    }
  }, [candidateTotal, logs])
  const recentFailures = useMemo(
    () => logs.filter((log) => log.status !== "success").slice(0, 3),
    [logs]
  )
  const successRate = stats.totalUploads
    ? Math.round((stats.completed / stats.totalUploads) * 100)
    : 0

  return (
    <div className="min-h-screen bg-background">
      <AppSidebar />
      <AlertDialog
        open={!!pendingDelete}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete candidate?</AlertDialogTitle>
            <AlertDialogDescription>
              {pendingDelete
                ? `This will permanently remove ${pendingDelete.name} from the system.`
                : "This action cannot be undone."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDeleteCandidate}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              {deletingId ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <main className="pt-16 lg:pl-64 lg:pt-0">
        <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">
                Recruitment Dashboard
              </h1>
              <p className="text-muted-foreground mt-1">
                Upload CVs, review parsed candidates, and match them to jobs
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button asChild>
                <Link href="/upload">
                  <Upload className="h-4 w-4" />
                  Upload CVs
                </Link>
              </Button>
              <Button variant="outline" asChild>
                <Link href="/match">
                  <Search className="h-4 w-4" />
                  Match Job
                </Link>
              </Button>
            </div>
          </div>

          <div className="mb-8 grid grid-cols-1 gap-3 md:grid-cols-3">
            {[
              ["1", "Upload CVs", "Add PDF or DOCX files"],
              ["2", "Review Candidates", "Check parsed profiles"],
              ["3", "Match Job", "Rank candidates by fit"],
            ].map(([step, title, description]) => (
              <div
                key={step}
                className="flex items-center gap-3 rounded-lg border border-border bg-card p-4"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                  {step}
                </div>
                <div>
                  <p className="text-sm font-semibold text-card-foreground">
                    {title}
                  </p>
                  <p className="text-xs text-muted-foreground">{description}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <StatsCard
              title="Files Uploaded"
              value={stats.totalUploads}
              description="All upload attempts"
              icon={<Upload className="h-5 w-5" />}
            />
            <StatsCard
              title="Candidates Parsed"
              value={stats.parsedCandidates}
              description="Stored in the backend"
              icon={<Users className="h-5 w-5" />}
            />
            <StatsCard
              title="Success Rate"
              value={`${successRate}%`}
              description={`${stats.completed} successful files`}
              icon={<CheckCircle2 className="h-5 w-5" />}
            />
            <StatsCard
              title="Failed Files"
              value={stats.failed}
              description="Need attention"
              icon={<AlertCircle className="h-5 w-5" />}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 flex flex-col gap-6">
              <div className="rounded-xl border border-border bg-card">
                <div className="flex items-center justify-between p-5 border-b border-border">
                  <div>
                    <h2 className="text-lg font-semibold text-card-foreground">
                      Recent Uploads
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      Latest processing results from the API
                    </p>
                  </div>
                  <Button variant="outline" size="sm" asChild>
                    <Link href="/upload">Upload New</Link>
                  </Button>
                </div>
                <div className="divide-y divide-border">
                  {loading ? (
                    <div className="p-4 text-sm text-muted-foreground">
                      Loading uploads...
                    </div>
                  ) : logs.length === 0 ? (
                    <div className="p-4 text-sm text-muted-foreground">
                      No uploads yet.
                    </div>
                  ) : (
                    logs.slice(0, 10).map((upload) => (
                      <div
                        key={upload.id}
                        className={`flex items-center gap-4 p-4 transition-colors ${
                          upload.status === "success"
                            ? "hover:bg-muted/30"
                            : "bg-destructive/5 hover:bg-destructive/10"
                        }`}
                      >
                        <div
                          className={`rounded-lg p-2.5 ${
                            upload.status === "success"
                              ? "bg-muted"
                              : "bg-destructive/10"
                          }`}
                        >
                          <FileText
                            className={`h-5 w-5 ${
                              upload.status === "success"
                                ? "text-muted-foreground"
                                : "text-destructive"
                            }`}
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-card-foreground truncate">
                            {upload.filename}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {upload.error_message || upload.candidate_id || "Saved to database"}
                          </p>
                        </div>
                        <div className="flex items-center gap-3">
                          {getStatusBadge(upload.status)}
                          <span className="text-xs text-muted-foreground whitespace-nowrap">
                            {formatTimeAgo(upload.created_at)}
                          </span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="rounded-xl border border-border bg-card">
                <div className="flex items-center justify-between p-5 border-b border-border">
                  <div>
                    <h2 className="text-lg font-semibold text-card-foreground">
                      Recent Candidates
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      Profiles coming from the FastAPI backend
                    </p>
                  </div>
                  <Button variant="outline" size="sm" asChild>
                    <Link href="/candidates">View All</Link>
                  </Button>
                </div>
                <div className="p-4 flex flex-col gap-3">
                  {loading ? (
                    <div className="text-sm text-muted-foreground">Loading candidates...</div>
                  ) : candidates.length === 0 ? (
                    <div className="text-sm text-muted-foreground">No candidates parsed yet.</div>
                  ) : (
                    candidates.slice(0, 4).map((candidate) => (
                      <CandidateCard
                        key={candidate.id}
                        candidate={{
                          ...candidate,
                          onDelete: handleDeleteCandidate,
                          deleting: deletingId === candidate.id,
                        }}
                      />
                    ))
                  )}
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-6">
              <SystemStatus
                queueSize={0}
                activeWorkers={health?.status === "ok" ? 1 : 0}
                processingSpeed={stats.completed}
                online={health?.status === "ok"}
              />

              {recentFailures.length > 0 && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-5">
                  <h3 className="text-sm font-semibold text-destructive mb-3">
                    Recent Failures
                  </h3>
                  <div className="flex flex-col gap-3">
                    {recentFailures.map((failure) => (
                      <div key={failure.id}>
                        <p className="truncate text-sm font-medium text-card-foreground">
                          {failure.filename}
                        </p>
                        <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                          {failure.error_message || "The file could not be processed."}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="rounded-xl border border-border bg-card p-5">
                <h3 className="text-sm font-semibold text-card-foreground mb-4">
                  Quick Actions
                </h3>
                <div className="flex flex-col gap-2">
                  <Button className="w-full justify-start gap-2" asChild>
                    <Link href="/upload">
                      <Upload className="h-4 w-4" />
                      Upload CVs
                    </Link>
                  </Button>
                  <Button
                    variant="outline"
                    className="w-full justify-start gap-2"
                    asChild
                  >
                    <Link href="/candidates">
                      <Users className="h-4 w-4" />
                      Browse Candidates
                    </Link>
                  </Button>
                  <Button
                    variant="outline"
                    className="w-full justify-start gap-2"
                    asChild
                  >
                    <Link href="/match">
                      <Search className="h-4 w-4" />
                      Match Job
                    </Link>
                  </Button>
                </div>
              </div>

              <div className="rounded-xl border border-border bg-card p-5">
                <h3 className="text-sm font-semibold text-card-foreground mb-3">
                  Processing Stats
                </h3>
                <div className="flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">
                      Success Rate
                    </span>
                    <span className="text-sm font-medium text-card-foreground">
                      {stats.totalUploads
                        ? successRate
                        : 0}
                      %
                    </span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-success rounded-full"
                      style={{
                        width: `${stats.totalUploads ? (stats.completed / stats.totalUploads) * 100 : 0}%`,
                      }}
                    />
                  </div>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{stats.completed} successful</span>
                    <span>{stats.failed} failed</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
