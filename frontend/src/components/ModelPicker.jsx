import { useEffect, useRef, useState } from 'react'
import { CheckIcon, ChevronIcon, SparkIcon } from './Icons'

const STORAGE_KEY = 'rag.chatModel'

function readStored() {
  try {
    return localStorage.getItem(STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

function sizeLabel(sizeGb) {
  if (typeof sizeGb !== 'number') return null
  return `${sizeGb} GB`
}

function metaLabel(model) {
  if (model.remote) return 'runs on ollama.com, not local'
  return [model.parameters, model.quantization, sizeLabel(model.size_gb)]
    .filter(Boolean)
    .join(' · ')
}

function ModelRow({ model, selected, onSelect }) {
  const meta = metaLabel(model)

  return (
    <button
      type="button"
      onClick={onSelect}
      className={`flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors ${
        selected ? 'bg-indigo-500/15' : 'hover:bg-slate-800/70'
      }`}
    >
      <span
        className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
          selected
            ? 'border-indigo-400 bg-indigo-500/30 text-indigo-200'
            : 'border-slate-700 text-transparent'
        }`}
      >
        <CheckIcon className="h-3 w-3" />
      </span>

      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-1.5">
          <span className="truncate text-xs font-medium text-slate-200">{model.name}</span>
          {model.recommended && (
            <span className="shrink-0 rounded bg-emerald-500/20 px-1 py-px text-[9px] font-semibold uppercase tracking-wide text-emerald-300">
              RAG
            </span>
          )}
        </span>
        {meta && (
          <span className="mt-0.5 block text-[10px] text-slate-500">
            {meta}
            {model.context_length ? ` · ctx ${Math.round(model.context_length / 1024)}k` : ''}
          </span>
        )}
        {model.blurb && (
          <span className="mt-0.5 block text-[10px] leading-snug text-slate-500">
            {model.blurb}
          </span>
        )}
      </span>
    </button>
  )
}

function SuggestionRow({ suggestion }) {
  return (
    <div className="flex items-start gap-2.5 rounded-lg px-2.5 py-2">
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-1.5">
          <span className="truncate text-xs font-medium text-slate-500">{suggestion.model}</span>
          <span className="shrink-0 rounded bg-slate-800 px-1 py-px text-[9px] font-semibold uppercase tracking-wide text-slate-500">
            not installed
          </span>
        </span>
        {suggestion.blurb && (
          <span className="mt-0.5 block text-[10px] leading-snug text-slate-600">
            {suggestion.blurb}
          </span>
        )}
        <code className="mt-1 block truncate rounded bg-slate-950/60 px-1.5 py-1 font-mono text-[10px] text-slate-400">
          {suggestion.pull}
        </code>
      </span>
    </div>
  )
}

// models prop has 3 possible values:
//   undefined → initial fetch still in progress
//   null      → fetch failed (Ollama/backend unreachable)
//   object    → successfully loaded from /api/models
export default function ModelPicker({
  models,
  value,
  onChange,
  disabled,
  onRefresh,
  embeddingModel,
  embeddingNote,
  ollamaDown,
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    function onPointerDown(event) {
      if (!ref.current?.contains(event.target)) setOpen(false)
    }
    function onKeyDown(event) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  const isLoading = models === undefined   // fetch in flight
  const isFailed  = models === null        // fetch done but errored
  const isLoaded  = models != null         // object with .chat etc.

  const chatModels  = isLoaded ? (models.chat || []) : []
  const ragModels   = chatModels.filter((m) => m.recommended)
  const selected    = chatModels.find((m) => m.name === value) || null
  const suggestions = isLoaded ? (models.suggested_chat || []) : []

  // Label shown on the collapsed trigger button
  const triggerLabel = isLoading
    ? 'Loading models…'
    : isFailed || ollamaDown
    ? 'Ollama offline'
    : selected
    ? selected.name
    : value || 'Select a model'

  return (
    <div className="relative" ref={ref}>
      {/* ── Trigger button ── */}
      <button
        type="button"
        onClick={() => setOpen((s) => !s)}
        disabled={disabled}
        aria-expanded={open}
        aria-haspopup="listbox"
        className="flex max-w-[15rem] items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-1.5 text-xs text-slate-300 transition-colors hover:border-slate-700 hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <SparkIcon className="h-3.5 w-3.5 shrink-0 text-indigo-400" />
        <span className="truncate">{triggerLabel}</span>
        {selected?.recommended && (
          <span className="shrink-0 rounded bg-emerald-500/20 px-1 py-px text-[9px] font-semibold uppercase tracking-wide text-emerald-300">
            RAG
          </span>
        )}
        <ChevronIcon
          className={`h-3.5 w-3.5 shrink-0 text-slate-500 transition-transform ${open ? 'rotate-90' : ''}`}
        />
      </button>

      {/* ── Dropdown panel ── */}
      {open && (
        <div className="animate-in-up absolute right-0 z-40 mt-1.5 w-[21rem] max-w-[calc(100vw-2rem)] rounded-xl border border-slate-800 bg-slate-900 p-1.5 shadow-2xl shadow-slate-950/80">
          <div className="flex items-center justify-between px-2.5 pb-1 pt-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Answer model
            </p>
            <button
              type="button"
              onClick={() => { onRefresh?.(); setOpen(false) }}
              className="text-[10px] text-slate-500 transition-colors hover:text-indigo-300"
            >
              Rescan
            </button>
          </div>

          {/* ── State-driven body ── */}
          {isLoading ? (
            /* Still waiting for the first response */
            <p className="px-2.5 py-3 text-[11px] leading-relaxed text-slate-500">
              Connecting to backend…{' '}
              <button
                type="button"
                onClick={() => { onRefresh?.(); setOpen(false) }}
                className="text-indigo-400 underline hover:text-indigo-300"
              >
                retry
              </button>
            </p>
          ) : isFailed || ollamaDown ? (
            /* Fetch completed but failed */
            <p className="px-2.5 py-3 text-[11px] leading-relaxed text-amber-400">
              Cannot reach Ollama or the backend.{' '}
              <span className="text-slate-400">
                Start it with{' '}
                <code className="font-mono text-slate-300">ollama serve</code>, then{' '}
              </span>
              <button
                type="button"
                onClick={() => { onRefresh?.(); setOpen(false) }}
                className="text-indigo-400 underline hover:text-indigo-300"
              >
                rescan
              </button>
              .
            </p>
          ) : ragModels.length === 0 ? (
            /* Loaded but no RAG-suitable models installed */
            <p className="px-2.5 py-3 text-[11px] leading-relaxed text-slate-500">
              No RAG-optimised models found. Pull one with{' '}
              <code className="font-mono text-slate-400">ollama pull qwen3:8b</code>.
            </p>
          ) : (
            /* RAG-recommended models only */
            <div className="max-h-80 overflow-y-auto">
              <div className="space-y-0.5">
                {ragModels.map((model) => (
                  <ModelRow
                    key={model.name}
                    model={model}
                    selected={model.name === value}
                    onSelect={() => { onChange(model.name); setOpen(false) }}
                  />
                ))}
              </div>
            </div>
          )}


          {/* Not-installed suggestions */}
          {isLoaded && suggestions.length > 0 && (
            <>
              <p className="border-t border-slate-800 px-2.5 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Recommended, not installed
              </p>
              <div className="max-h-40 space-y-0.5 overflow-y-auto">
                {suggestions.map((suggestion) => (
                  <SuggestionRow key={suggestion.model} suggestion={suggestion} />
                ))}
              </div>
            </>
          )}

          {/* Embedding model footer */}
          {embeddingModel && (
            <p className="border-t border-slate-800 px-2.5 pb-1.5 pt-2 text-[10px] leading-relaxed text-slate-500">
              Retrieval uses{' '}
              <span className="font-medium text-slate-400">{embeddingModel}</span>
              {embeddingNote ? ` — ${embeddingNote}` : '. Re-upload documents to change it.'}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export { readStored, STORAGE_KEY }
