import { useMemo } from 'react'

/**
 * Tiny markdown renderer for LLM output: headings, bullet/numbered lists,
 * paragraphs, plus inline **bold**, `code` and [n] citation chips.
 * Builds React elements directly, so no HTML injection surface.
 */

const INLINE = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\[\d+\])/g
const BULLET = /^[-*•]\s+/
const NUMBERED = /^(\d+)[.)]\s+/

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
          className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[0.85em] text-cyan-300"
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
        !BULLET.test(lines[index].trim()) &&
        !NUMBERED.test(lines[index].trim()) &&
        !/^#{1,6}\s/.test(lines[index].trim())
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
                  <span className="mt-[0.45em] h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-400" />
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
