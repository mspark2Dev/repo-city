import { useCityStore } from '../store'

/** Before/after for the file that was changed, with the city toggled alongside it. */
export function Comparison() {
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
    ['max CC', before.metrics.maxCC, after.metrics.maxCC],
    ['lines', before.metrics.loc, after.metrics.loc],
    ['functions', before.metrics.functions, after.metrics.functions],
  ]

  return (
    <div className="comparison">
      <div className="comparison-head">
        <h3>Before / after</h3>
        <button type="button" className={showBaseline ? 'on' : ''} onClick={toggle}>
          {showBaseline ? 'showing before' : 'show before'}
        </button>
      </div>

      <table>
        <thead>
          <tr>
            <th />
            <th>before</th>
            <th>after</th>
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
            <td>grade</td>
            <td className="from">{before.grade}</td>
            <td className={after.grade !== before.grade ? 'better' : ''}>{after.grade}</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
