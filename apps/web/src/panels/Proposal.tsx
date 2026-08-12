import { DiffEditor } from '@monaco-editor/react'
import { useT } from '../i18n'
import { useCityStore } from '../store'

const MONACO_LANG: Record<string, string> = {
  python: 'python',
  typescript: 'typescript',
  javascript: 'javascript',
  other: 'plaintext',
}

/** Nothing is written until Apply is pressed; this view is the point of that split. */
export function Proposal() {
  const t = useT()
  const proposal = useCityStore((s) => s.proposal)
  const detail = useCityStore((s) => s.detail)
  const selected = useCityStore((s) => s.selected)
  const apply = useCityStore((s) => s.applyProposal)
  const discard = useCityStore((s) => s.discardProposal)

  if (!proposal || !detail || !selected) return null

  const verdict = proposal.verdict

  return (
    <div className="proposal">
      <h3>{t.proposal.title}</h3>

      {verdict && (
        <div className="verdict">
          <span className={verdict.improved ? 'good' : 'flat'}>
            {t.proposal.maxCC(verdict.beforeMaxCC, verdict.afterMaxCC)}
          </span>
          <span>{t.proposal.lines(verdict.beforeLoc, verdict.afterLoc)}</span>
          {verdict.lostSymbols.length > 0 && (
            <span className="warn">{t.proposal.removed(verdict.lostSymbols.join(', '))}</span>
          )}
        </div>
      )}

      <DiffEditor
        // The wrapper disposes its models on unmount while the widget still references
        // them, which surfaces as "TextModel got disposed". Keeping the models makes
        // teardown the widget's business, not the wrapper's.
        keepCurrentOriginalModel
        keepCurrentModifiedModel
        height="420px"
        theme="vs-dark"
        language={MONACO_LANG[selected.lang] ?? 'plaintext'}
        original={detail.source}
        modified={proposal.content}
        options={{
          readOnly: true,
          renderSideBySide: false,
          minimap: { enabled: false },
          fontSize: 11,
          scrollBeyondLastLine: false,
        }}
      />

      <div className="actions">
        <button type="button" className="primary" onClick={() => void apply()}>
          {t.proposal.apply}
        </button>
        <button type="button" onClick={discard}>
          {t.proposal.discard}
        </button>
      </div>
    </div>
  )
}
