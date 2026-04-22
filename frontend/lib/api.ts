export interface ApiCandidateListItem {
  id: string
  name: string | null
  email: string | null
  phone: string | null
  category: string | null
  subcategory: string | null
  confidence: number | null
  skills: string[]
  skills_count: number
  source_filename: string | null
  created_at: string
}

export interface ApiCandidateDetail {
  id: string
  name: string | null
  email: string | null
  phone: string | null
  skills: string[]
  experience: string | null
  education: string | null
  category: string | null
  subcategory: string | null
  confidence: number | null
  source_filename: string | null
  has_cv_file: boolean
  created_at: string
}

export interface ApiCandidateListResponse {
  total: number
  limit: number
  offset: number
  candidates: ApiCandidateListItem[]
}

export interface ApiDuplicateCandidateGroup {
  match_type: string
  match_value: string
  candidates: ApiCandidateListItem[]
}

export interface ApiDuplicateCandidateGroupsResponse {
  total_groups: number
  total_candidates: number
  groups: ApiDuplicateCandidateGroup[]
}

export interface ApiUploadLog {
  id: number
  filename: string
  status: string
  candidate_id: string | null
  file_size_bytes: number | null
  error_message: string | null
  created_at: string
}

export interface ApiActivityLog {
  id: number
  worker: string
  action: string
  target_type: string | null
  target_id: string | null
  target_label: string | null
  status: string
  details: string | null
  created_at: string
}

export interface ApiHealth {
  status: string
  version: string
  database: string
}

export interface ApiSettingsStatus {
  backend_url_hint: string
  google_sheets_configured: boolean
  google_service_account_file_present: boolean
  google_sheets_tab_name: string
  google_sheets_spreadsheet_id: string | null
}

export interface ApiWorkerUser {
  username: string
  full_name: string | null
  is_admin: boolean
  is_active: boolean
  created_by: string | null
}

export interface ApiMatchedCandidate {
  candidate_id: string
  name: string | null
  email: string | null
  phone: string | null
  skills: string[]
  category: string | null
  subcategory: string | null
  similarity_score: number
  skill_match_score: number
  final_score: number
  matched_skills: string[]
}

export interface ApiJobMatchResponse {
  total_candidates: number
  matched_candidates: number
  results: ApiMatchedCandidate[]
}

export interface ApiUploadResult {
  candidate_id: string
  filename: string
  name: string | null
  email: string | null
  phone: string | null
  category: string
  subcategory: string | null
  confidence: number
  skills_extracted: number
  message: string
}

export interface ApiUploadError {
  filename: string
  error: string
  message: string
}

export interface ApiUploadBatchResponse {
  total_files: number
  success_count: number
  failure_count: number
  results: ApiUploadResult[]
  errors: ApiUploadError[]
}

function normalizeApiBaseUrl(value: string | undefined): string {
  const configuredUrl = value?.trim().replace(/\/$/, "")
  const renderBackendUrl = "https://cv-parser-backend-ggl7.onrender.com"
  const isRenderFrontend =
    typeof window !== "undefined" &&
    window.location.hostname.endsWith(".onrender.com")

  if (isRenderFrontend) {
    return renderBackendUrl
  }

  const fallbackUrl =
    configuredUrl || "http://127.0.0.1:8000"
  const baseUrl = fallbackUrl

  if (baseUrl.startsWith("http://") || baseUrl.startsWith("https://")) {
    return baseUrl
  }
  return `https://${baseUrl}`
}

const API_BASE_URL = normalizeApiBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL)

let accessToken: string | null = null
const TOKEN_STORAGE_KEY = "cvparser_access_token"
const WORKER_STORAGE_KEY = "cvparser_worker"

export class ApiRequestError extends Error {
  status: number
  path: string
  detail: string | null

  constructor(path: string, status: number, detail?: string | null) {
    super(`API request failed: ${status}`)
    this.name = "ApiRequestError"
    this.status = status
    this.path = path
    this.detail = detail || null
  }
}

export function getApiErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.path === "/api/v1/login" && error.status === 401) {
      return "Username or password is incorrect."
    }

    if (error.status === 401 || error.status === 403) {
      return "You are not authorized to access this data. Please restart the app or sign in again."
    }

    if (error.status === 404) {
      return "That backend feature is not available yet. Restart the backend so the latest routes are loaded."
    }

    if (error.detail) {
      return error.detail
    }

    if (error.status >= 500) {
      return "The backend had a problem while handling this request. Please check the backend terminal."
    }

    return `The backend could not complete this request. Status code: ${error.status}.`
  }

  if (error instanceof TypeError) {
    return "The frontend cannot reach the backend. Check that the backend server is running."
  }

  return "Something went wrong while loading data. Please try again."
}

function getStoredToken(): string | null {
  if (accessToken) return accessToken
  if (typeof window === "undefined") return null
  accessToken = window.localStorage.getItem(TOKEN_STORAGE_KEY)
  return accessToken
}

export function getCurrentWorker(): string | null {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem(WORKER_STORAGE_KEY)
}

export function hasWorkerSession(): boolean {
  return Boolean(getStoredToken() && getCurrentWorker())
}

export function logoutWorker() {
  accessToken = null
  if (typeof window === "undefined") return
  window.localStorage.removeItem(TOKEN_STORAGE_KEY)
  window.localStorage.removeItem(WORKER_STORAGE_KEY)
}

export async function loginWorker(username: string, password: string) {
  const normalizedUsername = username.trim().toLowerCase()
  const response = await fetch(`${API_BASE_URL}/api/v1/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      username: normalizedUsername,
      password,
    }),
    cache: "no-store",
  })

  if (!response.ok) {
    throw new ApiRequestError("/api/v1/login", response.status, await readErrorDetail(response))
  }

  const data = (await response.json()) as { access_token: string }
  accessToken = data.access_token
  if (typeof window !== "undefined") {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token)
    window.localStorage.setItem(WORKER_STORAGE_KEY, normalizedUsername)
  }
  return data
}

async function getAccessToken(): Promise<string> {
  const token = getStoredToken()
  if (token) return token

  if (typeof window !== "undefined") {
    window.location.assign("/login")
    return new Promise(() => {})
  }

  throw new ApiRequestError("/api/v1/login", 401)
}

function getApiUrl(path: string): string {
  return `${API_BASE_URL}${path}`
}

async function apiFetch<T>(
  path: string,
  init?: RequestInit,
  options?: { auth?: boolean }
): Promise<T> {
  const headers = new Headers(init?.headers)

  if (options?.auth) {
    headers.set("Authorization", `Bearer ${await getAccessToken()}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  })

  if (!response.ok) {
    throw new ApiRequestError(path, response.status, await readErrorDetail(response))
  }

  return response.json() as Promise<T>
}

async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const data = (await response.json()) as { detail?: unknown }
    return typeof data.detail === "string" ? data.detail : null
  } catch {
    return null
  }
}

export async function fetchHealth() {
  return apiFetch<ApiHealth>("/api/v1/health")
}

export async function fetchCandidates(
  category?: string,
  options?: { limit?: number; offset?: number }
) {
  const params = new URLSearchParams()
  if (category) params.set("category", category)
  if (options?.limit) params.set("limit", String(options.limit))
  if (options?.offset) params.set("offset", String(options.offset))
  const query = params.toString()
  return apiFetch<ApiCandidateListResponse>(
    `/api/v1/candidates${query ? `?${query}` : ""}`,
    undefined,
    { auth: true }
  )
}

export async function fetchAllCandidates(category?: string) {
  const limit = 200
  let offset = 0
  const candidates: ApiCandidateListItem[] = []
  let total = 0

  do {
    const response = await fetchCandidates(category, { limit, offset })
    total = response.total
    candidates.push(...response.candidates)
    offset += response.candidates.length

    if (response.candidates.length === 0) break
  } while (candidates.length < total)

  return {
    total,
    limit: candidates.length,
    offset: 0,
    candidates,
  } satisfies ApiCandidateListResponse
}

export async function fetchCandidate(id: string) {
  return apiFetch<ApiCandidateDetail>(`/api/v1/candidates/${id}`, undefined, {
    auth: true,
  })
}

export async function fetchCandidateCvBlob(id: string, download = false) {
  const response = await fetch(
    getApiUrl(`/api/v1/candidates/${id}/cv${download ? "?download=true" : ""}`),
    {
      headers: {
        Authorization: `Bearer ${await getAccessToken()}`,
      },
      cache: "no-store",
    }
  )

  if (!response.ok) {
    throw new ApiRequestError(
      `/api/v1/candidates/${id}/cv`,
      response.status,
      await readErrorDetail(response)
    )
  }

  return response.blob()
}

export async function fetchDuplicateCandidates() {
  return apiFetch<ApiDuplicateCandidateGroupsResponse>(
    "/api/v1/candidates/duplicates",
    undefined,
    { auth: true }
  )
}

export async function fetchUploadLogs(limit = 20) {
  return apiFetch<ApiUploadLog[]>(`/api/v1/uploads/logs?limit=${limit}`, undefined, {
    auth: true,
  })
}

export async function uploadCvFiles(files: File[]) {
  const formData = new FormData()
  files.forEach((file) => formData.append("files", file))

  return apiFetch<ApiUploadBatchResponse>("/api/v1/upload", {
    method: "POST",
    body: formData,
  }, { auth: true })
}

export async function deleteCandidate(id: string) {
  const response = await fetch(`${API_BASE_URL}/api/v1/candidates/${id}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${await getAccessToken()}`,
    },
  })

  if (!response.ok) {
    throw new ApiRequestError(`/api/v1/candidates/${id}`, response.status)
  }
}

export async function fetchActivityLogs(limit = 100, worker?: string) {
  const params = new URLSearchParams()
  params.set("limit", String(limit))
  if (worker) params.set("worker", worker)

  return apiFetch<ApiActivityLog[]>(
    `/api/v1/activity/logs?${params.toString()}`,
    undefined,
    { auth: true }
  )
}

export async function fetchSettingsStatus() {
  return apiFetch<ApiSettingsStatus>("/api/v1/settings/status")
}

export async function createWorkerLogin(input: {
  username: string
  password: string
  full_name?: string
  is_admin?: boolean
}) {
  return apiFetch<ApiWorkerUser>(
    "/api/v1/admin/users",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(input),
    },
    { auth: true }
  )
}

export async function fetchCurrentWorkerProfile() {
  return apiFetch<ApiWorkerUser>("/api/v1/me", undefined, { auth: true })
}

export async function matchJobDescription(jobDescription: string) {
  return apiFetch<ApiJobMatchResponse>(
    "/api/v1/match",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        job_description: jobDescription,
        limit: 20,
      }),
    },
    { auth: true }
  )
}

export async function matchJobDescriptionFile(file: File) {
  const formData = new FormData()
  formData.append("file", file)
  formData.append("limit", "20")

  return apiFetch<ApiJobMatchResponse>(
    "/api/v1/match/upload",
    {
      method: "POST",
      body: formData,
    },
    { auth: true }
  )
}
