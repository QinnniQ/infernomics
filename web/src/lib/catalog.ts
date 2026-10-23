export type Provider = 'OpenAI' | 'Anthropic' | 'Google' | 'xAI' | 'Ollama'
export type CatalogPrice = { input: number; output: number; cachedInput: number | null; thresholdTokens: number | null; longInput: number | null; longOutput: number | null; longCachedInput: number | null }
export type CatalogModel = {
  id: string; name: string; provider: Provider; kind: 'hosted' | 'local'
  contextTokens: number | null; maxOutputTokens: number | null
  inputModalities: string[]; outputModalities: string[]; pricing: CatalogPrice | null
  freeTierEligible: boolean; execution: 'disabled' | 'local-opt-in-only' | 'local-manual-only'
  measurement: 'none' | 'historical-archive-only' | 'local-v1' | 'local-v2'
  note: string; artifactDigest?: string
  sources: { url: string; claim: string; verifiedOn: string }[]
}
export type ModelCatalog = { schemaVersion: 2; catalogVersion: string; verifiedOn: string; currency: 'USD'; priceUnit: string; models: CatalogModel[] }

const hosts: Record<Provider, string> = {
  OpenAI: 'developers.openai.com', Anthropic: 'platform.claude.com',
  Google: 'ai.google.dev', xAI: 'docs.x.ai', Ollama: 'ollama.com',
}
const date = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value))
const nonnegative = (value: unknown) => typeof value === 'number' && Number.isFinite(value) && value >= 0

export function validateCatalog(value: unknown): ModelCatalog {
  if (!value || typeof value !== 'object') throw new Error('Catalogue unavailable')
  const data = value as ModelCatalog
  if (data.schemaVersion !== 2 || !date(data.catalogVersion) || !date(data.verifiedOn) ||
    data.currency !== 'USD' || data.priceUnit !== 'per 1 million standard text tokens' ||
    !Array.isArray(data.models) || !data.models.length) throw new Error('Invalid catalogue header')
  const ids = new Set<string>()
  for (const model of data.models) {
    if (!model.id || ids.has(model.id) || !model.name || !hosts[model.provider] ||
      !['hosted', 'local'].includes(model.kind) || !model.note ||
      !Array.isArray(model.inputModalities) || !model.inputModalities.length ||
      !Array.isArray(model.outputModalities) || !model.outputModalities.length ||
      !Array.isArray(model.sources) || !model.sources.length) throw new Error(`Invalid model: ${model.id}`)
    ids.add(model.id)
    for (const count of [model.contextTokens, model.maxOutputTokens]) {
      if (count !== null && (!Number.isInteger(count) || count <= 0)) throw new Error(`Invalid token limit: ${model.id}`)
    }
    if (model.kind === 'local') {
      if (model.provider !== 'Ollama' || model.pricing !== null || !/^[a-f0-9]{64}$/.test(model.artifactDigest ?? '') || model.execution !== 'local-manual-only') throw new Error(`Invalid local model: ${model.id}`)
    } else {
      if (model.provider === 'Ollama' || !model.pricing || !nonnegative(model.pricing.input) || !nonnegative(model.pricing.output)) throw new Error(`Invalid hosted model: ${model.id}`)
      const p = model.pricing
      if (p.cachedInput !== null && !nonnegative(p.cachedInput)) throw new Error('Invalid cached rate')
      if (p.thresholdTokens !== null && (!Number.isInteger(p.thresholdTokens) || p.thresholdTokens <= 0 || !nonnegative(p.longInput) || !nonnegative(p.longOutput) || !nonnegative(p.longCachedInput))) throw new Error('Invalid long-context rates')
      if (p.thresholdTokens === null && (p.longInput !== null || p.longOutput !== null || p.longCachedInput !== null)) throw new Error('Unexpected long-context rates')
      if (model.provider !== 'Google' && model.freeTierEligible) throw new Error('Unsupported free-tier claim')
      if (model.execution === 'local-opt-in-only' && (!model.freeTierEligible || model.provider !== 'Google')) throw new Error('Invalid execution policy')
    }
    for (const source of model.sources) {
      let url: URL
      try { url = new URL(source.url) } catch { throw new Error('Invalid source URL') }
      if (url.protocol !== 'https:' || url.hostname !== hosts[model.provider] || !source.claim || !date(source.verifiedOn)) throw new Error(`Unverified source: ${model.id}`)
    }
  }
  return data
}

export type Workload = { requests: number; inputTokens: number; outputTokens: number; retryPercent: number; cachedInputPercent: number }
export function estimateModelCost(model: CatalogModel, workload: Workload) {
  if (model.kind !== 'hosted' || !model.pricing) return null
  const v = Object.values(workload)
  if (v.some(x => !Number.isFinite(x) || x < 0) || workload.retryPercent > 200 || workload.cachedInputPercent > 100) throw new Error('Invalid workload')
  if ((model.contextTokens !== null && workload.inputTokens + workload.outputTokens > model.contextTokens) ||
      (model.maxOutputTokens !== null && workload.outputTokens > model.maxOutputTokens)) return null
  const { pricing } = model
  const attempts = workload.requests * (1 + workload.retryPercent / 100)
  const longContext = pricing.thresholdTokens !== null && workload.inputTokens >= pricing.thresholdTokens
  const inputRate = longContext ? pricing.longInput! : pricing.input
  const outputRate = longContext ? pricing.longOutput! : pricing.output
  // Cache discounts are used only where an official cached-input rate is recorded.
  const cachedShare = pricing.cachedInput === null ? 0 : workload.cachedInputPercent / 100
  const inputCost = attempts * workload.inputTokens * ((1 - cachedShare) * inputRate + cachedShare * (longContext ? pricing.longCachedInput! : pricing.cachedInput!)) / 1_000_000
  const outputCost = attempts * workload.outputTokens * outputRate / 1_000_000
  return { attempts, inputCost, outputCost, total: inputCost + outputCost, longContext, cacheApplied: cachedShare > 0 }
}
