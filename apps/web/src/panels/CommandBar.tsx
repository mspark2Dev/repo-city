import { useState } from 'react'
import { useCityStore } from '../store'

const SUGGESTIONS = [
  'Split the most complex function into smaller ones.',
  'Add type hints to every function.',
  'Extract the repeated branches into a lookup table.',
]

export function CommandBar() {
  const [instruction, setInstruction] = useState('')
  const selected = useCityStore((s) => s.selected)
  const llm = useCityStore((s) => s.llm)
  const status = useCityStore((s) => s.agentStatus)
  const steps = useCityStore((s) => s.steps)
  const streamed = useCityStore((s) => s.streamed)
  const agentError = useCityStore((s) => s.agentError)
  const refactor = useCityStore((s) => s.refactor)

  const busy = status === 'planning' || status === 'generating'
  const disabled = !selected || !llm?.ok || busy

  return (
    <div className="command-bar">
      {(busy || steps.length > 0 || agentError) && (
        <div className="agent-log">
          {steps.map((step, index) => (
            <div key={index} className="step">
              {index + 1}. {step}
            </div>
          ))}
          {status === 'generating' && (
            <pre className="stream">{streamed.slice(-600) || 'writing…'}</pre>
          )}
          {agentError && <div className="agent-error">{agentError}</div>}
        </div>
      )}

      <form
        onSubmit={(event) => {
          event.preventDefault()
          if (disabled || !instruction.trim()) return
          void refactor(instruction.trim())
        }}
      >
        <input
          value={instruction}
          onChange={(event) => setInstruction(event.target.value)}
          placeholder={
            !llm?.ok
              ? (llm?.detail ?? 'connecting to the model…')
              : selected
                ? `Refactor ${selected.name}…`
                : 'Select a building first'
          }
          disabled={disabled}
          spellCheck={false}
        />
        <button type="submit" disabled={disabled || !instruction.trim()}>
          {busy ? status : 'send'}
        </button>
      </form>

      {selected && llm?.ok && !busy && (
        <div className="suggestions">
          {SUGGESTIONS.map((text) => (
            <button key={text} type="button" onClick={() => setInstruction(text)}>
              {text}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
