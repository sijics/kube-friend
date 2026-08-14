// Dashboard.tsx — the full dashboard tab: namespace selector + summary bar + pod table

import { useState } from 'react'
import { DashboardPod } from '../types'
import { useDashboard } from '../hooks/useDashboard'
import SummaryBar from './SummaryBar'
import PodTable from './PodTable'
import NamespaceSelector from './NamespaceSelector'

interface Props {
  // Called when user clicks "Ask AI" on a pod row — switches to chat tab
  // with a pre-filled question about that pod
  onAskAboutPod: (question: string) => void
}

export default function Dashboard({ onAskAboutPod }: Props) {
  const [namespace, setNamespace] = useState('kubefriend-test')
  const { data, loading, error, refresh } = useDashboard(namespace)

  function handleAsk(pod: DashboardPod) {
    const q = `Why is pod ${pod.name} in namespace ${pod.namespace} not running?`
    onAskAboutPod(q)
  }

  return (
    <div style={styles.container}>

      {/* ── Header ── */}
      <div style={styles.header}>
        <div>
          <h2 style={styles.title}>Cluster Dashboard</h2>
          <p style={styles.subtitle}>Live pod health — refreshes every 30s</p>
        </div>
        <div style={styles.controls}>
          {data && (
            <NamespaceSelector
              namespaces={data.namespaces}
              selected={namespace}
              onChange={setNamespace}
            />
          )}
          <button style={styles.refreshBtn} onClick={refresh} disabled={loading}>
            {loading ? 'Loading…' : '↻ Refresh'}
          </button>
        </div>
      </div>

      {/* ── Error banner ── */}
      {error && (
        <div style={styles.errorBanner}>
          ⚠ {error}
        </div>
      )}

      {/* ── Summary bar ── */}
      {data && !error && <SummaryBar summary={data.summary} />}

      {/* ── Pod table ── */}
      {loading && !data && (
        <p style={{ color: '#6b7280', fontSize: 14 }}>Loading pods…</p>
      )}
      {data && !error && (
        <PodTable pods={data.pods} onAsk={handleAsk} />
      )}

      <p style={styles.hint}>
        Click <strong>Ask AI</strong> on any unhealthy pod to open the chat with a pre-filled question.
      </p>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '24px',
    maxWidth: 1200,
    margin: '0 auto',
    fontFamily: '-apple-system, "Segoe UI", system-ui, sans-serif',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 20,
    flexWrap: 'wrap',
    gap: 12,
  },
  title: {
    margin: 0,
    fontSize: 20,
    fontWeight: 700,
    color: '#111827',
  },
  subtitle: {
    margin: '4px 0 0',
    fontSize: 13,
    color: '#6b7280',
  },
  controls: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
  },
  refreshBtn: {
    padding: '6px 14px',
    borderRadius: 6,
    border: '1px solid #d1d5db',
    background: '#fff',
    fontSize: 13,
    cursor: 'pointer',
    color: '#374151',
  },
  errorBanner: {
    background: '#fef2f2',
    border: '1px solid #fca5a5',
    borderRadius: 8,
    padding: '12px 16px',
    color: '#b91c1c',
    fontSize: 13,
    marginBottom: 16,
  },
  hint: {
    marginTop: 16,
    fontSize: 12,
    color: '#9ca3af',
  },
}
