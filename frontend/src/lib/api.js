const BASE = import.meta.env.VITE_API_URL ?? ''

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, options)
  const text = await response.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = { error: text }
  }
  if (!response.ok) {
    throw new Error(data?.error || `Request failed (${response.status})`)
  }
  return data
}

export function getHealth() {
  return request('/api/health')
}

export function listModels() {
  return request('/api/models')
}

export function listDocuments() {
  return request('/api/documents')
}

export function deleteDocument(id) {
  return request(`/api/documents/${id}`, { method: 'DELETE' })
}

export function uploadDocument(file, onProgress) {
  // XHR rather than fetch: upload progress events are still fetch-less in browsers.
  return new Promise((resolve, reject) => {
    const form = new FormData()
    form.append('file', file)

    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${BASE}/api/documents`)

    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    })

    xhr.addEventListener('load', () => {
      let data = null
      try {
        data = JSON.parse(xhr.responseText)
      } catch {
        data = null
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data)
      } else {
        reject(new Error(data?.error || `Upload failed (${xhr.status})`))
      }
    })

    xhr.addEventListener('error', () => reject(new Error('Network error during upload')))
    xhr.addEventListener('abort', () => reject(new Error('Upload cancelled')))

    xhr.send(form)
  })
}

/**
 * Streams a chat answer via SSE.
 * `handlers` receives { onSources, onDelta, onError, onDone }.
 * Returns an abort function.
 */
export function streamChat({ question, documentIds, history, model, mode = 'code', handlers }) {
  const controller = new AbortController()
  let finished = false
  const finish = () => {
    if (finished) return
    finished = true
    handlers.onDone?.()
  }

  ;(async () => {
    try {
      const response = await fetch(`${BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          document_ids: documentIds,
          history,
          model,
          mode,
        }),
        signal: controller.signal,
      })

      if (!response.ok) {
        const text = await response.text()
        let message = `Request failed (${response.status})`
        try {
          message = JSON.parse(text)?.error ?? message
        } catch {
          /* keep the default */
        }
        handlers.onError?.(new Error(message))
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // SSE frames are separated by a blank line.
        const frames = buffer.split('\n\n')
        buffer = frames.pop() ?? ''

        for (const frame of frames) {
          let event = 'message'
          const dataLines = []
          for (const line of frame.split('\n')) {
            if (line.startsWith('event:')) event = line.slice(6).trim()
            // Strip only the single optional space after the colon. Trimming here
            // would delete the leading spaces that separate streamed tokens.
            else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''))
          }
          if (!dataLines.length) continue

          const raw = dataLines.join('\n')
          if (event === 'delta') {
            handlers.onDelta?.(raw)
          } else if (event === 'sources') {
            try {
              handlers.onSources?.(JSON.parse(raw))
            } catch {
              /* ignore malformed frame */
            }
          } else if (event === 'error') {
            handlers.onError?.(new Error(raw))
          } else if (event === 'done') {
            finish()
          }
        }
      }

      finish()
    } catch (error) {
      if (error.name === 'AbortError') return
      handlers.onError?.(error)
    }
  })()

  return () => controller.abort()
}
