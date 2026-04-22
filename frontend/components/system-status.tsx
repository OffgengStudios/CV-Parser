"use client"

import { cn } from "@/lib/utils"
import { Server, Zap, Clock } from "lucide-react"

interface SystemStatusProps {
  queueSize: number
  activeWorkers: number
  processingSpeed: number
  online?: boolean
  className?: string
}

export function SystemStatus({
  queueSize,
  activeWorkers,
  processingSpeed,
  online = true,
  className,
}: SystemStatusProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card p-5",
        className
      )}
    >
      <div className="flex items-center gap-2 mb-4">
        <div
          className={cn(
            "flex h-2 w-2 rounded-full",
            online ? "bg-success animate-pulse" : "bg-destructive"
          )}
        />
        <span className="text-sm font-medium text-card-foreground">
          {online ? "System Online" : "System Offline"}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Clock className="h-4 w-4" />
            <span className="text-xs">Queue</span>
          </div>
          <span className="text-lg font-semibold text-card-foreground">
            {queueSize}
          </span>
        </div>
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Server className="h-4 w-4" />
            <span className="text-xs">Workers</span>
          </div>
          <span className="text-lg font-semibold text-card-foreground">
            {activeWorkers}
          </span>
        </div>
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Zap className="h-4 w-4" />
            <span className="text-xs">Speed</span>
          </div>
          <span className="text-lg font-semibold text-card-foreground">
            {processingSpeed}/min
          </span>
        </div>
      </div>
    </div>
  )
}
