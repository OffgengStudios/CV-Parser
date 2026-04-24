"use client"

/**
 * useIdleTimeout — auto-logout after a period of inactivity.
 *
 * Flow:
 *   1. Any user interaction (mouse, keyboard, touch, scroll) resets the idle timer.
 *   2. At (idleMs - warningMs) the `isWarning` flag becomes true so the UI can
 *      show a "You'll be signed out in Xs" countdown.
 *   3. At idleMs the `onIdle` callback fires (caller should call logoutWorker()
 *      and redirect to /login).
 *
 * Defaults: 30 min idle, 2 min warning.
 */
import { useCallback, useEffect, useRef, useState } from "react"

interface UseIdleTimeoutOptions {
  /** Total idle duration before logout (ms). Default: 30 minutes. */
  idleMs?: number
  /** How long before idle to show the warning (ms). Default: 2 minutes. */
  warningMs?: number
  /** Called when the idle threshold is reached. */
  onIdle: () => void
}

const ACTIVITY_EVENTS = [
  "mousemove",
  "mousedown",
  "keydown",
  "touchstart",
  "scroll",
  "click",
] as const

export function useIdleTimeout({
  idleMs = 30 * 60 * 1000,
  warningMs = 2 * 60 * 1000,
  onIdle,
}: UseIdleTimeoutOptions) {
  const [isWarning, setIsWarning] = useState(false)
  const [secondsLeft, setSecondsLeft] = useState(0)

  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const warningTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const countdownInterval = useRef<ReturnType<typeof setInterval> | null>(null)
  const onIdleRef = useRef(onIdle)

  // Keep a stable ref to onIdle so callers can update it without re-registering listeners.
  useEffect(() => {
    onIdleRef.current = onIdle
  }, [onIdle])

  const clearAllTimers = useCallback(() => {
    if (idleTimer.current) clearTimeout(idleTimer.current)
    if (warningTimer.current) clearTimeout(warningTimer.current)
    if (countdownInterval.current) clearInterval(countdownInterval.current)
    idleTimer.current = null
    warningTimer.current = null
    countdownInterval.current = null
  }, [])

  const startWarningCountdown = useCallback(() => {
    setIsWarning(true)
    setSecondsLeft(Math.round(warningMs / 1000))

    countdownInterval.current = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          if (countdownInterval.current) clearInterval(countdownInterval.current)
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }, [warningMs])

  const resetTimer = useCallback(() => {
    clearAllTimers()
    setIsWarning(false)
    setSecondsLeft(0)

    // Schedule warning
    warningTimer.current = setTimeout(() => {
      startWarningCountdown()
    }, idleMs - warningMs)

    // Schedule logout
    idleTimer.current = setTimeout(() => {
      clearAllTimers()
      onIdleRef.current()
    }, idleMs)
  }, [idleMs, warningMs, clearAllTimers, startWarningCountdown])

  useEffect(() => {
    // Start the timers on mount
    resetTimer()

    // Listen for activity
    const handleActivity = () => resetTimer()
    ACTIVITY_EVENTS.forEach((event) =>
      document.addEventListener(event, handleActivity, { passive: true })
    )

    return () => {
      clearAllTimers()
      ACTIVITY_EVENTS.forEach((event) =>
        document.removeEventListener(event, handleActivity)
      )
    }
  }, [resetTimer, clearAllTimers])

  return { isWarning, secondsLeft, resetTimer }
}
