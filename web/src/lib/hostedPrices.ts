export type HostedPrice = {
  id: string
  provider: string
  model: string
  inputPerMillion: number
  outputPerMillion: number
  sourceUrl: string
  note: string
}

export type HostedPriceCatalog = {
  schemaVersion: 1
  evidenceClass: 'published-list-price'
  verifiedOn: string
  currency: 'USD'
  unit: 'per 1 million standard text tokens'
  models: HostedPrice[]
}

const officialHosts: Record<string, string> = {
  OpenAI: 'developers.openai.com',
  Anthropic: 'platform.claude.com',
  Google: 'ai.google.dev',
}

export function validateHostedPrices(value: unknown): HostedPriceCatalog {
  if (!value || typeof value !== 'object') throw new Error('Hosted price catalog is unavailable')
  const data = value as HostedPriceCatalog
  if (data.schemaVersion !== 1 || data.evidenceClass !== 'published-list-price' ||
    data.currency !== 'USD' || data.unit !== 'per 1 million standard text tokens' ||
    !/^\d{4}-\d{2}-\d{2}$/.test(data.verifiedOn) || !Array.isArray(data.models) || !data.models.length) {
    throw new Error('Invalid hosted price catalog')
  }
  const ids = new Set<string>()
  for (const model of data.models) {
    if (!model.id || ids.has(model.id) || !model.model || !model.note ||
      !Number.isFinite(model.inputPerMillion) || model.inputPerMillion < 0 ||
      !Number.isFinite(model.outputPerMillion) || model.outputPerMillion < 0 ||
      !officialHosts[model.provider]) throw new Error('Invalid hosted model price')
    let source: URL
    try { source = new URL(model.sourceUrl) } catch { throw new Error('Invalid hosted model source') }
    if (source.protocol !== 'https:' || source.hostname !== officialHosts[model.provider]) throw new Error('Unverified hosted model source')
    ids.add(model.id)
  }
  return data
}
