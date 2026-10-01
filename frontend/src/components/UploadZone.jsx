import { useRef, useState } from 'react'
import { uploadDocument } from '../lib/api'
import { AlertIcon, CheckIcon, FileIcon, UploadIcon } from './Icons'

const ACCEPT = '.pdf,.docx,.txt,.md,.markdown'

export default function UploadZone({ onUploaded }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [queue, setQueue] = useState([])
  const [error, setError] = useState('')

  async function handleFiles(fileList) {
    const files = Array.from(fileList ?? [])
    if (!files.length) return

    setError('')
    for (const file of files) {
      const id = `${file.name}-${file.size}-${Math.random().toString(36).slice(2, 8)}`
      setQueue((prev) => [
        ...prev,
        { id, name: file.name, size: file.size, progress: 0, status: 'uploading' },
      ])

      try {
        await uploadDocument(file, (progress) => {
          setQueue((prev) =>
            prev.map((item) => (item.id === id ? { ...item, progress } : item)),
          )
        })
        setQueue((prev) =>
          prev.map((item) =>
            item.id === id ? { ...item, status: 'done', progress: 100 } : item,
          ),
        )
        onUploaded?.()
      } catch (uploadError) {
        setQueue((prev) => prev.filter((item) => item.id !== id))
        setError(uploadError.message)
      }
    }
  }

  function onDrop(event) {
    event.preventDefault()
    setDragging(false)
    handleFiles(event.dataTransfer.files)
  }

  const uploading = queue.some((item) => item.status === 'uploading')

  return (
    <div className="space-y-3">
      <div
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !uploading && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            inputRef.current?.click()
          }
        }}
        className={`group cursor-pointer rounded-xl border border-dashed p-4 text-center transition-colors ${
          dragging
            ? 'border-indigo-400 bg-indigo-500/10'
            : 'border-slate-700 bg-slate-900/40 hover:border-slate-600 hover:bg-slate-900/70'
        } ${uploading ? 'pointer-events-none opacity-60' : ''}`}
      >
        <UploadIcon className="mx-auto h-6 w-6 text-slate-500 transition-colors group-hover:text-indigo-400" />
        <p className="mt-2 text-sm text-slate-300">
          Drop files here or <span className="text-indigo-400">browse</span>
        </p>
        <p className="mt-1 text-xs text-slate-500">PDF, DOCX, TXT or MD · up to 32 MB</p>

        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          onChange={(event) => {
            handleFiles(event.target.files)
            event.target.value = ''
          }}
        />
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 p-2.5 text-xs text-rose-200">
          <AlertIcon className="mt-px h-4 w-4 shrink-0" />
          <span className="min-w-0 break-words">{error}</span>
        </div>
      )}

      {queue.length > 0 && (
        <ul className="space-y-2">
          {queue.map((item) => (
            <li key={item.id} className="animate-in-up rounded-lg bg-slate-900/60 p-2.5">
              <div className="flex items-center gap-2">
                <FileIcon className="h-4 w-4 shrink-0 text-slate-500" />
                <span className="min-w-0 flex-1 truncate text-xs text-slate-300">{item.name}</span>
                {item.status === 'done' ? (
                  <CheckIcon className="h-4 w-4 shrink-0 text-emerald-400" />
                ) : (
                  <span className="shrink-0 text-[11px] tabular-nums text-slate-500">
                    {item.progress}%
                  </span>
                )}
              </div>
              {item.status !== 'done' && (
                <div className="mt-2 h-1 overflow-hidden rounded-full bg-slate-800">
                  <div
                    className="h-full rounded-full bg-indigo-500 transition-all duration-200"
                    style={{ width: `${item.progress}%` }}
                  />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
