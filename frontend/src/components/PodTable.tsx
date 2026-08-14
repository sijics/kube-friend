// PodTable.tsx — table of pods with status badge, AI diagnosis, and Ask button

import { DashboardPod } from '../types'

interface Props {
  pods: DashboardPod[]
  onAsk: (pod: DashboardPod) => void   // fires when user clicks "Ask" on a row
}

const SEVERITY_BADGE: Record<string, { bg: string; color: string; label: string }> = {
  healthy:  { bg: '#dcfce7', color: '#15803d', label: '● Running'  },
  warning:  { bg: '#fef9c3', color: '#a16207', label: '● Warning'  },
  critical: { bg: '#fee2e2', color: '#b91c1c', label: '● Critical' },
}

export default function PodTable({ pods, onAsk }: Props) {
  if (pods.length === 0) {
    return <p style={{ color: '#6b7280', fontSize: 14 }}>No pods found in this namespace.</p>
  }

  return (
    <div style={styles.wrapper}>
      <table style={styles.table}>
        <thead>
          <tr style={styles.headerRow}>
            <Th>Pod</Th>
            <Th>Status</Th>
            <Th>Restarts</Th>
            <Th>Age (h)</Th>
            <Th>Node</Th>
            <Th>AI Diagnosis</Th>
            <Th>Suggestion</Th>
            <th style={styles.th}></th>
          </tr>
        </thead>
        <tbody>
          {pods.map(pod => (
            <PodRow key={`${pod.namespace}/${pod.name}`} pod={pod} onAsk={onAsk} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function PodRow({ pod, onAsk }: { pod: DashboardPod; onAsk: (p: DashboardPod) => void }) {
  const badge = SEVERITY_BADGE[pod.severity] ?? SEVERITY_BADGE.warning

  return (
    <tr style={styles.row}>
      <td style={{ ...styles.cell, fontWeight: 500, fontFamily: 'monospace', fontSize: 12 }}>
        {pod.name}
      </td>
      <td style={styles.cell}>
        <span style={{ ...styles.badge, background: badge.bg, color: badge.color }}>
          {pod.status}
        </span>
      </td>
      <td style={{ ...styles.cell, textAlign: 'center' }}>{pod.restarts}</td>
      <td style={{ ...styles.cell, textAlign: 'center' }}>
        {pod.age_hours !== null ? pod.age_hours : '—'}
      </td>
      <td style={{ ...styles.cell, fontFamily: 'monospace', fontSize: 12 }}>{pod.node}</td>
      <td style={{ ...styles.cell, maxWidth: 240, fontSize: 12, color: '#374151' }}>
        {pod.diagnosis ?? <span style={{ color: '#9ca3af' }}>—</span>}
      </td>
      <td style={{ ...styles.cell, maxWidth: 240, fontSize: 12, color: '#374151' }}>
        {pod.suggestion
          ? <code style={styles.code}>{pod.suggestion}</code>
          : <span style={{ color: '#9ca3af' }}>—</span>
        }
      </td>
      <td style={styles.cell}>
        {pod.severity !== 'healthy' && (
          <button style={styles.askBtn} onClick={() => onAsk(pod)}>
            Ask AI
          </button>
        )}
      </td>
    </tr>
  )
}

function Th({ children }: { children: React.ReactNode }) {
  return <th style={styles.th}>{children}</th>
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    overflowX: 'auto',
    border: '1px solid #e5e7eb',
    borderRadius: 8,
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: 13,
  },
  headerRow: {
    background: '#f9fafb',
    borderBottom: '1px solid #e5e7eb',
  },
  th: {
    padding: '10px 14px',
    textAlign: 'left',
    fontWeight: 600,
    color: '#374151',
    whiteSpace: 'nowrap',
  },
  row: {
    borderBottom: '1px solid #f3f4f6',
  },
  cell: {
    padding: '10px 14px',
    verticalAlign: 'top',
    color: '#111827',
  },
  badge: {
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: 99,
    fontSize: 11,
    fontWeight: 600,
    whiteSpace: 'nowrap',
  },
  code: {
    display: 'block',
    background: '#f3f4f6',
    borderRadius: 4,
    padding: '3px 6px',
    fontFamily: 'monospace',
    fontSize: 11,
    wordBreak: 'break-all',
    color: '#1d4ed8',
  },
  askBtn: {
    padding: '4px 10px',
    borderRadius: 6,
    border: '1px solid #3b82f6',
    background: 'transparent',
    color: '#3b82f6',
    fontSize: 12,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
}
