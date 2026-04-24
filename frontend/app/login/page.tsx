"use client"

import { FormEvent, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Eye, EyeOff, FileText, Lock, User } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useToast } from "@/hooks/use-toast"
import { getApiErrorMessage, hasWorkerSession, loginWorker } from "@/lib/api"

export default function LoginPage() {
  const router = useRouter()
  const { toast } = useToast()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (hasWorkerSession()) {
      router.replace("/")
    }
  }, [router])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)

    try {
      await loginWorker(username.trim(), password)
      toast({
        title: "Signed in",
        description: `Welcome, ${username.trim()}.`,
      })
      router.replace("/")
    } catch (error) {
      toast({
        title: "Login failed",
        description:
          getApiErrorMessage(error) ||
          "Check your username and password, then try again.",
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-background">
      <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[1fr_460px]">
        <section className="hidden bg-primary text-primary-foreground lg:flex lg:flex-col lg:justify-between lg:p-10">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-foreground/15">
              <FileText className="h-5 w-5" />
            </div>
            <span className="text-xl font-semibold">CVParser</span>
          </div>
          <div>
            <h1 className="max-w-xl text-4xl font-semibold leading-tight">
              Track every CV action by worker.
            </h1>
            <p className="mt-4 max-w-lg text-sm text-primary-foreground/80">
              Sign in before uploading, reviewing duplicates, deleting candidates,
              or matching job descriptions.
            </p>
          </div>
          <p className="text-xs text-primary-foreground/70">
            Demo workers: admin/admin123 or demo/demo123
          </p>
        </section>

        <section className="flex items-center justify-center p-6">
          <form
            onSubmit={handleSubmit}
            className="w-full max-w-sm rounded-lg border border-border bg-card p-6 shadow-sm"
          >
            <div className="mb-6">
              <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground lg:hidden">
                <FileText className="h-5 w-5" />
              </div>
              <h2 className="text-2xl font-semibold text-card-foreground">
                Worker login
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Use your worker account to continue.
              </p>
            </div>

            <div className="grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="username">Username</Label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="username"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    className="pl-9"
                    autoComplete="username"
                    required
                  />
                </div>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    className="pl-9 pr-11"
                    autoComplete="current-password"
                    required
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => setShowPassword((current) => !current)}
                    className="absolute right-1 top-1/2 h-8 w-8 -translate-y-1/2"
                    title={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>

              <Button type="submit" disabled={loading} className="mt-2 w-full">
                {loading ? "Signing in..." : "Sign in"}
              </Button>
            </div>
          </form>
        </section>
      </div>
    </main>
  )
}
