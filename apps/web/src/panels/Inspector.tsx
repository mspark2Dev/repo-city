import { useCityStore } from '../store'
import { GRADE_COLOR } from '../scene/palette'
import { CodeView } from './CodeView'

function resolvedShare(stats: { links: number; unresolved: number }): number {
  const total = stats.links + stats.unresolved
  return total === 0 ? 100 : Math.round((stats.links / total) * 100)
}

function Row({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

export function Inspector() {
  const city = useCityStore((s) => s.city)
  const building = useCityStore((s) => s.selected)
  const detail = useCityStore((s) => s.detail)

  if (!city) return null

  if (!building) {
    return (
      <div className="inspector">
        <h2>City</h2>
        <Row label="files" value={city.stats.files} />
        <Row label="lines" value={city.stats.loc.toLocaleString()} />
        <Row label="imports resolved" value={city.stats.links} />
        <Row
          label="unresolved imports"
          value={`${city.stats.unresolved} (${resolvedShare(city.stats)}% resolved)`}
        />
        <p className="hint">
          Unresolved specifiers are packages or paths this analyzer could not map to a file.
          They are excluded from the graph, so this share is how much of the dependency
          picture you are actually seeing.
        </p>
        <p className="hint">Click a building to inspect it. Double-click to fly to it.</p>
      </div>
    )
  }

  const m = building.metrics
  return (
    <div className="inspector">
      <h2 title={building.path}>{building.name}</h2>
      <div className="grade" style={{ background: GRADE_COLOR[building.grade] }}>
        {building.grade} · max CC {m.maxCC}
      </div>
      <p className="path">{building.path}</p>

      <Row label="lines" value={m.loc} />
      <Row label="code / comments" value={`${m.sloc} / ${m.comments}`} />
      <Row label="functions / classes" value={`${m.functions} / ${m.classes}`} />
      <Row label="avg CC" value={m.avgCC} />
      <Row label="imported by" value={m.fanIn} />
      <Row label="imports" value={m.fanOut} />

      {detail && (
        <>
          <h3>Dependencies</h3>
          <ul>
            {detail.imports.map((id) => (
              <li key={id}>→ {id.slice(2)}</li>
            ))}
            {detail.importedBy.map((id) => (
              <li key={id} className="incoming">
                ← {id.slice(2)}
              </li>
            ))}
            {detail.imports.length + detail.importedBy.length === 0 && (
              <li className="hint">none resolved</li>
            )}
          </ul>

          <h3>Source</h3>
          <CodeView />
        </>
      )}
    </div>
  )
}
