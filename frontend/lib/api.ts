export interface ApiCandidateListItem {
  id: string
  name: string | null
  email: string | null
  phone: string | null
  category: string | null
  subcategory: string | null
  confidence: number | null
  years_experience: number | null
  seniority_level: string | null
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
  temporary_password?: string | null
  created_at?: string | null
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

const TOKEN_STORAGE_KEY = "cvparser_access_token"
const WORKER_STORAGE_KEY = "cvparser_worker"
const SESSION_COOKIE = "cvparser_session"

/** Returns "; Secure" on HTTPS so the session cookie is accepted by the browser. */
function secureFlag(): string {
  if (typeof window === "undefined") return ""
  return window.location.protocol === "https:" ? "; Secure" : ""
}

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
  if (typeof window === "undefined") return null
  return window.localStorage.getItem(TOKEN_STORAGE_KEY)
}

export function getCurrentWorker(): string | null {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem(WORKER_STORAGE_KEY)
}

export function hasWorkerSession(): boolean {
  return Boolean(getStoredToken() && getCurrentWorker())
}

/**
 * Clears the local session (localStorage + cookie) and fires the backend
 * /logout endpoint to revoke the JWT denylist entry.
 *
 * The backend call is best-effort — even if it fails (e.g., backend offline,
 * token already expired) the local session is still cleared so the user is
 * effectively signed out on this device.
 */
export function logoutWorker() {
  if (typeof window === "undefined") return

  // Fire the server-side revocation request while we still have the token.
  const token = window.localStorage.getItem(TOKEN_STORAGE_KEY)
  if (token) {
    // Best-effort: don't await, don't throw — local logout proceeds regardless.
    fetch(`${API_BASE_URL}/api/v1/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      keepalive: true, // ensures the request completes even if the page unloads
    }).catch(() => {
      // Silently ignore — the token's jti just won't be in the server denylist.
    })
  }

  window.localStorage.removeItem(TOKEN_STORAGE_KEY)
  window.localStorage.removeItem(WORKER_STORAGE_KEY)
  // Clear the session-presence cookie so middleware redirects immediately
  document.cookie = `${SESSION_COOKIE}=; path=/; max-age=0; SameSite=Lax${secureFlag()}`
}

/** Exchange the current token for a fresh one. Revokes the old token server-side. */
export async function refreshToken() {
  return apiFetch<{ access_token: string; expires_in: number }>(
    "/api/v1/auth/refresh",
    { method: "POST" },
    { auth: true }
  ).then((data) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token)
      const maxAge = data.expires_in ?? 86400
      document.cookie = `${SESSION_COOKIE}=1; path=/; max-age=${maxAge}; SameSite=Lax${secureFlag()}`
    }
    return data
  })
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

  const data = (await response.json()) as { access_token: string; expires_in?: number }
  if (typeof window !== "undefined") {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token)
    window.localStorage.setItem(WORKER_STORAGE_KEY, normalizedUsername)
    // Set a lightweight session-presence cookie (not the JWT) so Next.js middleware
    // can gate protected routes before client JS hydrates.
    const maxAge = data.expires_in ?? 86400
    document.cookie = `${SESSION_COOKIE}=1; path=/; max-age=${maxAge}; SameSite=Lax${secureFlag()}`
  }
  return data
}

async function getAccessToken(): Promise<string> {
  const token = getStoredToken()
  if (token) return token

  if (typeof window !== "undefined") {
    window.location.assign("/login")
  }
  // Throw immediately so awaiting callers reach their catch/finally blocks.
  // (Previously this returned a never-resolving Promise which silently stalled
  // all in-flight requests and prevented error boundaries from firing.)
  throw new ApiRequestError("/api/v1/login", 401, "Session expired — please sign in again.")
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

  if (response.status === 401 && path !== "/api/v1/login") {
    // Token has expired or been revoked server-side. Wipe local session so
    // subsequent navigation lands on the login page rather than hitting 401s.
    logoutWorker()
    if (typeof window !== "undefined") {
      window.location.assign("/login")
    }
    throw new ApiRequestError(path, 401, "Session expired — please sign in again.")
  }

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

export async function fetchWorkerUsers() {
  return apiFetch<ApiWorkerUser[]>("/api/v1/admin/users", undefined, { auth: true })
}

/** Alias kept for backward compatibility with the settings page. */
export const fetchWorkerLogins = fetchWorkerUsers

export async function deactivateWorkerUser(username: string) {
  const response = await fetch(`${API_BASE_URL}/api/v1/admin/users/${encodeURIComponent(username)}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${await getAccessToken()}` },
  })
  if (!response.ok) {
    throw new ApiRequestError(`/api/v1/admin/users/${username}`, response.status, await readErrorDetail(response))
  }
}

export const deleteWorkerLogin = deactivateWorkerUser

export async function deleteOldWorkerLogins() {
  return apiFetch<{ deleted_count: number; deleted_usernames: string[] }>(
    "/api/v1/admin/users",
    {
      method: "DELETE",
    },
    { auth: true }
  )
}

export async function updateWorkerLoginAdmin(username: string, isAdmin: boolean) {
  return apiFetch<ApiWorkerUser>(
    `/api/v1/admin/users/${encodeURIComponent(username)}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ is_admin: isAdmin }),
    },
    { auth: true }
  )
}

export async function resetWorkerPassword(username: string, newPassword: string) {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/admin/users/${encodeURIComponent(username)}/reset-password`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${await getAccessToken()}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ new_password: newPassword }),
    }
  )
  if (!response.ok) {
    throw new ApiRequestError(
      `/api/v1/admin/users/${username}/reset-password`,
      response.status,
      await readErrorDetail(response)
    )
  }
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
