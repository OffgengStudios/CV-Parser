"use client"

import { cn } from "@/lib/utils"

interface SkeletonCardProps {
  className?: string
}

export function SkeletonCard({ className }: SkeletonCardProps) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-card p-6 animate-pulse",
        className
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-2">
          <div className="h-4 w-24 rounded bg-muted" />
          <div className="h-8 w-16 rounded bg-muted" />
          <div className="h-3 w-32 rounded bg-muted" />
        </div>
        <div className="h-10 w-10 rounded-lg bg-muted" />
      </div>
    </div>
  )
}

export function SkeletonCandidateCard({ className }: SkeletonCardProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-4 rounded-xl border border-border bg-card p-4 animate-pulse",
        className
      )}
    >
      <div className="h-12 w-12 rounded-full bg-muted" />
      <div className="flex flex-1 flex-col gap-2">
        <div className="h-5 w-32 rounded bg-muted" />
        <div className="flex gap-4">
          <div className="h-4 w-40 rounded bg-muted" />
          <div className="h-4 w-24 rounded bg-muted" />
        </div>
        <div className="flex gap-2">
          <div className="h-5 w-16 rounded bg-muted" />
          <div className="h-5 w-16 rounded bg-muted" />
          <div className="h-5 w-16 rounded bg-muted" />
        </div>
      </div>
    </div>
  )
}

export function SkeletonTable({ rows = 5, className }: SkeletonCardProps & { rows?: number }) {
  return (
    <div className={cn("rounded-xl border border-border bg-card overflow-hidden animate-pulse", className)}>
      <div className="border-b border-border p-4">
        <div className="flex gap-4">
          <div className="h-4 w-32 rounded bg-muted" />
          <div className="h-4 w-48 rounded bg-muted" />
          <div className="h-4 w-24 rounded bg-muted" />
          <div className="h-4 w-32 rounded bg-muted" />
        </div>
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="border-b border-border p-4 last:border-0">
          <div className="flex gap-4">
            <div className="h-4 w-32 rounded bg-muted" />
            <div className="h-4 w-48 rounded bg-muted" />
            <div className="h-4 w-24 rounded bg-muted" />
            <div className="h-4 w-32 rounded bg-muted" />
          </div>
        </div>
      ))}
    </div>
  )
}
