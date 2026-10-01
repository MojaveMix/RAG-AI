import { AlertIcon, DatabaseIcon, FileIcon, TrashIcon } from './Icons'

function formatSize(bytes) {
  if (!bytes) return ''
  const units = ['B', 'KB', 'MB', 'GB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value < 10 && unit > 0 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`
}

export default function DocumentSidebar({ documents, selectedIds, onToggle, onSelectAll, onDelete }) {
  const ready = documents.filter((doc) => doc.status === 'ready')

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-1">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          <DatabaseIcon className="h-3.5 w-3.5" />
          Documents
          <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] tabular-nums text-slate-400">
            {ready.length}
          </span>
        </h2>
        {ready.length > 0 && (
          <button
            type="button"
            onClick={onSelectAll}
            className="text-[11px] text-slate-500 transition-colors hover:text-indigo-400"
          >
            {selectedIds.length === ready.length ? 'Clear' : 'Select all'}
          </button>
        )}
      </div>

      <div className="mt-3 flex-1 space-y-1.5 overflow-y-auto pr-1">
        {documents.length === 0 ? (
          <p className="rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-6 text-center text-xs text-slate-500">
            No documents yet.
            <br />
            Upload a file to get started.
          </p>
        ) : (
          documents.map((doc) => {
            const active = selectedIds.includes(doc.id)
            const failed = doc.status === 'failed'

            return (
              <div
                key={doc.id}
                className={`group rounded-lg border p-2.5 transition-colors ${
                  failed
                    ? 'border-rose-500/30 bg-rose-500/5'
                    : active
                      ? 'border-indigo-500/50 bg-indigo-500/10'
                      : 'border-transparent bg-slate-900/50 hover:border-slate-700'
                }`}
              >
                <div className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    checked={active}
                    disabled={failed}
                    onChange={() => onToggle(doc.id)}
                    className="mt-1 h-3.5 w-3.5 shrink-0 cursor-pointer accent-indigo-500 disabled:cursor-not-allowed disabled:opacity-40"
                    aria-label={`Use ${doc.filename} in answers`}
                  />
                  <div className="min-w-0 flex-1">
                    <p
                      className={`truncate text-xs font-medium ${
                        failed ? 'text-rose-300' : 'text-slate-200'
                      }`}
                      title={doc.filename}
                    >
                      {doc.filename}
                    </p>
                    <p className="mt-0.5 text-[10px] text-slate-500">
                      {failed ? (
                        <span className="text-rose-400">failed</span>
                      ) : (
                        <>
                          {formatSize(doc.size_bytes)}
                          {' · '}
                          {doc.indexed_chunks ?? doc.chunks ?? 0} chunks
                          {doc.pages ? ` · ${doc.pages} pages` : ''}
                        </>
                      )}
                    </p>
                    {failed && doc.error && (
                      <p className="mt-1 flex items-start gap-1 text-[10px] leading-relaxed text-rose-300/80">
                        <AlertIcon className="mt-px h-3 w-3 shrink-0" />
                        <span className="min-w-0 break-words">{doc.error}</span>
                      </p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => onDelete(doc)}
                    aria-label={`Delete ${doc.filename}`}
                    className="shrink-0 rounded p-1 text-slate-600 opacity-0 transition-all hover:bg-rose-500/10 hover:text-rose-400 focus-visible:opacity-100 group-hover:opacity-100"
                  >
                    <TrashIcon className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )
          })
        )}
      </div>

      {documents.some((doc) => doc.status !== 'ready') && (
        <p className="mt-3 flex items-start gap-1.5 px-1 text-[10px] leading-relaxed text-slate-500">
          <FileIcon className="mt-px h-3 w-3 shrink-0" />
          Failed uploads are excluded from answers. Delete them to retry.
        </p>
      )}
    </div>
  )
}
