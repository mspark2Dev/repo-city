import { useState } from 'react'
import { useT } from '../i18n'
import { useCityStore } from '../store'

export function CommandBar() {
  const t = useT()
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
            <pre className="stream">{streamed.slice(-600) || t.agent.writing}</pre>
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
              ? (llm?.detail ?? t.agent.connecting)
              : selected
                ? t.agent.refactor(selected.name)
                : t.agent.selectFirst
          }
          disabled={disabled}
          spellCheck={false}
        />
        <button type="submit" disabled={disabled || !instruction.trim()}>
          {busy ? (status === 'planning' ? t.agent.planning : t.agent.generating) : t.agent.send}
        </button>
      </form>

      {selected && llm?.ok && !busy && (
        <div className="suggestions">
          {t.agent.suggestions.map((text) => (
            <button key={text} type="button" onClick={() => setInstruction(text)}>
              {text}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
