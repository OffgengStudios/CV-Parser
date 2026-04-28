"use client"

import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Calendar,
  ChevronRight,
  Mail,
  Phone,
  Sparkles,
  Trash2,
} from "lucide-react"
import Link from "next/link"

export interface Candidate {
  id: string
  name: string
  email: string
  phone: string
  skills: string[]
  category?: string
  subcategory?: string | null
  confidence?: number | null
  createdAt?: string
  sourceFilename?: string | null
  hasCvFile?: boolean
  duplicateMatch?: string | null
  onDelete?: ((id: string) => void) | undefined
  deleting?: boolean
}

interface CandidateCardProps {
  candidate: Candidate
  className?: string
  selectable?: boolean
  selected?: boolean
  onSelectedChange?: (id: string, selected: boolean) => void
}

export function CandidateCard({
  candidate,
  className,
  selectable = false,
  selected = false,
  onSelectedChange,
}: CandidateCardProps) {
  const initials = candidate.name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2)

  return (
      <div
        className={cn(
          "group flex flex-col gap-4 rounded-lg border border-border bg-card p-4 transition-all hover:border-primary/30 hover:shadow-md sm:flex-row sm:items-center",
          className
        )}
      >
        {selectable && (
          <div className="flex h-12 items-center">
            <Checkbox
              checked={selected}
              disabled={!candidate.hasCvFile}
              onCheckedChange={(checked) =>
                onSelectedChange?.(candidate.id, checked === true)
              }
              aria-label={`Select ${candidate.name}`}
            />
          </div>
        )}
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-semibold">
          {initials}
        </div>
        <div className="flex flex-1 flex-col gap-1.5 min-w-0">
          <Link href={`/candidates/${candidate.id}`} className="block">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-card-foreground truncate">
                {candidate.name}
              </span>
              {candidate.category && (
                <Badge variant="outline" className="text-xs font-normal">
                  {candidate.subcategory
                    ? `${candidate.category} • ${candidate.subcategory}`
                    : candidate.category}
                </Badge>
              )}
              {candidate.duplicateMatch && (
                <Badge variant="destructive" className="text-xs font-normal">
                  Possible duplicate
                </Badge>
              )}
            </div>
          </Link>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <Mail className="h-3.5 w-3.5" />
              <span className="truncate max-w-[180px]">{candidate.email}</span>
            </span>
            <span className="flex items-center gap-1.5 hidden md:flex">
              <Phone className="h-3.5 w-3.5" />
              {candidate.phone}
            </span>
            {candidate.confidence != null && (
              <span className="flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5" />
                {Math.round(candidate.confidence * 100)}% confidence
              </span>
            )}
            {candidate.createdAt && (
              <span className="flex items-center gap-1.5 hidden xl:flex">
                <Calendar className="h-3.5 w-3.5" />
                {new Date(candidate.createdAt).toLocaleDateString()}
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5 mt-1">
            {candidate.skills.slice(0, 4).map((skill) => (
              <Badge
                key={skill}
                variant="secondary"
                className="text-xs font-normal"
              >
                {skill}
              </Badge>
            ))}
            {candidate.skills.length > 4 && (
              <Badge variant="outline" className="text-xs font-normal">
                +{candidate.skills.length - 4}
              </Badge>
            )}
            {candidate.sourceFilename && (
              <Badge variant="outline" className="max-w-full truncate text-xs font-normal">
                {candidate.sourceFilename}
              </Badge>
            )}
            {candidate.duplicateMatch && (
              <Badge variant="outline" className="text-xs font-normal text-destructive">
                Same {candidate.duplicateMatch}
              </Badge>
            )}
          </div>
        </div>
        <div className="flex w-full items-center justify-end gap-2 sm:w-auto">
          {candidate.onDelete && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => candidate.onDelete?.(candidate.id)}
              disabled={candidate.deleting}
              aria-label={`Delete ${candidate.name}`}
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          )}
          <Link href={`/candidates/${candidate.id}`}>
            <ChevronRight className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors" />
          </Link>
        </div>
      </div>
  )
}
