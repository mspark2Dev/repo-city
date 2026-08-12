import { useT } from '../i18n'
import { GRADE_COLOR } from '../scene/palette'
import { useCityStore } from '../store'
import { CodeView } from './CodeView'
import { Comparison } from './Comparison'
import { Proposal } from './Proposal'

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
  const t = useT()
  const city = useCityStore((s) => s.city)
  const llm = useCityStore((s) => s.llm)
  const snapshotId = useCityStore((s) => s.snapshotId)
  const revert = useCityStore((s) => s.revert)
  const origin = useCityStore((s) => s.origin)
  const building = useCityStore((s) => s.selected)
  const selectedFloor = useCityStore((s) => s.selectedFloor)
  const select = useCityStore((s) => s.select)
  const detail = useCityStore((s) => s.detail)

  if (!city) return null

  const badge = (
    <div className={`llm-badge ${llm?.ok ? 'up' : 'down'}`} title={llm?.detail ?? ''}>
      {llm?.ok && llm.model ? t.agent.online(llm.model) : t.agent.offline(llm?.detail ?? null)}
    </div>
  )

  if (!building) {
    return (
      <div className="inspector">
        {badge}
        <h2>{t.city.title}</h2>
        {(origin?.ref || origin?.subpath) && (
          <p className="origin">
            {origin.ref && <span>{t.city.branch(origin.ref)}</span>}
            {origin.subpath && <span>{t.city.subpath(origin.subpath)}</span>}
          </p>
        )}
        <Row label={t.city.files} value={city.stats.files} />
        <Row label={t.city.lines} value={city.stats.loc.toLocaleString()} />
        <Row label={t.city.resolved} value={city.stats.links} />
        <Row
          label={t.city.unresolved}
          value={t.city.unresolvedShare(city.stats.unresolved, resolvedShare(city.stats))}
        />
        <p className="hint">{t.city.unresolvedNote}</p>
        <p className="hint">{t.city.selectHint}</p>
        <p className="hint">{t.city.sourceHint}</p>
      </div>
    )
  }

  const m = building.metrics
  const floors = building.floors ?? []
  return (
    <div className="inspector">
      {badge}
      {snapshotId && (
        <div className="revert-bar">
          {t.applied.message}
          <button type="button" onClick={() => void revert()}>
            {t.applied.revert}
          </button>
        </div>
      )}
      <h2 title={building.path}>{building.name}</h2>
      <div className="grade" style={{ background: GRADE_COLOR[building.grade] }}>
        {t.building.gradeBadge(t.grade[building.grade], m.maxCC)}
      </div>
      <p className="path">{building.path}</p>
      {selectedFloor !== null && floors[selectedFloor] && (
        <p className="selected-floor">
          {t.building.selectedFloor(floors[selectedFloor].name, floors[selectedFloor].line)}
        </p>
      )}

      <Row label={t.building.lines} value={m.loc} />
      <Row label={t.building.codeComments} value={`${m.sloc} / ${m.comments}`} />
      <Row label={t.building.functionsClasses} value={`${m.functions} / ${m.classes}`} />
      <Row label={t.building.avgCC} value={m.avgCC} />
      <Row label={t.building.importedBy} value={m.fanIn} />
      <Row label={t.building.imports} value={m.fanOut} />

      {floors.length > 0 && (
        <>
          <h3>{t.building.functions}</h3>
          <p className="hint">{t.building.floorHint}</p>
          <ul className="floors">
            {[...floors]
              .map((floor, index) => ({ floor, index }))
              .sort((a, b) => b.floor.cc - a.floor.cc || a.floor.line - b.floor.line)
              .map(({ floor, index }) => (
                <li key={`${floor.name}-${floor.line}`}>
                  <button
                    type="button"
                    className={index === selectedFloor ? 'on' : ''}
                    onClick={() => void select(building.id, index)}
                  >
                    <span className="cc" style={{ background: GRADE_COLOR[floor.grade] }}>
                      {floor.cc}
                    </span>
                    <span className="fn">{floor.name}</span>
                    <span className="ln">L{floor.line}</span>
                  </button>
                </li>
              ))}
          </ul>
        </>
      )}

      {detail && (
        <>
          <h3>{t.building.dependencies}</h3>
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
              <li className="hint">{t.building.noneResolved}</li>
            )}
          </ul>

          <Proposal />
          <Comparison />

          <h3>{t.building.source}</h3>
          <CodeView />
        </>
      )}
    </div>
  )
}
