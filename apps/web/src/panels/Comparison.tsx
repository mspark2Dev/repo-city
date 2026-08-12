import { useT } from '../i18n'
import { useCityStore } from '../store'

/** Before/after for the file that was changed, with the city toggled alongside it. */
export function Comparison() {
  const t = useT()
  const baseline = useCityStore((s) => s.baseline)
  const city = useCityStore((s) => s.city)
  const selected = useCityStore((s) => s.selected)
  const showBaseline = useCityStore((s) => s.showBaseline)
  const toggle = useCityStore((s) => s.toggleBaseline)

  if (!baseline || !city || !selected) return null

  const before = baseline.buildings.find((b) => b.id === selected.id)
  const after = city.buildings.find((b) => b.id === selected.id)
  if (!before || !after) return null

  const rows: [string, number, number][] = [
    [t.comparison.maxCC, before.metrics.maxCC, after.metrics.maxCC],
    [t.comparison.lines, before.metrics.loc, after.metrics.loc],
    [t.comparison.functions, before.metrics.functions, after.metrics.functions],
  ]

  return (
    <div className="comparison">
      <div className="comparison-head">
        <h3>{t.comparison.title}</h3>
        <button type="button" className={showBaseline ? 'on' : ''} onClick={toggle}>
          {showBaseline ? t.comparison.showingBefore : t.comparison.showBefore}
        </button>
      </div>

      <table>
        <thead>
          <tr>
            <th />
            <th>{t.comparison.before}</th>
            <th>{t.comparison.after}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, from, to]) => (
            <tr key={label}>
              <td>{label}</td>
              <td className="from">{from}</td>
              <td className={to < from ? 'better' : to > from ? 'worse' : ''}>{to}</td>
            </tr>
          ))}
          <tr>
            <td>{t.comparison.grade}</td>
            <td className="from">{t.grade[before.grade]}</td>
            <td className={after.grade !== before.grade ? 'better' : ''}>{t.grade[after.grade]}</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
