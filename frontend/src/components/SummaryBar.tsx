// SummaryBar.tsx — Running / Warning / Critical pod counters at the top of the dashboard

import { DashboardSummary } from '../types'

interface Props {
  summary: DashboardSummary
}

export default function SummaryBar({ summary }: Props) {
  return (
    <div style={styles.bar}>
      <Tile label="Total" value={summary.total} color="#6b7280" />
      <Tile label="Running" value={summary.running} color="#16a34a" />
      <Tile label="Warning" value={summary.warning} color="#d97706" />
      <Tile label="Critical" value={summary.critical} color="#dc2626" />
    </div>
  )
}

function Tile({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ ...styles.tile, borderTop: `3px solid ${color}` }}>
      <span style={{ ...styles.value, color }}>{value}</span>
      <span style={styles.label}>{label}</span>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  bar: {
    display: 'flex',
    gap: 12,
    marginBottom: 20,
  },
  tile: {
    flex: 1,
    background: '#f9fafb',
    border: '1px solid #e5e7eb',
    borderRadius: 8,
    padding: '14px 16px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 4,
  },
  value: {
    fontSize: 28,
    fontWeight: 700,
    lineHeight: 1,
  },
  label: {
    fontSize: 12,
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
}
