import Markdown from './Markdown'
import SourceList from './SourceList'
import { AlertIcon, SparkIcon } from './Icons'

function UserMessage({ text }) {
  return (
    <div className="animate-in-up flex justify-end">
      <div className="max-w-[85%] rounded-2xl rounded-br-md bg-indigo-600 px-4 py-2.5 text-sm leading-relaxed text-white shadow-lg shadow-indigo-950/40">
        {text}
      </div>
    </div>
  )
}

function AssistantMessage({ text, sources, streaming, error }) {
  const empty = !text.trim()

  return (
    <div className="animate-in-up flex gap-3">
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-lg shadow-indigo-950/50">
        <SparkIcon className="h-4 w-4" />
      </div>

      <div className="min-w-0 flex-1">
        {empty && streaming && (
          <div className="flex items-center gap-1 py-1">
            {[0, 150, 300].map((delay) => (
              <span
                key={delay}
                className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-600"
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
            className={`text-[0.925rem] leading-relaxed text-slate-200 ${
              streaming ? 'cursor-blink' : ''
            }`}
          >
            <Markdown content={text} />
          </div>
        )}

        {!streaming && !error && <SourceList sources={sources} />}
      </div>
    </div>
  )
}

export default function Message({ message }) {
  if (message.role === 'user') return <UserMessage text={message.content} />

  return (
    <AssistantMessage
      text={message.content}
      sources={message.sources}
      streaming={message.streaming}
      error={message.error}
    />
  )
}
