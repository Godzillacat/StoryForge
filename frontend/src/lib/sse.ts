export interface SseEvent {
  event: string
  data: string
}

function parseBlock(raw: string): SseEvent | null {
  let event = 'message'
  const data: string[] = []
  for (const line of raw.split('\n')) {
    if (!line || line.startsWith(':')) continue
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') event = value
    else if (field === 'data') data.push(value)
  }
  return data.length === 0 ? null : { event, data: data.join('\n') }
}

export function createSseParser() {
  let buffer = ''
  return {
    push(chunk: string): SseEvent[] {
      buffer = (buffer + chunk).replace(/\r\n/g, '\n')
      const events: SseEvent[] = []
      for (;;) {
        const boundary = buffer.indexOf('\n\n')
        if (boundary < 0) break
        const block = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const parsed = parseBlock(block)
        if (parsed) events.push(parsed)
      }
      return events
    },
  }
}
