import { useEffect, useState } from 'react'
import { CommandBar } from './panels/CommandBar'
import { Inspector } from './panels/Inspector'
import { CityCanvas } from './scene/CityCanvas'
import { useCityStore } from './store'

const DEFAULT_PATH = '../../fixtures/sample-project'
const PLACEHOLDER = 'a local path, or https://github.com/owner/repo.git'

function Progress() {
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
          ? `cloning ${cloning}`
          : progress
            ? `parsing ${progress.done} / ${progress.total} files`
            : 'scanning repository…'}
      </span>
    </div>
  )
}

export function App() {
  const [path, setPath] = useState(DEFAULT_PATH)
  const { status, error, load } = useCityStore()

  useEffect(() => {
    void load(DEFAULT_PATH)
  }, [load])

  return (
    <div className="app">
      <div className="canvas">
        <CityCanvas />
        <form
          className="loader"
          onSubmit={(event) => {
            event.preventDefault()
            void load(path)
          }}
        >
          <input
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder={PLACEHOLDER}
            spellCheck={false}
          />
          <button type="submit" disabled={status === 'loading'}>
            {status === 'loading' ? 'analyzing…' : 'analyze'}
          </button>
        </form>
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
