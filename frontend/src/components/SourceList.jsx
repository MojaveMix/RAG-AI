import { useState } from 'react'
import { ChevronIcon, FileIcon } from './Icons'

export default function SourceList({ sources, title = 'Sources' }) {
  const [open, setOpen] = useState(false)
  if (!sources?.length) return null

  const score = (value) =>
    typeof value === 'number' ? `${Math.round(Math.min(Math.max(value, 0), 1) * 100)}%` : null

  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-slate-800 bg-slate-900/50">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-2 px-3 py-2 text-xs font-medium text-slate-400 transition-colors hover:text-slate-300"
      >
        <ChevronIcon
          className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${open ? 'rotate-90' : ''}`}
        />
        {title}
        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] tabular-nums text-slate-400">
          {sources.length}
        </span>
      </button>

      {open && (
        <ul className="animate-in-up space-y-2 border-t border-slate-800 p-2">
          {sources.map((source) => {
            const match = score(source.score)
            return (
              <li
                key={`${source.document_id}-${source.chunk_index}-${source.label}`}
                className="rounded-md bg-slate-950/50 p-2.5"
              >
                <div className="flex items-center gap-2">
                  <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded bg-indigo-500/20 text-[10px] font-semibold text-indigo-300">
                    {source.label}
                  </span>
                  <FileIcon className="h-3 w-3 shrink-0 text-slate-600" />
                  <span className="min-w-0 flex-1 truncate text-[11px] font-medium text-slate-300">
                    {source.filename}
                  </span>
                  {source.page && (
                    <span className="shrink-0 text-[10px] text-slate-500">p.{source.page}</span>
                  )}
                  {match && (
                    <span className="shrink-0 text-[10px] tabular-nums text-emerald-400/80">
                      {match}
                    </span>
                  )}
                </div>
                <p
                  dir="auto"
                  className="mt-1.5 line-clamp-4 text-[11px] leading-relaxed text-slate-500"
                >
                  {source.excerpt}
                </p>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
