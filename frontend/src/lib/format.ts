export function costLabel(cost: number): string {
  if (!cost) return '$0'
  if (cost < 0.01) return `$${cost.toFixed(4)}`
  return `$${cost.toFixed(2)}`
}

export function durationLabel(ms: number): string {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
}

export function tokensLabel(prompt: number, completion: number): string {
  return `${prompt} + ${completion} tokens`
}

export function maskPreview(text: string | null | undefined, limit = 4): string {
  if (!text) return ''
  return text.length <= limit ? text : `${text.slice(0, limit)}…`
}
