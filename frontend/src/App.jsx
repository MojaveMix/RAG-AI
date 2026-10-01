import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from './lib/api'
import Composer from './components/Composer'
import DocumentSidebar from './components/DocumentSidebar'
import Message from './components/Message'
import ModelPicker, { STORAGE_KEY, readStored } from './components/ModelPicker'
import UploadZone from './components/UploadZone'
import { AlertIcon, ChevronIcon, SparkIcon } from './components/Icons'

const MAX_HISTORY = 6

export default function App() {
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
  const [model, setModel] = useState(readStored)

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

  // Keep the selection pointing at something installed: fall back to the
  // backend's recommended default when the stored model is gone.
  useEffect(() => {
    refreshModels().then((list) => {
      if (!list) return
      const installed = (list.chat || []).map((entry) => entry.name)
      const current = installed.find((name) => name === model)
      if (current) return
      const fallback = installed.includes(model) ? model : list.default_chat
      if (fallback) setModel(fallback)
    })
    // Runs once on mount; `model` is intentionally not a dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshModels])

  useEffect(() => {
    if (!model) return
    try {
      localStorage.setItem(STORAGE_KEY, model)
    } catch {
      /* private browsing: the selection just will not persist */
    }
  }, [model])

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
      // Empty array means "search everything"; null would too, but be explicit.
      documentIds: selectedIds,
      history,
      model,
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
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-white">
            <SparkIcon className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold text-slate-100">RAG AI</h1>
            <p className="truncate text-[10px] text-slate-500">Powered by Ollama · local</p>
          </div>
        </div>

        <UploadZone onUploaded={handleUploaded} />

        <div className="min-h-0 flex-1">
          <DocumentSidebar
            documents={documents}
            selectedIds={selectedIds}
            onToggle={toggleDocument}
            onSelectAll={selectAll}
            onDelete={handleDelete}
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
        <header className="flex items-center gap-3 border-b border-slate-800/80 px-4 py-3">
          <button
            type="button"
            onClick={() => setSidebarOpen((value) => !value)}
            className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-200 lg:hidden"
            aria-label="Toggle sidebar"
          >
            <ChevronIcon className="h-4 w-4" />
          </button>
          <h2 className="min-w-0 flex-1 truncate text-sm font-medium text-slate-200">
            {hasDocuments
              ? selectedIds.length === 0
                ? `Asking across all ${readyDocuments.length} documents`
                : selectedIds.length === 1
                  ? 'Asking 1 document'
                  : `Asking ${selectedIds.length} documents`
              : 'No documents loaded'}
          </h2>
          <ModelPicker
            models={models}
            value={model}
            onChange={setModel}
            disabled={busy}
            ollamaDown={ollamaDown}
            onRefresh={refreshModels}
            embeddingModel={models?.default_embed || health?.ollama?.embed_model}
            embeddingNote={
              models?.default_embed && models?.default_embed !== health?.ollama?.embed_model
                ? 'Catalog differs from .env; uploads still use the configured embed model.'
                : null
            }
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
              <EmptyState hasDocuments={hasDocuments} onPick={setInput} />
            ) : (
              <div className="space-y-6">
                {messages.map((message) => (
                  <Message key={message.id} message={message} />
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
          disabled={!hasDocuments || ollamaDown || noChatModel}
          hasDocuments={hasDocuments}
        />
      </main>
    </div>
  )
}

function EmptyState({ hasDocuments, onPick }) {
  const prompts = [
    'What is this document about?',
    'Give me a summary with the key points.',
    'List any dates, figures or names it mentions.',
  ]

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-2xl shadow-indigo-950/60">
        <SparkIcon className="h-7 w-7" />
      </div>
      <h3 className="mt-5 text-lg font-semibold text-slate-100">
        {hasDocuments ? 'Ask about your documents' : 'Upload a document to begin'}
      </h3>
      <p className="mt-1.5 max-w-sm text-sm text-slate-500">
        {hasDocuments
          ? 'Your files are indexed locally. Select specific ones in the sidebar, or ask across all of them.'
          : 'Upload a PDF, DOCX, TXT or MD file. It is parsed, chunked and embedded locally with Ollama — nothing leaves your machine.'}
      </p>

      {hasDocuments && (
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {prompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => onPick(prompt)}
              className="rounded-full border border-slate-800 bg-slate-900/60 px-3 py-1.5 text-xs text-slate-400 transition-colors hover:border-slate-700 hover:text-slate-200"
            >
              {prompt}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
