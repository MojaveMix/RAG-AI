import { useEffect, useRef, useState } from 'react'
import { CheckIcon, ChevronIcon, CodeIcon, SparkIcon } from './Icons'

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
          {model.is_code ? (
            <span className="shrink-0 rounded bg-cyan-500/20 px-1 py-px text-[9px] font-semibold uppercase tracking-wide text-cyan-300">
              CODE
            </span>
          ) : model.recommended ? (
            <span className="shrink-0 rounded bg-emerald-500/20 px-1 py-px text-[9px] font-semibold uppercase tracking-wide text-emerald-300">
              RAG
            </span>
          ) : null}
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

function SuggestionRow({ suggestion, isCode }) {
  return (
    <div className="flex items-start gap-2.5 rounded-lg px-2.5 py-2">
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-1.5">
          <span className="truncate text-xs font-medium text-slate-500">{suggestion.model}</span>
          <span className={`shrink-0 rounded px-1 py-px text-[9px] font-semibold uppercase tracking-wide ${isCode ? 'bg-cyan-500/10 text-cyan-400' : 'bg-slate-800 text-slate-500'}`}>
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

export default function ModelPicker({
  models,
  value,
  onChange,
  disabled,
  onRefresh,
  embeddingModel,
  embeddingNote,
  ollamaDown,
  mode = 'code',
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

  const isLoading = models === undefined
  const isFailed  = models === null
  const isLoaded  = models != null

  const chatModels = isLoaded ? (models.chat || []) : []
  const selected = chatModels.find((m) => m.name === value) || null

  const codeModels = chatModels.filter((m) => m.is_code)
  const analysisModels = chatModels.filter((m) => !m.is_code)

  // Primary list vs secondary list based on active mode
  const primaryModels = mode === 'code' ? (codeModels.length > 0 ? codeModels : chatModels) : analysisModels
  const secondaryModels = mode === 'code' ? (codeModels.length > 0 ? analysisModels : []) : codeModels

  const suggestions = isLoaded
    ? mode === 'code'
      ? (models.suggested_code && models.suggested_code.length > 0 ? models.suggested_code : models.suggested_chat || [])
      : (models.suggested_analysis && models.suggested_analysis.length > 0 ? models.suggested_analysis : models.suggested_chat || [])
    : []

  // Label shown on the collapsed trigger button
  const triggerLabel = isLoading
    ? 'Loading models…'
    : isFailed || ollamaDown
    ? 'Ollama offline'
    : selected
    ? selected.name
    : value || 'Select a model'

  function handleTriggerClick() {
    setOpen((prev) => {
      const next = !prev
      if (next) onRefresh?.()
      return next
    })
  }

  return (
    <div className="relative" ref={ref}>
      {/* ── Trigger button ── */}
      <button
        type="button"
        onClick={handleTriggerClick}
        disabled={disabled}
        aria-expanded={open}
        aria-haspopup="listbox"
        className="flex max-w-[16rem] items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-1.5 text-xs text-slate-300 transition-colors hover:border-slate-700 hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {mode === 'code' ? (
          <CodeIcon className="h-3.5 w-3.5 shrink-0 text-cyan-400" />
        ) : (
          <SparkIcon className="h-3.5 w-3.5 shrink-0 text-indigo-400" />
        )}
        <span className="truncate">{triggerLabel}</span>
        {selected?.is_code ? (
          <span className="shrink-0 rounded bg-cyan-500/20 px-1 py-px text-[9px] font-semibold uppercase tracking-wide text-cyan-300">
            CODE
          </span>
        ) : selected?.recommended ? (
          <span className="shrink-0 rounded bg-emerald-500/20 px-1 py-px text-[9px] font-semibold uppercase tracking-wide text-emerald-300">
            RAG
          </span>
        ) : null}
        <ChevronIcon
          className={`h-3.5 w-3.5 shrink-0 text-slate-500 transition-transform ${open ? 'rotate-90' : ''}`}
        />
      </button>

      {/* ── Dropdown panel ── */}
      {open && (
        <div className="animate-in-up absolute right-0 z-40 mt-1.5 w-[22rem] max-w-[calc(100vw-2rem)] rounded-xl border border-slate-800 bg-slate-900 p-1.5 shadow-2xl shadow-slate-950/80">
          <div className="flex items-center justify-between px-2.5 pb-1 pt-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
              {mode === 'code' ? 'Code Generation Model' : 'Document Analysis Model'}
            </p>
            <button
              type="button"
              onClick={() => onRefresh?.()}
              className="text-[10px] text-cyan-400 transition-colors hover:text-cyan-300 font-medium"
            >
              ↻ Rescan Ollama
            </button>
          </div>

          {/* ── State-driven body ── */}
          {isLoading ? (
            <p className="px-2.5 py-3 text-[11px] leading-relaxed text-slate-500">
              Connecting to Ollama…
            </p>
          ) : isFailed || ollamaDown ? (
            <p className="px-2.5 py-3 text-[11px] leading-relaxed text-amber-400">
              Cannot reach Ollama at localhost:11434.{' '}
              <span className="text-slate-400">
                Start with <code className="font-mono text-slate-300">ollama serve</code>, then{' '}
              </span>
              <button
                type="button"
                onClick={() => onRefresh?.()}
                className="text-indigo-400 underline hover:text-indigo-300"
              >
                rescan
              </button>
              .
            </p>
          ) : chatModels.length === 0 ? (
            <p className="px-2.5 py-3 text-[11px] leading-relaxed text-slate-500">
              No models found. Pull one with{' '}
              <code className="font-mono text-slate-400">
                ollama pull {mode === 'code' ? 'qwen2.5-coder:7b' : 'qwen3:8b'}
              </code>.
            </p>
          ) : (
            <div className="max-h-80 overflow-y-auto space-y-2">
              {/* Primary list */}
              <div>
                <p className="px-2.5 py-1 text-[10px] font-medium text-slate-500">
                  {mode === 'code'
                    ? codeModels.length > 0
                      ? '⚡ Dedicated Coding Models'
                      : '⚡ Recommended Models for Code'
                    : '📄 Document & Analysis Models'}
                </p>
                <div className="space-y-0.5">
                  {primaryModels.map((m) => (
                    <ModelRow
                      key={m.name}
                      model={m}
                      selected={m.name === value}
                      onSelect={() => { onChange(m.name); setOpen(false) }}
                    />
                  ))}
                </div>
              </div>

              {/* Secondary list */}
              {secondaryModels.length > 0 && (
                <div className="border-t border-slate-800/80 pt-1.5">
                  <p className="px-2.5 py-1 text-[10px] font-medium text-slate-500">
                    {mode === 'code' ? '📄 General & Document Models' : '⚡ Dedicated Code Models'}
                  </p>
                  <div className="space-y-0.5">
                    {secondaryModels.map((m) => (
                      <ModelRow
                        key={m.name}
                        model={m}
                        selected={m.name === value}
                        onSelect={() => { onChange(m.name); setOpen(false) }}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Not-installed suggestions */}
          {isLoaded && suggestions.length > 0 && (
            <div className="border-t border-slate-800 pt-1.5">
              <p className="px-2.5 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                {mode === 'code' ? 'Suggested Code Models' : 'Suggested Analysis Models'}
              </p>
              <div className="max-h-36 space-y-0.5 overflow-y-auto">
                {suggestions.map((suggestion) => (
                  <SuggestionRow
                    key={suggestion.model}
                    suggestion={suggestion}
                    isCode={mode === 'code'}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Embedding model footer */}
          {embeddingModel && (
            <p className="border-t border-slate-800 px-2.5 pb-1.5 pt-2 text-[10px] leading-relaxed text-slate-500">
              Retrieval embedding: <span className="font-medium text-slate-400">{embeddingModel}</span>
              {embeddingNote ? ` — ${embeddingNote}` : ''}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export { readStored, STORAGE_KEY }
