import { useEffect, useState } from 'react'
import { Inspector } from './panels/Inspector'
import { CityCanvas } from './scene/CityCanvas'
import { useCityStore } from './store'

const DEFAULT_PATH = '../../fixtures/sample-project'

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
          <input value={path} onChange={(e) => setPath(e.target.value)} spellCheck={false} />
          <button type="submit" disabled={status === 'loading'}>
            {status === 'loading' ? 'analyzing…' : 'analyze'}
          </button>
        </form>
        {status === 'error' && <div className="error">{error}</div>}
      </div>
      <aside>
        <Inspector />
      </aside>
    </div>
  )
}
