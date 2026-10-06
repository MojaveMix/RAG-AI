import { useMemo, useState } from 'react'
import { CheckIcon, CodeIcon, CopyIcon } from './Icons'

/**
 * Enhanced markdown renderer for LLM output:
 * - Multi-line fenced code blocks (```language ... ```) with syntax layout & Copy button
 * - Tables (| Header | ...)
 * - Headings (#, ##, ###, ####)
 * - Bullet & numbered lists
 * - Inline bold (**bold**), inline code (`code`), citations ([n]), and links ([text](url))
 */

const INLINE = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\[\d+\]|\[[^\]]+\]\([^)]+\))/g
const BULLET = /^[-*•]\s+/
const NUMBERED = /^(\d+)[.)]\s+/

function CodeBlock({ language, code }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* ignore copy errors */
    }
  }

  const langLabel = (language || 'code').toUpperCase()

  return (
    <div className="group my-3 overflow-hidden rounded-xl border border-slate-800 bg-slate-950/90 shadow-2xl">
      <div className="flex items-center justify-between border-b border-slate-800/80 bg-slate-900/60 px-3.5 py-1.5 text-xs text-slate-400">
        <div className="flex items-center gap-1.5 font-mono text-[11px] font-medium text-slate-300">
          <CodeIcon className="h-3.5 w-3.5 text-cyan-400" />
          <span>{langLabel}</span>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-200"
          title="Copy code to clipboard"
        >
          {copied ? (
            <>
              <CheckIcon className="h-3 w-3 text-emerald-400" />
              <span className="text-emerald-400">Copied!</span>
            </>
          ) : (
            <>
              <CopyIcon className="h-3 w-3" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="overflow-x-auto p-4 font-mono text-xs leading-relaxed text-slate-100 selection:bg-indigo-500/30 sm:text-sm">
        <code>{code}</code>
      </pre>
    </div>
  )
}

function renderInline(text, keyPrefix) {
  return text.split(INLINE).map((token, index) => {
    const key = `${keyPrefix}-${index}`
    if (!token) return null

    if (token.startsWith('**') && token.endsWith('**')) {
      return (
        <strong key={key} className="font-semibold text-slate-50">
          {token.slice(2, -2)}
        </strong>
      )
    }
    if (token.startsWith('`') && token.endsWith('`')) {
      return (
        <code
          key={key}
          className="rounded bg-slate-800/90 px-1.5 py-0.5 font-mono text-[0.85em] text-cyan-300"
        >
          {token.slice(1, -1)}
        </code>
      )
    }
    const citation = token.match(/^\[(\d+)\]$/)
    if (citation) {
      return (
        <sup
          key={key}
          data-citation={citation[1]}
          className="mx-0.5 inline-flex h-[1.15em] min-w-[1.15em] items-center justify-center rounded bg-indigo-500/20 px-1 align-top font-sans text-[0.68em] font-semibold text-indigo-300"
        >
          {citation[1]}
        </sup>
      )
    }
    const linkMatch = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
    if (linkMatch) {
      return (
        <a
          key={key}
          href={linkMatch[2]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-cyan-400 underline underline-offset-2 hover:text-cyan-300"
        >
          {linkMatch[1]}
        </a>
      )
    }
    return <span key={key}>{token}</span>
  })
}

export default function Markdown({ content }) {
  const blocks = useMemo(() => {
    if (!content) return []

    const lines = content.split('\n')
    const out = []
    let index = 0

    while (index < lines.length) {
      const line = lines[index]

      if (!line.trim()) {
        index += 1
        continue
      }

      // Fenced code block (```lang ... ```)
      const codeMatch = line.match(/^```(\w*)/)
      if (codeMatch) {
        const language = codeMatch[1].trim()
        index += 1
        const codeLines = []
        while (index < lines.length && !lines[index].startsWith('```')) {
          codeLines.push(lines[index])
          index += 1
        }
        if (index < lines.length && lines[index].startsWith('```')) {
          index += 1
        }
        out.push({
          type: 'code',
          language,
          code: codeLines.join('\n'),
        })
        continue
      }

      // Markdown Table
      if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
        const tableLines = []
        while (index < lines.length && lines[index].trim().startsWith('|') && lines[index].trim().endsWith('|')) {
          tableLines.push(lines[index].trim())
          index += 1
        }
        if (tableLines.length >= 2) {
          const parseRow = (row) =>
            row
              .slice(1, -1)
              .split('|')
              .map((c) => c.trim())
          const header = parseRow(tableLines[0])
          const rows = tableLines.slice(2).map(parseRow)
          out.push({ type: 'table', header, rows })
          continue
        }
      }

      // Heading
      const heading = line.match(/^(#{1,6})\s+(.*)$/)
      if (heading) {
        const level = Math.min(heading[1].length, 4)
        out.push({
          type: 'heading',
          level,
          text: heading[2],
        })
        index += 1
        continue
      }

      // Horizontal rule
      if (/^([-*_])\1{2,}$/.test(line.trim())) {
        out.push({ type: 'rule' })
        index += 1
        continue
      }

      // Consecutive bullets
      if (BULLET.test(line.trim())) {
        const items = []
        while (index < lines.length && BULLET.test(lines[index].trim())) {
          items.push(lines[index].trim().replace(BULLET, ''))
          index += 1
        }
        out.push({ type: 'ul', items })
        continue
      }

      // Consecutive numbered items
      if (NUMBERED.test(line.trim())) {
        const items = []
        while (index < lines.length && NUMBERED.test(lines[index].trim())) {
          items.push(lines[index].trim().replace(NUMBERED, ''))
          index += 1
        }
        out.push({ type: 'ol', items })
        continue
      }

      // Paragraph: gather until a blank line or the start of another block
      const paragraph = []
      while (
        index < lines.length &&
        lines[index].trim() &&
        !lines[index].startsWith('```') &&
        !BULLET.test(lines[index].trim()) &&
        !NUMBERED.test(lines[index].trim()) &&
        !/^#{1,6}\s/.test(lines[index].trim()) &&
        !(lines[index].trim().startsWith('|') && lines[index].trim().endsWith('|'))
      ) {
        paragraph.push(lines[index].trim())
        index += 1
      }
      out.push({ type: 'p', text: paragraph.join(' ') })
    }

    return out
  }, [content])

  if (!blocks.length) return null

  return (
    <div className="space-y-3">
      {blocks.map((block, index) => {
        const key = `b${index}`

        if (block.type === 'code') {
          return <CodeBlock key={key} language={block.language} code={block.code} />
        }

        if (block.type === 'table') {
          return (
            <div key={key} className="my-3 overflow-x-auto rounded-lg border border-slate-800">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="border-b border-slate-800 bg-slate-900/80 font-semibold text-slate-100">
                  <tr>
                    {block.header.map((col, colIdx) => (
                      <th key={colIdx} className="px-3 py-2">
                        {renderInline(col, `${key}-th-${colIdx}`)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 bg-slate-950/40">
                  {block.rows.map((row, rowIdx) => (
                    <tr key={rowIdx} className="hover:bg-slate-900/40">
                      {row.map((cell, cellIdx) => (
                        <td key={cellIdx} className="px-3 py-2">
                          {renderInline(cell, `${key}-td-${rowIdx}-${cellIdx}`)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        }

        if (block.type === 'heading') {
          const sizes = {
            1: 'text-lg',
            2: 'text-base',
            3: 'text-[0.95rem]',
            4: 'text-sm',
          }
          return (
            <p key={key} className={`font-semibold text-slate-50 ${sizes[block.level]}`}>
              {renderInline(block.text, key)}
            </p>
          )
        }

        if (block.type === 'rule') {
          return <hr key={key} className="border-slate-800" />
        }

        if (block.type === 'ul') {
          return (
            <ul key={key} className="space-y-1.5">
              {block.items.map((item, itemIndex) => (
                <li key={`${key}-${itemIndex}`} className="flex gap-2.5">
                  <span className="mt-[0.45em] h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400" />
                  <span className="min-w-0 flex-1">{renderInline(item, `${key}-${itemIndex}`)}</span>
                </li>
              ))}
            </ul>
          )
        }

        if (block.type === 'ol') {
          return (
            <ol key={key} className="space-y-1.5">
              {block.items.map((item, itemIndex) => (
                <li key={`${key}-${itemIndex}`} className="flex gap-2.5">
                  <span className="mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded bg-slate-800 text-xs font-semibold text-slate-300">
                    {itemIndex + 1}
                  </span>
                  <span className="min-w-0 flex-1">{renderInline(item, `${key}-${itemIndex}`)}</span>
                </li>
              ))}
            </ol>
          )
        }

        return <p key={key}>{renderInline(block.text, key)}</p>
      })}
    </div>
  )
}
