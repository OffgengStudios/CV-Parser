"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { AlertTriangle, Download, Search, Trash2, Users, X } from "lucide-react"

import { AppSidebar } from "@/components/app-sidebar"
import { CandidateCard, type Candidate } from "@/components/candidate-card"
import { DeleteCandidateDialog } from "@/components/delete-candidate-dialog"
import { EmptyState } from "@/components/empty-state"
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
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useToast } from "@/hooks/use-toast"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  deleteCandidate,
  deleteDuplicateCandidates,
  downloadCandidateCvZip,
  fetchAllCandidates,
  fetchDuplicateCandidates,
  getApiErrorMessage,
  type ApiDuplicateCandidateGroup,
} from "@/lib/api"

export const dynamic = "force-dynamic"

type SortOption = "recent" | "name" | "confidence"

const categories = [
  "Management",
  "Business & Finance",
  "Information Technology (IT)",
  "Engineering",
  "Healthcare",
  "Education",
  "Legal",
  "Arts & Media",
  "Sales",
  "Marketing",
  "Administration & Operations",
  "Agriculture",
  "Skilled Trades",
  "Manufacturing",
  "Transport & Logistics",
  "Hospitality & Tourism",
  "Security & Protective Services",
  "Social Services",
]

export default function CandidatesPage() {
  const { toast } = useToast()
  const [refreshParam, setRefreshParam] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedCategory, setSelectedCategory] = useState<string>("")
  const [sortBy, setSortBy] = useState<SortOption>("recent")
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [duplicateGroups, setDuplicateGroups] = useState<ApiDuplicateCandidateGroup[]>([])
  const [loading, setLoading] = useState(true)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<Candidate | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<Set<string>>(
    () => new Set()
  )
  const [zipName, setZipName] = useState("selected-cvs")
  const [downloadingZip, setDownloadingZip] = useState(false)
  const [confirmDuplicateDeleteOpen, setConfirmDuplicateDeleteOpen] = useState(false)
  const [deletingDuplicates, setDeletingDuplicates] = useState(false)

  // Get refresh param from URL on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search)
      setRefreshParam(params.get("refresh"))
    }
  }, [])

  useEffect(() => {
    loadCandidates()
  }, [selectedCategory, refreshParam, reloadKey])

  async function loadCandidates() {
    setLoading(true)
    try {
      const response = await fetchAllCandidates(selectedCategory || undefined)
      let duplicates: ApiDuplicateCandidateGroup[] = []

      try {
        const duplicatesResponse = await fetchDuplicateCandidates()
        duplicates = duplicatesResponse.groups
      } catch (error) {
        setDuplicateGroups([])
        toast({
          title: "Duplicate check unavailable",
          description: getApiErrorMessage(error),
          variant: "destructive",
        })
      }

      setDuplicateGroups(duplicates)
      const duplicateById = new Map<string, string>()
      duplicates.forEach((group) => {
        group.candidates.forEach((candidate) => {
          duplicateById.set(candidate.id, group.match_type)
        })
      })
      setCandidates(
        response.candidates.map((candidate) => ({
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
          hasCvFile: candidate.has_cv_file,
          duplicateMatch: duplicateById.get(candidate.id) || null,
        }))
      )
    } catch (error) {
      setCandidates([])
      toast({
        title: "Could not load candidates",
        description: getApiErrorMessage(error),
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  async function handleDeleteCandidate(id: string) {
    const target = candidates.find((candidate) => candidate.id === id)
    if (!target) return
    setPendingDelete(target)
  }

  function handleDeleteDuplicate(candidate: ApiDuplicateCandidateGroup["candidates"][number]) {
    setPendingDelete({
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
      hasCvFile: candidate.has_cv_file,
    })
  }

  async function confirmDeleteCandidate() {
    if (!pendingDelete) return
    setDeletingId(pendingDelete.id)
    try {
      await deleteCandidate(pendingDelete.id)
      setCandidates((prev) =>
        prev.filter((candidate) => candidate.id !== pendingDelete.id)
      )
      setDuplicateGroups((prev) =>
        prev
          .map((group) => ({
            ...group,
            candidates: group.candidates.filter(
              (candidate) => candidate.id !== pendingDelete.id
            ),
          }))
          .filter((group) => group.candidates.length > 1)
      )
      toast({
        title: "Candidate deleted",
        description: `${pendingDelete.name} was removed successfully.`,
      })
      setPendingDelete(null)
      setReloadKey((key) => key + 1)
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

  async function confirmDeleteReviewedDuplicates() {
    setDeletingDuplicates(true)
    try {
      const result = await deleteDuplicateCandidates()
      const deletedIds = new Set(result.deleted_candidate_ids)
      setCandidates((prev) => prev.filter((candidate) => !deletedIds.has(candidate.id)))
      setDuplicateGroups([])
      setSelectedCandidateIds((prev) => {
        const next = new Set(prev)
        deletedIds.forEach((id) => next.delete(id))
        return next
      })
      setConfirmDuplicateDeleteOpen(false)
      setReloadKey((key) => key + 1)
      toast({
        title: "Duplicates deleted",
        description: `${result.deleted_count} duplicate candidate${result.deleted_count === 1 ? "" : "s"} removed. Newest records were kept.`,
      })
    } catch (error) {
      toast({
        title: "Duplicate delete failed",
        description: getApiErrorMessage(error),
        variant: "destructive",
      })
    } finally {
      setDeletingDuplicates(false)
    }
  }

  const filteredCandidates = useMemo(() => {
    let result = [...candidates]

    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(
        (candidate) =>
          candidate.name.toLowerCase().includes(query) ||
          candidate.email.toLowerCase().includes(query) ||
          (candidate.category || "").toLowerCase().includes(query)
      )
    }

    switch (sortBy) {
      case "name":
        result.sort((a, b) => a.name.localeCompare(b.name))
        break
      case "confidence":
        result.sort((a, b) => (b.confidence || 0) - (a.confidence || 0))
        break
      case "recent":
      default:
        result.sort(
          (a, b) =>
            new Date(b.createdAt || 0).getTime() -
            new Date(a.createdAt || 0).getTime()
        )
        break
    }

    return result
  }, [candidates, searchQuery, sortBy])

  useEffect(() => {
    const availableIds = new Set(
      candidates
        .filter((candidate) => candidate.hasCvFile)
        .map((candidate) => candidate.id)
    )
    setSelectedCandidateIds((prev) => {
      const next = new Set([...prev].filter((id) => availableIds.has(id)))
      return next.size === prev.size ? prev : next
    })
  }, [candidates])

  const clearFilters = () => {
    setSearchQuery("")
    setSelectedCategory("")
    setSortBy("recent")
  }

  const hasActiveFilters =
    searchQuery.length > 0 || selectedCategory.length > 0 || sortBy !== "recent"
  const duplicateCandidateIds = useMemo(() => {
    const ids = new Set<string>()
    duplicateGroups.forEach((group) => {
      group.candidates.forEach((candidate) => ids.add(candidate.id))
    })
    return ids
  }, [duplicateGroups])
  const visibleDownloadableCandidates = useMemo(
    () => filteredCandidates.filter((candidate) => candidate.hasCvFile),
    [filteredCandidates]
  )
  const selectedCount = selectedCandidateIds.size
  const allVisibleSelected =
    visibleDownloadableCandidates.length > 0 &&
    visibleDownloadableCandidates.every((candidate) =>
      selectedCandidateIds.has(candidate.id)
    )

  function handleCandidateSelection(id: string, selected: boolean) {
    setSelectedCandidateIds((prev) => {
      const next = new Set(prev)
      if (selected) {
        next.add(id)
      } else {
        next.delete(id)
      }
      return next
    })
  }

  function toggleVisibleSelection() {
    setSelectedCandidateIds((prev) => {
      const next = new Set(prev)
      if (allVisibleSelected) {
        visibleDownloadableCandidates.forEach((candidate) => next.delete(candidate.id))
      } else {
        visibleDownloadableCandidates.forEach((candidate) => next.add(candidate.id))
      }
      return next
    })
  }

  async function downloadSelectedCvs() {
    if (selectedCount === 0) return
    setDownloadingZip(true)
    try {
      const blob = await downloadCandidateCvZip([...selectedCandidateIds], zipName)
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      const safeName = zipName.trim().replace(/\.zip$/i, "") || "selected-cvs"
      link.download = `${safeName}.zip`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      toast({
        title: "CV zip downloaded",
        description: `${selectedCount} selected CV file${selectedCount === 1 ? "" : "s"} downloaded.`,
      })
    } catch (error) {
      toast({
        title: "Download failed",
        description: getApiErrorMessage(error),
        variant: "destructive",
      })
    } finally {
      setDownloadingZip(false)
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <AppSidebar />
      <DeleteCandidateDialog
        candidate={pendingDelete}
        deleting={!!deletingId}
        onConfirm={confirmDeleteCandidate}
        onCancel={() => setPendingDelete(null)}
      />
      <AlertDialog
        open={confirmDuplicateDeleteOpen}
        onOpenChange={setConfirmDuplicateDeleteOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete reviewed duplicates?</AlertDialogTitle>
            <AlertDialogDescription>
              This will keep the newest candidate in each duplicate group and permanently remove the older duplicate records.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deletingDuplicates}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDeleteReviewedDuplicates}
              disabled={deletingDuplicates}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              {deletingDuplicates ? "Deleting..." : "Delete duplicates"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <main className="pt-16 lg:pl-64 lg:pt-0">
        <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="mb-8">
            <h1 className="text-2xl font-semibold text-foreground">
              Candidates
            </h1>
            <p className="text-muted-foreground mt-1">
              Browse candidates parsed by the FastAPI backend
            </p>
          </div>

          {duplicateGroups.length > 0 && (
            <div className="mb-6 rounded-lg border border-warning/40 bg-warning/5 p-5">
              <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex gap-3">
                  <div className="mt-0.5 rounded-full bg-warning/20 p-2 text-warning-foreground">
                    <AlertTriangle className="h-5 w-5" />
                  </div>
                  <div>
                    <h2 className="text-sm font-semibold text-card-foreground">
                      Possible duplicates found
                    </h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {duplicateCandidateIds.size} candidate records appear in{" "}
                      {duplicateGroups.length} duplicate group
                      {duplicateGroups.length === 1 ? "" : "s"}.
                    </p>
                  </div>
                </div>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setConfirmDuplicateDeleteOpen(true)}
                  disabled={deletingDuplicates}
                  className="gap-2"
                >
                  <Trash2 className="h-4 w-4" />
                  Delete reviewed duplicates
                </Button>
              </div>
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                {duplicateGroups.slice(0, 4).map((group) => (
                  <div
                    key={`${group.match_type}:${group.match_value}`}
                    className="rounded-md border border-border bg-background/70 p-3"
                  >
                    <p className="text-xs font-medium uppercase text-muted-foreground">
                      Same {group.match_type}
                    </p>
                    <p className="mt-0.5 truncate text-sm font-semibold text-card-foreground">
                      {group.match_value}
                    </p>
                    <div className="mt-3 flex flex-col gap-2">
                      {group.candidates.map((candidate) => (
                        <div
                          key={candidate.id}
                          className="flex items-center justify-between gap-3 rounded-md px-2 py-1.5 text-sm hover:bg-muted"
                        >
                          <Link
                            href={`/candidates/${candidate.id}`}
                            className="min-w-0 flex-1"
                          >
                            <span className="block truncate">
                              {candidate.name || "Unnamed Candidate"}
                            </span>
                            <span className="block text-xs text-muted-foreground">
                              {new Date(candidate.created_at).toLocaleDateString()}
                            </span>
                          </Link>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => handleDeleteDuplicate(candidate)}
                            disabled={deletingId === candidate.id}
                            aria-label={`Delete duplicate ${candidate.name || "candidate"}`}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              {duplicateGroups.length > 4 && (
                <p className="mt-3 text-xs text-muted-foreground">
                  Showing 4 of {duplicateGroups.length} duplicate groups.
                </p>
              )}
            </div>
          )}

          <div className="mb-6 flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search by name, email, or category..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-lg border border-input bg-background py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>

              <Select value={selectedCategory || "all"} onValueChange={(value) => setSelectedCategory(value === "all" ? "" : value)}>
                <SelectTrigger className="w-[260px]">
                  <SelectValue placeholder="Category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Categories</SelectItem>
                  {categories.map((category) => (
                    <SelectItem key={category} value={category}>
                      {category}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={sortBy} onValueChange={(value) => setSortBy(value as SortOption)}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Sort by" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="recent">Most Recent</SelectItem>
                  <SelectItem value="confidence">Confidence</SelectItem>
                  <SelectItem value="name">Name (A-Z)</SelectItem>
                </SelectContent>
              </Select>

              {hasActiveFilters && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearFilters}
                  className="gap-1 text-muted-foreground"
                >
                  <X className="h-4 w-4" />
                  Clear
                </Button>
              )}
            </div>
          </div>

          <div className="mb-4 text-sm text-muted-foreground">
            Showing {filteredCandidates.length} candidate
            {filteredCandidates.length === 1 ? "" : "s"}
          </div>

          <div className="mb-4 flex flex-col gap-3 rounded-lg border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={toggleVisibleSelection}
                disabled={visibleDownloadableCandidates.length === 0}
              >
                {allVisibleSelected ? "Clear visible" : "Select visible"}
              </Button>
              <span className="text-sm text-muted-foreground">
                {selectedCount} selected
              </span>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <Input
                value={zipName}
                onChange={(event) => setZipName(event.target.value)}
                placeholder="Zip file name"
                className="sm:w-56"
                aria-label="Zip file name"
              />
              <Button
                onClick={downloadSelectedCvs}
                disabled={selectedCount === 0 || downloadingZip}
                className="gap-2"
              >
                <Download className="h-4 w-4" />
                {downloadingZip ? "Preparing..." : "Download zip"}
              </Button>
            </div>
          </div>

          {loading ? (
            <div className="text-sm text-muted-foreground">Loading candidates...</div>
          ) : filteredCandidates.length === 0 ? (
            <EmptyState
              icon={<Users className="h-8 w-8 text-muted-foreground" />}
              title="No candidates found"
              description="Try uploading a CV or adjusting your filters."
              action={{
                label: "Clear Filters",
                onClick: clearFilters,
              }}
            />
          ) : (
            <div className="flex flex-col gap-3">
              {filteredCandidates.map((candidate) => (
                <CandidateCard
                  key={candidate.id}
                  candidate={{
                    ...candidate,
                    onDelete: handleDeleteCandidate,
                    deleting: deletingId === candidate.id,
                  }}
                  selectable
                  selected={selectedCandidateIds.has(candidate.id)}
                  onSelectedChange={handleCandidateSelection}
                />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
