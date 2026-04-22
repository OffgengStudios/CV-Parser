"use client"

import { useCallback, useState } from "react"
import { cn } from "@/lib/utils"
import { Upload, File, X, CheckCircle2, Loader2, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"

export type FileStatus = "queued" | "processing" | "done" | "failed"

export interface UploadFile {
  id: string
  file: File
  status: FileStatus
  progress: number
  errorMessage?: string
}

interface UploadBoxProps {
  files: UploadFile[]
  onFilesAdd: (files: File[]) => void
  onFileRemove: (id: string) => void
  accept?: string
  maxFiles?: number
  className?: string
}

export function UploadBox({
  files,
  onFilesAdd,
  onFileRemove,
  accept = ".pdf,.docx",
  maxFiles,
  className,
}: UploadBoxProps) {
  const [isDragging, setIsDragging] = useState(false)

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragging(false)
      const droppedFiles = Array.from(e.dataTransfer.files)
      onFilesAdd(droppedFiles)
    },
    [onFilesAdd]
  )

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files) {
        const selectedFiles = Array.from(e.target.files)
        onFilesAdd(selectedFiles)
      }
    },
    [onFilesAdd]
  )

  const getStatusIcon = (status: FileStatus) => {
    switch (status) {
      case "queued":
        return <Loader2 className="h-4 w-4 text-muted-foreground animate-pulse" />
      case "processing":
        return <Loader2 className="h-4 w-4 text-primary animate-spin" />
      case "done":
        return <CheckCircle2 className="h-4 w-4 text-success" />
      case "failed":
        return <AlertCircle className="h-4 w-4 text-destructive" />
    }
  }

  const getStatusText = (status: FileStatus) => {
    switch (status) {
      case "queued":
        return "Queued"
      case "processing":
        return "Processing..."
      case "done":
        return "Done"
      case "failed":
        return "Failed"
    }
  }

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          "relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-12 transition-all",
          isDragging
            ? "border-primary bg-primary/5"
            : "border-border bg-muted/30 hover:border-primary/50 hover:bg-muted/50"
        )}
      >
        <input
          type="file"
          accept={accept}
          multiple
          onChange={handleFileChange}
          className="absolute inset-0 cursor-pointer opacity-0"
          disabled={typeof maxFiles === "number" ? files.length >= maxFiles : false}
        />
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="rounded-full bg-primary/10 p-4">
            <Upload className="h-8 w-8 text-primary" />
          </div>
          <div className="flex flex-col gap-1">
            <p className="text-lg font-medium text-foreground">
              Drop your CVs here
            </p>
            <p className="text-sm text-muted-foreground">
              or click to browse (PDF, DOCX)
            </p>
          </div>
          {typeof maxFiles === "number" ? (
            <p className="text-xs text-muted-foreground">
              Up to {maxFiles} files at once
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">
              Multiple files supported
            </p>
          )}
        </div>
      </div>

      {files.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">
              Uploaded files ({files.length})
            </span>
          </div>
          <div className="flex flex-col gap-2">
            {files.map((uploadFile) => (
              <div
                key={uploadFile.id}
                className={cn(
                  "flex items-center gap-3 rounded-lg border bg-card p-3",
                  uploadFile.status === "failed"
                    ? "border-destructive/50 bg-destructive/5"
                    : "border-border"
                )}
              >
                <div
                  className={cn(
                    "rounded-lg p-2",
                    uploadFile.status === "failed" ? "bg-destructive/10" : "bg-muted"
                  )}
                >
                  <File
                    className={cn(
                      "h-5 w-5",
                      uploadFile.status === "failed"
                        ? "text-destructive"
                        : "text-muted-foreground"
                    )}
                  />
                </div>
                <div className="flex flex-1 flex-col gap-1">
                  <span className="text-sm font-medium text-card-foreground truncate">
                    {uploadFile.file.name}
                  </span>
                  <div className="flex items-center gap-2">
                    {getStatusIcon(uploadFile.status)}
                    <span
                      className={cn(
                        "text-xs",
                        uploadFile.status === "failed"
                          ? "font-medium text-destructive"
                          : "text-muted-foreground"
                      )}
                    >
                      {getStatusText(uploadFile.status)}
                    </span>
                    {uploadFile.status === "processing" && (
                      <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-primary rounded-full transition-all duration-300"
                          style={{ width: `${uploadFile.progress}%` }}
                        />
                      </div>
                    )}
                  </div>
                  {uploadFile.status === "failed" && uploadFile.errorMessage && (
                    <p className="text-xs text-destructive">
                      {uploadFile.errorMessage}
                    </p>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-muted-foreground hover:text-foreground"
                  onClick={() => onFileRemove(uploadFile.id)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
