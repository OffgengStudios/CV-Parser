"use client"

import { FormEvent, use, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { notFound, useRouter } from "next/navigation"
import {
  ArrowLeft,
  Calendar,
  Download,
  Edit3,
  Eye,
  FileText,
  GraduationCap,
  Mail,
  Phone,
  ShieldCheck,
  Trash2,
} from "lucide-react"

import { AppSidebar } from "@/components/app-sidebar"
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useToast } from "@/hooks/use-toast"
import { cn } from "@/lib/utils"
import {
  deleteCandidate,
  fetchCandidate,
  fetchCandidateCvBlob,
  fetchCurrentWorkerProfile,
  updateCandidate,
  type ApiCandidateDetail,
} from "@/lib/api"

type ViewMode = "parsed" | "raw"
type EditValues = {
  name: string
  email: string
  phone: string
  category: string
  subcategory: string
  confidencePercent: string
  yearsExperience: string
  seniorityLevel: string
  skills: string
  experience: string
  education: string
}

function toEditValues(candidate: ApiCandidateDetail): EditValues {
  return {
    name: candidate.name || "",
    email: candidate.email || "",
    phone: candidate.phone || "",
    category: candidate.category || "",
    subcategory: candidate.subcategory || "",
    confidencePercent:
      candidate.confidence == null ? "" : String(Math.round(candidate.confidence * 100)),
    yearsExperience:
      candidate.years_experience == null ? "" : String(candidate.years_experience),
    seniorityLevel: candidate.seniority_level || "",
    skills: candidate.skills.join(", "),
    experience: candidate.experience || "",
    education: candidate.education || "",
  }
}

export default function CandidateDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const router = useRouter()
  const { toast } = useToast()
  const [viewMode, setViewMode] = useState<ViewMode>("parsed")
  const [candidate, setCandidate] = useState<ApiCandidateDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [missing, setMissing] = useState(false)
  const [isAdmin, setIsAdmin] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editValues, setEditValues] = useState<EditValues | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [cvLoading, setCvLoading] = useState<"view" | "download" | null>(null)

  useEffect(() => {
    async function loadCandidate() {
      setLoading(true)
      setMissing(false)
      try {
        const response = await fetchCandidate(id)
        setCandidate(response)
        setEditValues(toEditValues(response))
      } catch {
        setMissing(true)
      } finally {
        setLoading(false)
      }
    }

    loadCandidate()
  }, [id])

  useEffect(() => {
    async function loadWorkerProfile() {
      try {
        const profile = await fetchCurrentWorkerProfile()
        setIsAdmin(profile.is_admin)
      } catch {
        setIsAdmin(false)
      }
    }

    loadWorkerProfile()
  }, [])

  const initials = useMemo(() => {
    const name = candidate?.name || "Unknown Candidate"
    return name
      .split(" ")
      .map((part) => part[0])
      .join("")
      .toUpperCase()
      .slice(0, 2)
  }, [candidate?.name])

  if (missing) {
    notFound()
  }

  async function handleDelete() {
    if (!candidate) return
    setDeleting(true)
    try {
      await deleteCandidate(candidate.id)
      toast({
        title: "Candidate deleted",
        description: `${candidate.name || "Candidate"} was removed successfully.`,
      })
      router.push("/candidates")
    } catch {
      toast({
        title: "Delete failed",
        description: "The candidate could not be removed.",
        variant: "destructive",
      })
    } finally {
      setDeleting(false)
      setConfirmOpen(false)
    }
  }

  function updateEditValue(field: keyof EditValues, value: string) {
    setEditValues((current) => current ? { ...current, [field]: value } : current)
  }

  async function handleSaveCorrections(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!candidate || !editValues) return

    const skills = editValues.skills
      .split(/[\n,]+/)
      .map((skill) => skill.trim())
      .filter(Boolean)
    const confidence = editValues.confidencePercent.trim()
      ? Number(editValues.confidencePercent) / 100
      : null
    const yearsExperience = editValues.yearsExperience.trim()
      ? Number(editValues.yearsExperience)
      : null

    setSaving(true)
    try {
      const updated = await updateCandidate(candidate.id, {
        name: editValues.name,
        email: editValues.email,
        phone: editValues.phone,
        category: editValues.category,
        subcategory: editValues.subcategory,
        confidence,
        years_experience: yearsExperience,
        seniority_level: editValues.seniorityLevel,
        skills,
        experience: editValues.experience,
        education: editValues.education,
      })
      setCandidate(updated)
      setEditValues(toEditValues(updated))
      setEditing(false)
      toast({
        title: "Candidate updated",
        description: "The parsed data correction was saved.",
      })
    } catch {
      toast({
        title: "Correction failed",
        description: "The candidate could not be updated.",
        variant: "destructive",
      })
    } finally {
      setSaving(false)
    }
  }

  async function handleViewCv() {
    if (!candidate) return
    setCvLoading("view")
    try {
      const blob = await fetchCandidateCvBlob(candidate.id)
      const url = URL.createObjectURL(blob)
      const opened = window.open(url, "_blank", "noopener,noreferrer")

      if (!opened) {
        toast({
          title: "CV ready",
          description: "Your browser blocked the new tab. Use Download CV instead.",
        })
        URL.revokeObjectURL(url)
        return
      }

      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch (error) {
      toast({
        title: "CV unavailable",
        description:
          error instanceof Error
            ? "The stored CV file could not be opened."
            : "The stored CV file could not be opened.",
        variant: "destructive",
      })
    } finally {
      setCvLoading(null)
    }
  }

  async function handleDownloadCv() {
    if (!candidate) return
    setCvLoading("download")
    try {
      const blob = await fetchCandidateCvBlob(candidate.id, true)
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")

      link.href = url
      link.download = candidate.source_filename || `${candidate.id}-cv`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    } catch {
      toast({
        title: "Download failed",
        description: "The stored CV file could not be downloaded.",
        variant: "destructive",
      })
    } finally {
      setCvLoading(null)
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <AppSidebar />
      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete candidate?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently remove {candidate?.name || "this candidate"} from the system.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              {deleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <main className="pt-16 lg:pl-64 lg:pt-0">
        <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="mb-6">
            <Link
              href="/candidates"
              className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Candidates
            </Link>
          </div>

          {loading || !candidate ? (
            <div className="text-sm text-muted-foreground">Loading candidate...</div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2 flex flex-col gap-6">
                <div className="rounded-xl border border-border bg-card p-6">
                  <div className="flex items-start gap-5">
                    <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 text-primary text-xl font-semibold">
                      {initials}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-start justify-between">
                        <div>
                          <h1 className="text-2xl font-semibold text-card-foreground">
                            {candidate.name || "Unnamed Candidate"}
                          </h1>
                          <p className="text-muted-foreground mt-0.5">
                            {candidate.subcategory
                              ? `${candidate.category || "Unknown category"} • ${candidate.subcategory}`
                              : candidate.category || "Unknown category"}
                          </p>
                        </div>
                        <div className="flex flex-wrap justify-end gap-2">
                          {isAdmin && (
                            <Button
                              variant={editing ? "secondary" : "outline"}
                              className="gap-2"
                              onClick={() => setEditing((current) => !current)}
                              disabled={saving}
                            >
                              <Edit3 className="h-4 w-4" />
                              {editing ? "Close Editor" : "Edit Parsed Data"}
                            </Button>
                          )}
                          <Button
                            variant="outline"
                            className="gap-2"
                            onClick={handleViewCv}
                            disabled={!candidate.has_cv_file || cvLoading !== null}
                          >
                            <Eye className="h-4 w-4" />
                            {cvLoading === "view" ? "Opening..." : "View CV"}
                          </Button>
                          <Button
                            variant="outline"
                            className="gap-2"
                            onClick={handleDownloadCv}
                            disabled={!candidate.has_cv_file || cvLoading !== null}
                          >
                            <Download className="h-4 w-4" />
                            {cvLoading === "download" ? "Downloading..." : "Download CV"}
                          </Button>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-4 mt-4 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1.5">
                          <Mail className="h-4 w-4" />
                          {candidate.email || "No email"}
                        </span>
                        <span className="flex items-center gap-1.5">
                          <Phone className="h-4 w-4" />
                          {candidate.phone || "No phone"}
                        </span>
                        <span className="flex items-center gap-1.5">
                          <ShieldCheck className="h-4 w-4" />
                          {candidate.confidence != null
                            ? `${Math.round(candidate.confidence * 100)}% confidence`
                            : "No confidence score"}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 p-1 rounded-lg bg-muted w-fit">
                  <button
                    onClick={() => setViewMode("parsed")}
                    className={cn(
                      "flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors",
                      viewMode === "parsed"
                        ? "bg-background text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <Eye className="h-4 w-4" />
                    Parsed Data
                  </button>
                  <button
                    onClick={() => setViewMode("raw")}
                    className={cn(
                      "flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors",
                      viewMode === "raw"
                        ? "bg-background text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <FileText className="h-4 w-4" />
                    Raw View
                  </button>
                </div>

                {isAdmin && editing && editValues ? (
                  <form
                    onSubmit={handleSaveCorrections}
                    className="rounded-xl border border-border bg-card p-6"
                  >
                    <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <h2 className="text-lg font-semibold text-card-foreground">
                        Correct Parsed Data
                      </h2>
                      <div className="flex gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => {
                            setEditValues(toEditValues(candidate))
                            setEditing(false)
                          }}
                          disabled={saving}
                        >
                          Cancel
                        </Button>
                        <Button type="submit" disabled={saving}>
                          {saving ? "Saving..." : "Save Corrections"}
                        </Button>
                      </div>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="grid gap-2">
                        <Label htmlFor="candidate-name">Name</Label>
                        <Input
                          id="candidate-name"
                          value={editValues.name}
                          onChange={(event) => updateEditValue("name", event.target.value)}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="candidate-email">Email</Label>
                        <Input
                          id="candidate-email"
                          type="email"
                          value={editValues.email}
                          onChange={(event) => updateEditValue("email", event.target.value)}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="candidate-phone">Phone</Label>
                        <Input
                          id="candidate-phone"
                          value={editValues.phone}
                          onChange={(event) => updateEditValue("phone", event.target.value)}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="candidate-category">Category</Label>
                        <Input
                          id="candidate-category"
                          value={editValues.category}
                          onChange={(event) => updateEditValue("category", event.target.value)}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="candidate-subcategory">Subcategory</Label>
                        <Input
                          id="candidate-subcategory"
                          value={editValues.subcategory}
                          onChange={(event) => updateEditValue("subcategory", event.target.value)}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="candidate-seniority">Seniority</Label>
                        <Input
                          id="candidate-seniority"
                          value={editValues.seniorityLevel}
                          onChange={(event) => updateEditValue("seniorityLevel", event.target.value)}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="candidate-years">Years experience</Label>
                        <Input
                          id="candidate-years"
                          type="number"
                          min="0"
                          step="0.5"
                          value={editValues.yearsExperience}
                          onChange={(event) => updateEditValue("yearsExperience", event.target.value)}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="candidate-confidence">Confidence percent</Label>
                        <Input
                          id="candidate-confidence"
                          type="number"
                          min="0"
                          max="100"
                          step="1"
                          value={editValues.confidencePercent}
                          onChange={(event) => updateEditValue("confidencePercent", event.target.value)}
                        />
                      </div>
                    </div>

                    <div className="mt-4 grid gap-2">
                      <Label htmlFor="candidate-skills">Skills</Label>
                      <Textarea
                        id="candidate-skills"
                        value={editValues.skills}
                        onChange={(event) => updateEditValue("skills", event.target.value)}
                        rows={3}
                      />
                    </div>
                    <div className="mt-4 grid gap-2">
                      <Label htmlFor="candidate-experience">Experience</Label>
                      <Textarea
                        id="candidate-experience"
                        value={editValues.experience}
                        onChange={(event) => updateEditValue("experience", event.target.value)}
                        rows={6}
                      />
                    </div>
                    <div className="mt-4 grid gap-2">
                      <Label htmlFor="candidate-education">Education</Label>
                      <Textarea
                        id="candidate-education"
                        value={editValues.education}
                        onChange={(event) => updateEditValue("education", event.target.value)}
                        rows={4}
                      />
                    </div>
                  </form>
                ) : viewMode === "parsed" ? (
                  <>
                    <div className="rounded-xl border border-border bg-card p-6">
                      <h2 className="text-lg font-semibold text-card-foreground mb-3">
                        Experience
                      </h2>
                      <p className="text-muted-foreground leading-relaxed whitespace-pre-wrap">
                        {candidate.experience || "No experience section was extracted."}
                      </p>
                    </div>

                    <div className="rounded-xl border border-border bg-card p-6">
                      <h2 className="text-lg font-semibold text-card-foreground mb-4">
                        Education
                      </h2>
                      <div className="flex items-start gap-4">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                          <GraduationCap className="h-5 w-5" />
                        </div>
                        <p className="text-muted-foreground whitespace-pre-wrap">
                          {candidate.education || "No education section was extracted."}
                        </p>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="rounded-xl border border-border bg-card p-6">
                    <h2 className="text-lg font-semibold text-card-foreground mb-4">
                      Raw Candidate Record
                    </h2>
                    <pre className="whitespace-pre-wrap text-sm text-muted-foreground font-mono bg-muted/50 p-4 rounded-lg overflow-x-auto">
{JSON.stringify(candidate, null, 2)}
                    </pre>
                  </div>
                )}
              </div>

              <div className="flex flex-col gap-6">
                <div className="rounded-xl border border-border bg-card p-5">
                  <h3 className="text-sm font-semibold text-card-foreground mb-3">
                    Skills
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {candidate.skills.length > 0 ? (
                      candidate.skills.map((skill) => (
                        <Badge
                          key={skill}
                          variant="secondary"
                          className="text-sm font-normal"
                        >
                          {skill}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-sm text-muted-foreground">
                        No skills extracted.
                      </span>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-border bg-card p-5">
                  <h3 className="text-sm font-semibold text-card-foreground mb-3">
                    Quick Info
                  </h3>
                  <div className="flex flex-col gap-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Category</span>
                      <span className="font-medium text-card-foreground">
                        {candidate.subcategory
                          ? `${candidate.category || "Unknown"} • ${candidate.subcategory}`
                          : candidate.category || "Unknown"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Skills</span>
                      <span className="font-medium text-card-foreground">
                        {candidate.skills.length}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Created</span>
                      <span className="font-medium text-card-foreground inline-flex items-center gap-1.5">
                        <Calendar className="h-3.5 w-3.5" />
                        {new Date(candidate.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Source file</span>
                      <span className="font-medium text-card-foreground text-right">
                        {candidate.source_filename || "Unknown"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Original CV</span>
                      <span className="font-medium text-card-foreground">
                        {candidate.has_cv_file ? "Available" : "Not stored"}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="rounded-xl border border-border bg-card p-5">
                  <h3 className="text-sm font-semibold text-card-foreground mb-3">
                    Actions
                  </h3>
                  <div className="flex flex-col gap-2">
                    <Button
                      variant="outline"
                      className="w-full justify-start gap-2"
                      onClick={handleViewCv}
                      disabled={!candidate.has_cv_file || cvLoading !== null}
                    >
                      <Eye className="h-4 w-4" />
                      {cvLoading === "view" ? "Opening CV..." : "View Original CV"}
                    </Button>
                    <Button
                      variant="destructive"
                      className="w-full justify-start gap-2"
                      onClick={() => setConfirmOpen(true)}
                      disabled={deleting}
                    >
                      <Trash2 className="h-4 w-4" />
                      {deleting ? "Deleting..." : "Delete Candidate"}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
