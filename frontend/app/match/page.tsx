"use client"

import { ChangeEvent, useMemo, useState } from "react"
import Link from "next/link"
import { Download, FileText, Loader2, Search, Upload, X } from "lucide-react"

import { AppSidebar } from "@/components/app-sidebar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useToast } from "@/hooks/use-toast"
import {
  matchJobDescription,
  matchJobDescriptionFile,
  type ApiMatchedCandidate,
} from "@/lib/api"
import { cn } from "@/lib/utils"

function asPercent(value: number) {
  return `${Math.round(value * 100)}%`
}

function getMatchTone(value: number) {
  if (value >= 0.7) {
    return {
      label: "Strong fit",
      card: "border-success/40 bg-success/5",
      badge: "bg-success text-success-foreground hover:bg-success/90",
      bar: "bg-success",
    }
  }

  if (value >= 0.4) {
    return {
      label: "Possible fit",
      card: "border-warning/40 bg-warning/5",
      badge: "bg-warning text-warning-foreground hover:bg-warning/90",
      bar: "bg-warning",
    }
  }

  return {
    label: "Low fit",
    card: "border-border bg-card",
    badge: "",
    bar: "bg-muted-foreground",
  }
}

function escapeCsvCell(value: string | number | null | undefined) {
  const text = value === null || value === undefined ? "" : String(value)
  return `"${text.replace(/"/g, '""')}"`
}

export default function MatchPage() {
  const { toast } = useToast()
  const [jobText, setJobText] = useState("")
  const [jobFile, setJobFile] = useState<File | null>(null)
  const [results, setResults] = useState<ApiMatchedCandidate[]>([])
  const [totalCandidates, setTotalCandidates] = useState(0)
  const [loading, setLoading] = useState(false)

  const canMatch = useMemo(
    () => jobFile || jobText.trim().length >= 50,
    [jobFile, jobText]
  )

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] || null
    setJobFile(file)
    if (file) setJobText("")
  }

  async function runMatch() {
    if (!canMatch) {
      toast({
        title: "Job description needed",
        description: "Add at least 50 characters or upload a PDF/DOCX file.",
        variant: "destructive",
      })
      return
    }

    setLoading(true)
    try {
      const response = jobFile
        ? await matchJobDescriptionFile(jobFile)
        : await matchJobDescription(jobText.trim())

      setResults(response.results)
      setTotalCandidates(response.total_candidates)
      toast({
        title: "Matching complete",
        description: `${response.matched_candidates} candidate(s) ranked.`,
      })
    } catch {
      toast({
        title: "Matching failed",
        description: "The backend could not process this job description.",
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  function downloadMatchedCandidatesSheet() {
    if (results.length === 0) return

    const rows = [
      ["Name", "Phone Number"],
      ...results.map((candidate) => [
        candidate.name || "Unnamed Candidate",
        candidate.phone || "",
      ]),
    ]
    const csv = rows
      .map((row) => row.map((cell) => escapeCsvCell(cell)).join(","))
      .join("\r\n")
    const blob = new Blob([`\ufeff${csv}`], {
      type: "text/csv;charset=utf-8;",
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")

    link.href = url
    link.download = `matched-candidates-${new Date()
      .toISOString()
      .slice(0, 10)}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)

    toast({
      title: "Sheet downloaded",
      description: `${results.length} matched candidate(s) exported.`,
    })
  }

  return (
    <div className="min-h-screen bg-background">
      <AppSidebar />
      <main className="pt-16 lg:pl-64 lg:pt-0">
        <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="mb-8">
            <h1 className="text-2xl font-semibold text-foreground">
              Match Job Description
            </h1>
            <p className="text-muted-foreground mt-1">
              Rank stored candidates against a job description
            </p>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <div className="xl:col-span-1 flex flex-col gap-6">
              <div className="rounded-xl border border-border bg-card p-5">
                <h2 className="text-sm font-semibold text-card-foreground mb-4">
                  Job Description
                </h2>
                <label className="flex min-h-36 cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-muted/30 p-5 text-center transition-colors hover:bg-muted/50">
                  <Upload className="h-7 w-7 text-muted-foreground" />
                  <span className="text-sm font-medium text-card-foreground">
                    {jobFile ? jobFile.name : "Upload PDF or DOCX"}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    The file text will be extracted by the backend
                  </span>
                  <input
                    type="file"
                    accept=".pdf,.docx"
                    className="sr-only"
                    onChange={handleFileChange}
                  />
                </label>

                {jobFile && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-3 gap-2"
                    onClick={() => setJobFile(null)}
                  >
                    <X className="h-4 w-4" />
                    Remove file
                  </Button>
                )}

                <div className="my-5 flex items-center gap-3">
                  <div className="h-px flex-1 bg-border" />
                  <span className="text-xs text-muted-foreground">or paste text</span>
                  <div className="h-px flex-1 bg-border" />
                </div>

                <textarea
                  value={jobText}
                  onChange={(event) => {
                    setJobText(event.target.value)
                    if (event.target.value) setJobFile(null)
                  }}
                  placeholder="Paste the job description here..."
                  className="min-h-56 w-full resize-y rounded-lg border border-input bg-background p-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                />

                <Button
                  className="mt-4 w-full gap-2"
                  onClick={runMatch}
                  disabled={loading || !canMatch}
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4" />
                  )}
                  {loading ? "Matching..." : "Find Best Candidates"}
                </Button>
              </div>
            </div>

            <div className="xl:col-span-2">
              <div className="rounded-xl border border-border bg-card">
                <div className="flex items-center justify-between border-b border-border p-5">
                  <div>
                    <h2 className="text-lg font-semibold text-card-foreground">
                      Ranked Candidates
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      {totalCandidates
                        ? `${results.length} shown from ${totalCandidates} stored candidates`
                        : "Run a match to see ranked results"}
                    </p>
                  </div>
                  {results.length > 0 ? (
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-2"
                      onClick={downloadMatchedCandidatesSheet}
                    >
                      <Download className="h-4 w-4" />
                      Download Sheet
                    </Button>
                  ) : (
                    <FileText className="h-5 w-5 text-muted-foreground" />
                  )}
                </div>

                <div className="divide-y divide-border">
                  {results.length === 0 ? (
                    <div className="flex min-h-72 flex-col items-center justify-center gap-3 p-8 text-center">
                      <div className="rounded-full bg-primary/10 p-4 text-primary">
                        <Search className="h-7 w-7" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-card-foreground">
                          No ranked candidates yet
                        </p>
                        <p className="mt-1 text-sm text-muted-foreground">
                          Add a job description to compare it with stored CVs.
                        </p>
                      </div>
                    </div>
                  ) : (
                    results.map((candidate, index) => {
                      const tone = getMatchTone(candidate.final_score)

                      return (
                        <div
                          key={candidate.candidate_id}
                          className={cn(
                            "m-4 rounded-lg border p-5",
                            index === 0 ? tone.card : "border-border bg-card"
                          )}
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">
                                  #{index + 1}
                                </span>
                                <Link
                                  href={`/candidates/${candidate.candidate_id}`}
                                  className="text-base font-semibold text-card-foreground hover:text-primary"
                                >
                                  {candidate.name || "Unnamed Candidate"}
                                </Link>
                                <Badge
                                  variant={tone.badge ? undefined : "secondary"}
                                  className={tone.badge}
                                >
                                  {tone.label}
                                </Badge>
                              </div>
                              <p className="mt-1 text-sm text-muted-foreground">
                                {candidate.subcategory
                                  ? `${candidate.category || "Unknown"} / ${candidate.subcategory}`
                                  : candidate.category || "Unknown category"}
                              </p>
                            </div>
                            <div className="text-right">
                              <p className="text-2xl font-semibold text-card-foreground">
                                {asPercent(candidate.final_score)}
                              </p>
                              <p className="text-xs text-muted-foreground">match</p>
                            </div>
                          </div>

                          <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
                            <div
                              className={cn("h-full rounded-full", tone.bar)}
                              style={{ width: asPercent(candidate.final_score) }}
                            />
                          </div>

                        <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
                          <div className="rounded-lg bg-muted/50 p-3">
                            <p className="text-muted-foreground">Final</p>
                            <p className="font-semibold text-card-foreground">
                              {asPercent(candidate.final_score)}
                            </p>
                          </div>
                          <div className="rounded-lg bg-muted/50 p-3">
                            <p className="text-muted-foreground">Text similarity</p>
                            <p className="font-semibold text-card-foreground">
                              {asPercent(candidate.similarity_score)}
                            </p>
                          </div>
                          <div className="rounded-lg bg-muted/50 p-3">
                            <p className="text-muted-foreground">Skill match</p>
                            <p className="font-semibold text-card-foreground">
                              {asPercent(candidate.skill_match_score)}
                            </p>
                          </div>
                        </div>

                        <div className="mt-4 flex flex-wrap gap-2">
                          {candidate.matched_skills.length > 0 ? (
                            candidate.matched_skills.map((skill) => (
                              <Badge key={skill} variant="secondary">
                                {skill}
                              </Badge>
                            ))
                          ) : (
                            <span className="text-sm text-muted-foreground">
                              No direct skill overlap found.
                            </span>
                          )}
                        </div>
                      </div>
                    )})
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
