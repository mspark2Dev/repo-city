import Editor from '@monaco-editor/react'
import { useCityStore } from '../store'

export const MONACO_LANG: Record<string, string> = {
  python: 'python',
  typescript: 'typescript',
  javascript: 'javascript',
  java: 'java',
  go: 'go',
  rust: 'rust',
  c: 'c',
  cpp: 'cpp',
  csharp: 'csharp',
  ruby: 'ruby',
  php: 'php',
  kotlin: 'kotlin',
  swift: 'swift',
  scala: 'scala',
  objectivec: 'objective-c',
  lua: 'lua',
  perl: 'perl',
  r: 'r',
  plsql: 'sql',
  vue: 'html',
  solidity: 'sol',
  other: 'plaintext',
}

/** Read-only for now; Phase 3 swaps this for a diff view of the agent's proposal. */
export function CodeView() {
  const detail = useCityStore((s) => s.detail)
  const building = useCityStore((s) => s.selected)

  if (!detail || !building) return null

  return (
    <div className="code-view">
      <Editor
        height="340px"
        theme="vs-dark"
        language={MONACO_LANG[building.lang] ?? 'plaintext'}
        value={detail.source}
        options={{
          readOnly: true,
          minimap: { enabled: false },
          fontSize: 11,
          lineNumbers: 'on',
          scrollBeyondLastLine: false,
          renderLineHighlight: 'none',
          padding: { top: 10 },
        }}
      />
    </div>
  )
}
