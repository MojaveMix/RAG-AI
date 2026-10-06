import { useState } from 'react'
import Markdown from './Markdown'
import SourceList from './SourceList'
import { AlertIcon, CheckIcon, CodeIcon, CopyIcon, SparkIcon } from './Icons'

function UserMessage({ text, mode = 'code' }) {
  return (
    <div className="animate-in-up flex justify-end">
      <div
        dir="auto"
        className={`max-w-[85%] rounded-2xl rounded-br-md px-4 py-2.5 text-sm leading-relaxed text-white shadow-lg ${
          mode === 'code'
            ? 'bg-gradient-to-r from-slate-800 to-indigo-950 border border-slate-700/80 shadow-slate-950/60'
            : 'bg-indigo-600 shadow-indigo-950/40'
        }`}
      >
        {text}
      </div>
    </div>
  )
}

function AssistantMessage({ text, sources, streaming, error, mode = 'code' }) {
  const empty = !text.trim()
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="animate-in-up flex gap-3">
      <div
        className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-white shadow-lg ${
          mode === 'code'
            ? 'bg-gradient-to-br from-cyan-500 to-indigo-600 shadow-cyan-950/50'
            : 'bg-gradient-to-br from-indigo-500 to-violet-600 shadow-indigo-950/50'
        }`}
      >
        {mode === 'code' ? <CodeIcon className="h-3.5 w-3.5" /> : <SparkIcon className="h-4 w-4" />}
      </div>

      <div className="min-w-0 flex-1">
        {empty && streaming && (
          <div className="flex items-center gap-1 py-1">
            {[0, 150, 300].map((delay) => (
              <span
                key={delay}
                className={`h-1.5 w-1.5 animate-bounce rounded-full ${mode === 'code' ? 'bg-cyan-500' : 'bg-slate-600'}`}
                style={{ animationDelay: `${delay}ms` }}
              />
            ))}
          </div>
        )}

        {empty && error && (
          <div className="flex items-start gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">
            <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
            <span className="min-w-0 break-words">{error}</span>
          </div>
        )}

        {!empty && (
          <div
            dir="auto"
            className={`text-[0.925rem] leading-relaxed text-slate-200 ${
              streaming ? 'cursor-blink' : ''
            }`}
          >
            <Markdown content={text} />
          </div>
        )}

        {!streaming && !empty && !error && (
          <div className="mt-2 flex items-center justify-start gap-2">
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-1 rounded-md bg-slate-900/60 px-2 py-0.5 text-[11px] font-medium text-slate-400 border border-slate-800 transition-colors hover:bg-slate-800 hover:text-slate-200"
              title="Copy entire response"
            >
              {copied ? (
                <>
                  <CheckIcon className="h-3 w-3 text-emerald-400" />
                  <span className="text-emerald-400">Response copied</span>
                </>
              ) : (
                <>
                  <CopyIcon className="h-3 w-3" />
                  <span>Copy answer</span>
                </>
              )}
            </button>
          </div>
        )}

        {!streaming && !error && <SourceList sources={sources} />}
      </div>
    </div>
  )
}

export default function Message({ message, mode = 'code' }) {
  if (message.role === 'user') return <UserMessage text={message.content} mode={mode} />

  return (
    <AssistantMessage
      text={message.content}
      sources={message.sources}
      streaming={message.streaming}
      error={message.error}
      mode={mode}
    />
  )
}
