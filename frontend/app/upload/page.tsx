"use client"

import { useCallback, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { AlertCircle, CheckCircle2, FileText, Loader2 } from "lucide-react"

import { AppSidebar } from "@/components/app-sidebar"
import {
  UploadBox,
  type FileStatus,
  type UploadFile,
} from "@/components/upload-box"
import { SystemStatus } from "@/components/system-status"
import { Button } from "@/components/ui/button"
import { useToast } from "@/hooks/use-toast"
import { getApiErrorMessage, uploadCvFiles, type ApiUploadError } from "@/lib/api"

function formatUploadError(error: string): string {
  const lower = error.toLowerCase()

  if (lower.includes("unsupported file type")) {
    return "This file type is not supported. Please upload a PDF or DOCX file."
  }

  if (lower.includes("file too large")) {
    return "This file is too large. Please upload a file under the configured size limit."
  }

  if (lower.includes("no extractable text")) {
    return "No readable text was found. The file may be scanned, image-only, blank, or protected."
  }

  if (lower.includes("could not read pdf")) {
    return "The PDF could not be read. It may be damaged, encrypted, or image-only."
  }

  if (lower.includes("could not read docx")) {
    return "The Word document could not be read. It may be damaged or password-protected."
  }

  if (lower.includes("processing failed")) {
    return "The parser could not finish processing this file. Please check the document content and try again."
  }

  return error || "The backend could not process this file."
}

function summarizeUploadErrors(errors: ApiUploadError[]): string {
  if (errors.length === 0) return ""

  const readableErrors = errors.map(
    (error, index) =>
      `${index + 1}. ${error.filename} failed: ${formatUploadError(error.error)}`
  )

  return readableErrors.join("\n")
}

export default function UploadPage() {
  const { toast } = useToast()
  const router = useRouter()
  const [files, setFiles] = useState<UploadFile[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [lastResult, setLastResult] = useState<{
    total: number
    success: number
    failure: number
  } | null>(null)

  const handleFilesAdd = useCallback((newFiles: File[]) => {
    const uploadFiles: UploadFile[] = newFiles.map((file) => ({
      id: crypto.randomUUID(),
      file,
      status: "queued" as FileStatus,
      progress: 0,
    }))
    setFiles((prev) => [...prev, ...uploadFiles])
  }, [])

  const handleFileRemove = useCallback((id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id))
  }, [])

  const removeFailedFiles = useCallback(() => {
    setFiles((prev) => prev.filter((file) => file.status !== "failed"))
  }, [])

  const uploadNow = useCallback(async () => {
    if (!files.length) return
    const pendingFiles = files.filter((file) => file.status !== "done")
    if (!pendingFiles.length) return

    setIsUploading(true)
    setFiles((prev) =>
      prev.map((file) =>
        file.status === "done"
          ? file
          : { ...file, status: "queued", progress: 0, errorMessage: undefined }
      )
    )

    try {
      let successCount = 0
      let failureCount = 0
      const uploadErrors: ApiUploadError[] = []

      for (const uploadFile of pendingFiles) {
        setFiles((prev) =>
          prev.map((file) =>
            file.id === uploadFile.id
              ? { ...file, status: "processing", progress: 50, errorMessage: undefined }
              : file
          )
        )

        try {
          const response = await uploadCvFiles([uploadFile.file])
          const uploadError = response.errors[0]

          if (response.success_count > 0 && response.results.length > 0) {
            successCount += 1
            setFiles((prev) =>
              prev.map((file) =>
                file.id === uploadFile.id
                  ? { ...file, status: "done", progress: 100, errorMessage: undefined }
                  : file
              )
            )
            continue
          }

          const rawError =
            uploadError?.error || "The backend did not return a result for this file."
          const errorMessage = formatUploadError(rawError)
          failureCount += 1
          uploadErrors.push({
            filename: uploadFile.file.name,
            error: rawError,
            message: uploadError?.message || "CV processing failed.",
          })
          setFiles((prev) =>
            prev.map((file) =>
              file.id === uploadFile.id
                ? { ...file, status: "failed", progress: 100, errorMessage }
                : file
            )
          )
        } catch (error) {
          const message = getApiErrorMessage(error)
          failureCount += 1
          uploadErrors.push({
            filename: uploadFile.file.name,
            error: message,
            message: "CV processing failed.",
          })
          setFiles((prev) =>
            prev.map((file) =>
              file.id === uploadFile.id
                ? { ...file, status: "failed", progress: 100, errorMessage: message }
                : file
            )
          )
        }
      }

      setLastResult({
        total: pendingFiles.length,
        success: successCount,
        failure: failureCount,
      })

      toast({
        title:
          failureCount > 0
            ? "Some uploads failed"
            : "Upload complete",
        description:
          failureCount > 0
            ? summarizeUploadErrors(uploadErrors)
            : `${successCount} file(s) processed successfully.`,
        variant: failureCount > 0 ? "destructive" : undefined,
      })
    } finally {
      setIsUploading(false)
    }
  }, [files, toast])

  const queuedCount = useMemo(
    () => files.filter((f) => f.status === "queued").length,
    [files]
  )
  const processingCount = useMemo(
    () => files.filter((f) => f.status === "processing").length,
    [files]
  )
  const doneCount = useMemo(
    () => files.filter((f) => f.status === "done").length,
    [files]
  )
  const errorCount = useMemo(
    () => files.filter((f) => f.status === "failed").length,
    [files]
  )
  const failedFiles = useMemo(
    () => files.filter((file) => file.status === "failed"),
    [files]
  )

  return (
    <div className="min-h-screen bg-background">
      <AppSidebar />
      <main className="pt-16 lg:pl-64 lg:pt-0">
        <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="mb-8">
            <h1 className="text-2xl font-semibold text-foreground">Upload CVs</h1>
            <p className="text-muted-foreground mt-1">
              Send PDF or DOCX files to the FastAPI backend for parsing
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <UploadBox
                files={files}
                onFilesAdd={handleFilesAdd}
                onFileRemove={handleFileRemove}
              />

              <div className="mt-6 flex items-center gap-3">
                <Button
                  onClick={uploadNow}
                  disabled={!files.length || isUploading}
                >
                  {isUploading ? "Uploading..." : "Start Processing"}
                </Button>
                {lastResult && (
                  <span className="text-sm text-muted-foreground">
                    {lastResult.success} succeeded, {lastResult.failure} failed
                  </span>
                )}
              </div>

              {files.length > 0 && (
                <div className="mt-6 rounded-xl border border-border bg-card p-5">
                  <h3 className="text-sm font-semibold text-card-foreground mb-4">
                    Processing Summary
                  </h3>
                  <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                    <div className="flex flex-col items-center gap-1 p-3 rounded-lg bg-muted/50">
                      <Loader2 className="h-5 w-5 text-muted-foreground animate-pulse" />
                      <span className="text-lg font-semibold text-card-foreground">
                        {queuedCount}
                      </span>
                      <span className="text-xs text-muted-foreground">Queued</span>
                    </div>
                    <div className="flex flex-col items-center gap-1 p-3 rounded-lg bg-primary/10">
                      <Loader2 className="h-5 w-5 text-primary animate-spin" />
                      <span className="text-lg font-semibold text-card-foreground">
                        {processingCount}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        Processing
                      </span>
                    </div>
                    <div className="flex flex-col items-center gap-1 p-3 rounded-lg bg-success/10">
                      <CheckCircle2 className="h-5 w-5 text-success" />
                      <span className="text-lg font-semibold text-card-foreground">
                        {doneCount}
                      </span>
                      <span className="text-xs text-muted-foreground">Done</span>
                    </div>
                    <div className="flex flex-col items-center gap-1 p-3 rounded-lg bg-destructive/10">
                      <AlertCircle className="h-5 w-5 text-destructive" />
                      <span className="text-lg font-semibold text-card-foreground">
                        {errorCount}
                      </span>
                      <span className="text-xs text-muted-foreground">Failed</span>
                    </div>
                  </div>

                  {failedFiles.length > 0 && (
                    <div className="mt-5 rounded-lg border border-destructive/30 bg-destructive/5 p-4">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <h4 className="text-sm font-semibold text-destructive">
                          Failed files
                        </h4>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:text-destructive"
                          onClick={removeFailedFiles}
                        >
                          Remove failed
                        </Button>
                      </div>
                      <div className="flex flex-col gap-3">
                        {failedFiles.map((file) => (
                          <div
                            key={file.id}
                            className="rounded-md border border-destructive/20 bg-background/60 p-3 text-sm"
                          >
                            <p className="font-medium text-card-foreground">
                              {file.file.name}
                            </p>
                            <p className="mt-0.5 text-xs text-muted-foreground">
                              {file.errorMessage || "The backend could not process this file."}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {doneCount > 0 && (
                    <div className="mt-4 flex justify-end">
                      <Button onClick={() => router.push("/candidates?refresh=true")}>
                        View Parsed Candidates
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="flex flex-col gap-6">
              <SystemStatus
                queueSize={queuedCount}
                activeWorkers={processingCount > 0 ? 1 : 0}
                processingSpeed={doneCount}
              />

              <div className="rounded-xl border border-border bg-card p-5">
                <h3 className="text-sm font-semibold text-card-foreground mb-3">
                  Supported Formats
                </h3>
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-3 text-sm">
                    <div className="rounded-lg bg-muted p-2">
                      <FileText className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="font-medium text-card-foreground">PDF</p>
                      <p className="text-xs text-muted-foreground">
                        Portable Document Format
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <div className="rounded-lg bg-muted p-2">
                      <FileText className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="font-medium text-card-foreground">DOCX</p>
                      <p className="text-xs text-muted-foreground">
                        Microsoft Word Document
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-border bg-card p-5">
                <h3 className="text-sm font-semibold text-card-foreground mb-3">
                  Tips
                </h3>
                <ul className="flex flex-col gap-2 text-sm text-muted-foreground">
                  <li className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    Multiple file batches are supported
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    Files are parsed by the FastAPI backend
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    Successful uploads are stored and can sync to Google Sheets
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    Max file size per CV: 10MB
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
