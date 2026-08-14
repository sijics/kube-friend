// NamespaceSelector.tsx — dropdown to pick which namespace to display

interface Props {
  namespaces: string[]
  selected: string
  onChange: (ns: string) => void
}

export default function NamespaceSelector({ namespaces, selected, onChange }: Props) {
  return (
    <div style={styles.wrapper}>
      <label style={styles.label} htmlFor="ns-select">Namespace</label>
      <select
        id="ns-select"
        value={selected}
        onChange={e => onChange(e.target.value)}
        style={styles.select}
      >
        {namespaces.map(ns => (
          <option key={ns} value={ns}>{ns}</option>
        ))}
      </select>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  label: {
    fontSize: 13,
    color: '#374151',
    fontWeight: 500,
  },
  select: {
    padding: '6px 10px',
    borderRadius: 6,
    border: '1px solid #d1d5db',
    fontSize: 13,
    background: '#fff',
    cursor: 'pointer',
    color: '#111827',
  },
}
