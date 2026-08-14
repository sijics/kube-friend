// useDashboard.ts — polling hook for the dashboard endpoint
//
// Fetches /api/dashboard?namespace=<ns> on mount and every 30 seconds.
// Exposes the response, loading state, error, and a manual refresh function.

import { useState, useEffect, useCallback, useRef } from 'react'
import { DashboardResponse } from '../types'

const POLL_INTERVAL_MS = 30_000

export function useDashboard(namespace: string) {
  const [data, setData] = useState<DashboardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetch_ = useCallback(async (ns: string) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api/dashboard?namespace=${encodeURIComponent(ns)}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json: DashboardResponse = await res.json()
      if (json.error) throw new Error(json.error)
      setData(json)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  // Fetch immediately on namespace change, then poll
  useEffect(() => {
    fetch_(namespace)
    timerRef.current = setInterval(() => fetch_(namespace), POLL_INTERVAL_MS)
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [namespace, fetch_])

  const refresh = useCallback(() => fetch_(namespace), [namespace, fetch_])

  return { data, loading, error, refresh }
}
