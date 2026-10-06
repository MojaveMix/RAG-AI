import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from './lib/api'
import Composer from './components/Composer'
import DocumentSidebar from './components/DocumentSidebar'
import Message from './components/Message'
import ModelPicker, { STORAGE_KEY, readStored } from './components/ModelPicker'
import UploadZone from './components/UploadZone'
import { AlertIcon, ChevronIcon, CodeIcon, SparkIcon } from './components/Icons'

const MAX_HISTORY = 6
const MODE_STORAGE_KEY = 'rag_ai_mode'
const CODE_MODEL_STORAGE_KEY = 'rag_ai_code_model'
const ANALYSIS_MODEL_STORAGE_KEY = 'rag_ai_analysis_model'

function readStoredMode() {
  try {
    return localStorage.getItem(MODE_STORAGE_KEY) || 'code'
  } catch {
    return 'code'
  }
}

function readStoredCodeModel() {
  try {
    return localStorage.getItem(CODE_MODEL_STORAGE_KEY) || 'qwen2.5-coder:7b'
  } catch {
    return 'qwen2.5-coder:7b'
  }
}

function readStoredAnalysisModel() {
  try {
    return localStorage.getItem(ANALYSIS_MODEL_STORAGE_KEY) || 'Qwen3:8b'
  } catch {
    return 'Qwen3:8b'
  }
}

export default function App() {
  const [mode, setMode] = useState(readStoredMode)
  const [codeModel, setCodeModel] = useState(readStoredCodeModel)
  const [analysisModel, setAnalysisModel] = useState(readStoredAnalysisModel)
  const [documents, setDocuments] = useState([])
  const [selectedIds, setSelectedIds] = useState([])
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [health, setHealth] = useState(null)
  const [error, setError] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  // undefined = initial fetch in progress
  // null      = fetch completed but failed (Ollama down / backend unreachable)
  // object    = successfully loaded
  const [models, setModels] = useState(undefined)

  const activeModel = mode === 'code' ? codeModel : analysisModel

  function handleModelChange(newModel) {
    if (mode === 'code') {
      setCodeModel(newModel)
      try {
        localStorage.setItem(CODE_MODEL_STORAGE_KEY, newModel)
      } catch {
        /* ignore */
      }
    } else {
      setAnalysisModel(newModel)
      try {
        localStorage.setItem(ANALYSIS_MODEL_STORAGE_KEY, newModel)
      } catch {
        /* ignore */
      }
    }
  }

  const abortRef = useRef(null)
  const scrollRef = useRef(null)
  const bottomRef = useRef(null)

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await api.getHealth())
    } catch {
      setHealth({ status: 'down', ollama: { running: false } })
    }
  }, [])

  const refreshDocuments = useCallback(async () => {
    try {
      const { documents: list } = await api.listDocuments()
      setDocuments(list)
      // Drop selections for documents that no longer exist.
      setSelectedIds((prev) => prev.filter((id) => list.some((doc) => doc.id === id)))
    } catch (loadError) {
      setError(loadError.message)
    }
  }, [])

  const refreshModels = useCallback(async () => {
    try {
      const list = await api.listModels()
      setModels(list)
      return list
    } catch {
      // Ollama down or backend unreachable — mark as failed (null), not loading (undefined).
      setModels(null)
      return null
    }
  }, [])

  // Auto-sync installed models with dedicated code and analysis selections
  useEffect(() => {
    refreshModels().then((list) => {
      if (!list) return
      const installed = (list.chat || []).map((entry) => entry.name)

      // Sync Code Model: prefer dedicated coder model (e.g. qwen2.5-coder:7b)
      if (!installed.includes(codeModel)) {
        const fallbackCode = list.default_code_chat || list.default_chat
        if (fallbackCode) {
          setCodeModel(fallbackCode)
          try { localStorage.setItem(CODE_MODEL_STORAGE_KEY, fallbackCode) } catch {}
        }
      } else if (list.default_code_chat && !codeModel.toLowerCase().includes('coder')) {
        setCodeModel(list.default_code_chat)
        try { localStorage.setItem(CODE_MODEL_STORAGE_KEY, list.default_code_chat) } catch {}
      }

      // Sync Analysis Model: prefer document Q&A model (e.g. Qwen3:8b)
      if (!installed.includes(analysisModel)) {
        const fallbackAnalysis = list.default_analysis_chat || list.default_chat
        if (fallbackAnalysis) {
          setAnalysisModel(fallbackAnalysis)
          try { localStorage.setItem(ANALYSIS_MODEL_STORAGE_KEY, fallbackAnalysis) } catch {}
        }
      }
    })
  }, [refreshModels])

  useEffect(() => {
    try {
      localStorage.setItem(MODE_STORAGE_KEY, mode)
    } catch {
      /* ignore */
    }
  }, [mode])

  useEffect(() => {
    refreshHealth()
    refreshDocuments()
    const timer = setInterval(refreshHealth, 15000)
    return () => clearInterval(timer)
  }, [refreshHealth, refreshDocuments])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: busy ? 'auto' : 'smooth' })
  }, [messages, busy])

  const readyDocuments = documents.filter((doc) => doc.status === 'ready')
  const hasDocuments = readyDocuments.length > 0
  const ollamaDown = health && health.status !== 'ok'
  // Only show the "no chat model" warning when the catalog successfully loaded but is empty.
  const noChatModel = models != null && !(models.chat || []).length

  function toggleDocument(id) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((value) => value !== id) : [...prev, id],
    )
  }

  function selectAll() {
    setSelectedIds((prev) =>
      prev.length === readyDocuments.length ? [] : readyDocuments.map((doc) => doc.id),
    )
  }

  async function handleDelete(doc) {
    if (!window.confirm(`Delete "${doc.filename}"? Its chunks will be removed from the index.`)) {
      return
    }
    try {
      await api.deleteDocument(doc.id)
      setSelectedIds((prev) => prev.filter((id) => id !== doc.id))
      await refreshDocuments()
    } catch (deleteError) {
      setError(deleteError.message)
    }
  }

  async function handleUploaded() {
    await refreshDocuments()
    setSelectedIds((prev) => prev)
  }

  function stop() {
    abortRef.current?.()
    abortRef.current = null
    setBusy(false)
    setMessages((prev) => prev.map((msg) => ({ ...msg, streaming: false })))
  }

  async function handleSubmit() {
    const question = input.trim()
    if (!question || busy) return

    setError('')
    setInput('')

    const history = messages
      .filter((msg) => !msg.error && msg.content?.trim())
      .slice(-MAX_HISTORY)
      .map((msg) => ({ role: msg.role, content: msg.content }))

    const answerId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    setMessages((prev) => [
      ...prev,
      { id: `u-${answerId}`, role: 'user', content: question },
      {
        id: answerId,
        role: 'assistant',
        content: '',
        sources: [],
        streaming: true,
      },
    ])
    setBusy(true)

    const patch = (changes) =>
      setMessages((prev) => prev.map((msg) => (msg.id === answerId ? { ...msg, ...changes } : msg)))

    abortRef.current = api.streamChat({
      question,
      documentIds: selectedIds,
      history,
      model: activeModel,
      mode,
      handlers: {
        onSources: (sources) => patch({ sources }),
        onDelta: (delta) =>
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === answerId ? { ...msg, content: msg.content + delta } : msg,
            ),
          ),
        onError: (streamError) => patch({ error: streamError.message, streaming: false }),
        onDone: () => patch({ streaming: false }),
      },
    })
  }

  return (
    <div className="flex h-full">
      {/* ---- Sidebar ---- */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-80 shrink-0 flex-col gap-5 border-r border-slate-800 bg-slate-900/40 p-4 transition-transform duration-200 lg:static lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center gap-2.5">
          <div
            className={`flex h-8 w-8 items-center justify-center rounded-lg text-white shadow-md transition-all ${
              mode === 'code'
                ? 'bg-gradient-to-br from-cyan-500 to-indigo-600 shadow-cyan-950/50'
                : 'bg-gradient-to-br from-indigo-500 to-violet-600 shadow-indigo-950/50'
            }`}
          >
            {mode === 'code' ? <CodeIcon className="h-4 w-4" /> : <SparkIcon className="h-4 w-4" />}
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold text-slate-100">
              {mode === 'code' ? 'RAG Code AI' : 'RAG AI Analysis'}
            </h1>
            <p className="truncate text-[10px] text-slate-500">
              {mode === 'code' ? 'Codex & Claude Code · local' : 'Document Intelligence · local'}
            </p>
          </div>
        </div>

        <UploadZone onUploaded={handleUploaded} mode={mode} />

        <div className="min-h-0 flex-1">
          <DocumentSidebar
            documents={documents}
            selectedIds={selectedIds}
            onToggle={toggleDocument}
            onSelectAll={selectAll}
            onDelete={handleDelete}
            mode={mode}
          />
        </div>

        {models?.default_embed && (
          <div className="border-t border-slate-800 pt-3 text-[10px] text-slate-500">
            <div className="flex items-center justify-between">
              <span>embed</span>
              <span className="truncate pl-2 font-mono">{models.default_embed}</span>
            </div>
          </div>
        )}
      </aside>

      {sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-20 bg-slate-950/70 backdrop-blur-sm lg:hidden"
        />
      )}

      {/* ---- Chat ---- */}
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center gap-3 border-b border-slate-800/80 px-4 py-3">
          <button
            type="button"
            onClick={() => setSidebarOpen((value) => !value)}
            className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-200 lg:hidden"
            aria-label="Toggle sidebar"
          >
            <ChevronIcon className="h-4 w-4" />
          </button>

          {/* Mode Switcher Segmented Control */}
          <div className="flex items-center rounded-xl border border-slate-800 bg-slate-900/90 p-0.5 shadow-inner">
            <button
              type="button"
              onClick={() => setMode('code')}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold transition-all ${
                mode === 'code'
                  ? 'border border-cyan-500/40 bg-gradient-to-r from-cyan-500/20 to-indigo-500/20 text-cyan-300 shadow-sm shadow-cyan-950/50'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <CodeIcon className="h-3.5 w-3.5" />
              <span>RAG Code AI</span>
            </button>
            <button
              type="button"
              onClick={() => setMode('analysis')}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold transition-all ${
                mode === 'analysis'
                  ? 'border border-indigo-500/40 bg-gradient-to-r from-indigo-500/20 to-violet-500/20 text-indigo-300 shadow-sm shadow-indigo-950/50'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <SparkIcon className="h-3.5 w-3.5" />
              <span>RAG AI Analysis</span>
            </button>
          </div>

          <h2 className="hidden min-w-0 flex-1 truncate text-xs text-slate-400 sm:block">
            {hasDocuments
              ? selectedIds.length === 0
                ? mode === 'code'
                  ? `Repo context: all ${readyDocuments.length} files`
                  : `Context: all ${readyDocuments.length} documents`
                : selectedIds.length === 1
                  ? 'Context: 1 selected file'
                  : `Context: ${selectedIds.length} selected files`
              : mode === 'code'
                ? 'Codex & Claude Code generator'
                : 'No documents loaded'}
          </h2>

          <div className="ml-auto flex items-center gap-2">
            <ModelPicker
              models={models}
              value={activeModel}
              onChange={handleModelChange}
              disabled={busy}
              ollamaDown={ollamaDown}
              onRefresh={refreshModels}
              embeddingModel={models?.default_embed || health?.ollama?.embed_model}
              embeddingNote={
                models?.default_embed && models?.default_embed !== health?.ollama?.embed_model
                  ? 'Catalog differs from .env; uploads still use the configured embed model.'
                  : null
              }
              mode={mode}
            />
            {selectedIds.length > 0 && (
              <button
                type="button"
                onClick={() => setSelectedIds([])}
                className="shrink-0 rounded-lg bg-indigo-500/15 px-2.5 py-1 text-[11px] font-medium text-indigo-300 transition-colors hover:bg-indigo-500/25"
              >
                Search all
              </button>
            )}
          </div>
        </header>

        {noChatModel && (
          <div className="flex items-start gap-2 border-b border-amber-500/20 bg-amber-500/10 px-4 py-2.5 text-xs text-amber-200">
            <AlertIcon className="mt-px h-4 w-4 shrink-0" />
            <span>
              No chat model is installed. Pull one to start answering, for example{' '}
              <code className="font-mono">ollama pull qwen3:8b</code>.
            </span>
          </div>
        )}

        {ollamaDown && (
          <div className="flex items-start gap-2 border-b border-amber-500/20 bg-amber-500/10 px-4 py-2.5 text-xs text-amber-200">
            <AlertIcon className="mt-px h-4 w-4 shrink-0" />
            <span>
              Ollama is not reachable at <code className="font-mono">{health?.ollama?.host}</code>.
              Start it with <code className="font-mono">ollama serve</code>, then reload.
            </span>
          </div>
        )}

        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-4 py-6">
            {messages.length === 0 ? (
              <EmptyState hasDocuments={hasDocuments} onPick={setInput} mode={mode} />
            ) : (
              <div className="space-y-6">
                {messages.map((message) => (
                  <Message key={message.id} message={message} mode={mode} />
                ))}
              </div>
            )}

            {error && (
              <div className="mt-6 flex items-start gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-200">
                <AlertIcon className="mt-px h-4 w-4 shrink-0" />
                <span className="min-w-0 break-words">{error}</span>
                <button
                  type="button"
                  onClick={() => setError('')}
                  className="ml-auto shrink-0 text-rose-400 hover:text-rose-300"
                >
                  Dismiss
                </button>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        </div>

        <Composer
          value={input}
          onChange={setInput}
          onSubmit={handleSubmit}
          onStop={stop}
          busy={busy}
          disabled={
            mode === 'code'
              ? ollamaDown || noChatModel
              : !hasDocuments || ollamaDown || noChatModel
          }
          hasDocuments={hasDocuments}
          mode={mode}
        />
      </main>
    </div>
  )
}

function EmptyState({ hasDocuments, onPick, mode = 'code' }) {
  const codePrompts = [
    'Generate a FastAPI auth middleware with JWT tokens',
    'Explain the architecture and data flow of this codebase',
    'Find bugs, edge cases and write unit tests for this code',
    'Refactor this code to improve performance and readability',
  ]
  const analysisPrompts = [
    'What is this document about?',
    'Give me a summary with the key points.',
    'List any dates, figures or names it mentions.',
  ]
  const prompts = mode === 'code' ? codePrompts : analysisPrompts

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center text-center">
      <div
        className={`flex h-14 w-14 items-center justify-center rounded-2xl text-white shadow-2xl ${
          mode === 'code'
            ? 'bg-gradient-to-br from-cyan-500 to-indigo-600 shadow-cyan-950/60'
            : 'bg-gradient-to-br from-indigo-500 to-violet-600 shadow-indigo-950/60'
        }`}
      >
        {mode === 'code' ? <CodeIcon className="h-7 w-7" /> : <SparkIcon className="h-7 w-7" />}
      </div>
      <h3 className="mt-5 text-lg font-semibold text-slate-100">
        {mode === 'code'
          ? 'RAG Code AI · Codex & Claude Code'
          : hasDocuments
            ? 'Ask about your documents'
            : 'Upload a document to begin'}
      </h3>
      <p className="mt-1.5 max-w-md text-sm text-slate-400">
        {mode === 'code'
          ? hasDocuments
            ? 'Your codebase is indexed locally. Ask to generate complete features, refactor components, or debug functions.'
            : 'Generate production-ready code directly like Codex or Claude Code, or drop any source files / zip repos to query with repository context.'
          : hasDocuments
            ? 'Your files are indexed locally. Select specific ones in the sidebar, or ask across all of them.'
            : 'Upload a PDF, DOCX, TXT or MD file. It is parsed, chunked and embedded locally with Ollama — nothing leaves your machine.'}
      </p>

      <div className="mt-6 flex flex-wrap justify-center gap-2">
        {prompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => onPick(prompt)}
            className={`rounded-full border border-slate-800 bg-slate-900/60 px-3 py-1.5 text-xs text-slate-400 transition-colors hover:border-slate-700 ${
              mode === 'code' ? 'hover:text-cyan-300' : 'hover:text-slate-200'
            }`}
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  )
}
