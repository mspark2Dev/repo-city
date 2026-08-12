import { useEffect, useState } from 'react'
import { useT } from './i18n'
import { LocaleToggle } from './i18n/LocaleToggle'
import { CommandBar } from './panels/CommandBar'
import { Inspector } from './panels/Inspector'
import { CityCanvas } from './scene/CityCanvas'
import { useCityStore } from './store'

const DEFAULT_PATH = '../../fixtures/sample-project'

function Progress() {
  const t = useT()
  const status = useCityStore((s) => s.status)
  const progress = useCityStore((s) => s.progress)
  const cloning = useCityStore((s) => s.cloning)
  if (status !== 'loading') return null

  const pct = progress && progress.total > 0 ? (progress.done / progress.total) * 100 : 0
  return (
    <div className="progress">
      <div className={`bar${cloning ? ' indeterminate' : ''}`}>
        <div className="fill" style={{ width: cloning ? '100%' : `${pct}%` }} />
      </div>
      <span>
        {cloning
          ? t.progress.cloning(cloning)
          : progress
            ? t.progress.parsing(progress.done, progress.total)
            : t.progress.scanning}
      </span>
    </div>
  )
}

export function App() {
  const t = useT()
  const [path, setPath] = useState(DEFAULT_PATH)
  const { status, error, load } = useCityStore()

  useEffect(() => {
    void load(DEFAULT_PATH)
  }, [load])

  return (
    <div className="app">
      <div className="canvas">
        <CityCanvas />

        <div className="loader">
          <form
            onSubmit={(event) => {
              event.preventDefault()
              void load(path)
            }}
          >
            <input
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder={t.loader.placeholder}
              spellCheck={false}
            />
            <button type="submit" disabled={status === 'loading'}>
              {status === 'loading' ? t.loader.analyzing : t.loader.analyze}
            </button>
          </form>
          {/* The field is prefilled, so the placeholder never shows — without this caption
              there is nothing telling you a URL is accepted. */}
          <p className="loader-hint">{t.loader.hint}</p>
        </div>

        <LocaleToggle />
        <Progress />
        {status === 'error' && <div className="error">{error}</div>}
        <CommandBar />
      </div>
      <aside>
        <Inspector />
      </aside>
    </div>
  )
}
