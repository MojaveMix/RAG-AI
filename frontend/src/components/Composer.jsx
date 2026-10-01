import { useEffect, useRef } from 'react'
import { SendIcon, StopIcon } from './Icons'

const SUGGESTIONS = [
  'Summarise this document in a few bullet points.',
  'What are the key dates, names and numbers mentioned?',
  'What are the main conclusions or recommendations?',
]

export default function Composer({ value, onChange, onSubmit, onStop, busy, disabled, hasDocuments }) {
  const ref = useRef(null)

  useEffect(() => {
    const node = ref.current
    if (!node) return
    node.style.height = 'auto'
    node.style.height = `${Math.min(node.scrollHeight, 180)}px`
  }, [value])

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (!busy && !disabled && value.trim()) onSubmit()
    }
  }

  return (
    <div className="border-t border-slate-800/80 bg-slate-950/80 backdrop-blur">
      {!hasDocuments && (
        <div className="mx-auto max-w-3xl px-4 pt-3">
          <p className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
            Upload a PDF, DOCX, TXT or MD file first — answers are grounded in your documents.
          </p>
        </div>
      )}

      {hasDocuments && !value && !busy && (
        <div className="mx-auto max-w-3xl px-4 pt-3">
          <div className="flex flex-wrap gap-1.5">
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => onChange(suggestion)}
                className="rounded-full border border-slate-800 bg-slate-900/60 px-2.5 py-1 text-[11px] text-slate-400 transition-colors hover:border-slate-700 hover:text-slate-200"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="mx-auto max-w-3xl px-4 py-3">
        <div className="flex items-end gap-2 rounded-2xl border border-slate-800 bg-slate-900/70 p-2 transition-colors focus-within:border-slate-600">
          <textarea
            ref={ref}
            rows={1}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about your documents…"
            disabled={disabled}
            className="max-h-44 min-h-[2.5rem] flex-1 resize-none bg-transparent px-2 py-2 text-sm leading-relaxed text-slate-100 placeholder:text-slate-500 focus:outline-none disabled:opacity-50"
          />

          {busy ? (
            <button
              type="button"
              onClick={onStop}
              aria-label="Stop generating"
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-700 text-slate-200 transition-colors hover:bg-slate-600"
            >
              <StopIcon className="h-4 w-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={onSubmit}
              disabled={disabled || !value.trim()}
              aria-label="Send message"
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white transition-all hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-600"
            >
              <SendIcon className="h-4 w-4" />
            </button>
          )}
        </div>

        <p className="mt-2 text-center text-[10px] text-slate-600">
          Answers are generated from your documents and may be inaccurate. Press Enter to send,
          Shift + Enter for a new line.
        </p>
      </div>
    </div>
  )
}
