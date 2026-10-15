export type Observation = {
  id: string
  index: number
  prompt: string
  response: string | null
  inputTokens: number | null
  outputTokens: number | null
  latencyMs: number | null
  status: string
  incompleteReason: string | null
  error: boolean
}

export type Run = {
  id: string
  executedAt: string
  provider: string
  model: string
  resolvedModel: string
  task: string
  datasetVersion: string
  maxOutputTokens: number
  items: Observation[]
}

export type Pricing = {
  currency: 'USD'
  inputPerMillion: number
  outputPerMillion: number
  verifiedOn: string
  sourceUrl: string
  note: string
}

export type Benchmark = {
  schemaVersion: number
  source: string
  pricing: Pricing
  runs: Run[]
}

const isNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0

export function validateBenchmark(value: unknown): Benchmark {
  if (!value || typeof value !== 'object') throw new Error('Benchmark data is unavailable')
  const data = value as Benchmark
  if (data.schemaVersion !== 1 || !Array.isArray(data.runs) || !data.runs.length) {
    throw new Error('Unsupported benchmark snapshot')
  }
  if (!data.pricing || data.pricing.currency !== 'USD' || !isNumber(data.pricing.inputPerMillion) || !isNumber(data.pricing.outputPerMillion)) {
    throw new Error('Invalid pricing metadata')
  }
  const runIds = new Set<string>()
  for (const run of data.runs) {
    if (!run.id || runIds.has(run.id) || !run.executedAt || !run.provider || !run.model || !run.resolvedModel ||
      !run.task || !run.datasetVersion || !isNumber(run.maxOutputTokens) || !Array.isArray(run.items)) {
      throw new Error('Invalid run metadata')
    }
    runIds.add(run.id)
    const itemIds = new Set<string>()
    for (const item of run.items) {
      if (!item.id || itemIds.has(item.id) || !isNumber(item.index) || typeof item.prompt !== 'string' ||
        (item.response !== null && typeof item.response !== 'string') ||
        typeof item.status !== 'string' || typeof item.error !== 'boolean' ||
        (item.incompleteReason !== null && typeof item.incompleteReason !== 'string') ||
        (item.inputTokens !== null && !isNumber(item.inputTokens)) ||
        (item.outputTokens !== null && !isNumber(item.outputTokens)) ||
        (item.latencyMs !== null && !isNumber(item.latencyMs))) {
        throw new Error('Invalid observation')
      }
      itemIds.add(item.id)
    }
  }
  return data
}

export function estimateCost(inputTokens: number, outputTokens: number, pricing: Pricing): number {
  if (![inputTokens, outputTokens].every(isNumber)) throw new Error('Token counts must be nonnegative')
  return (inputTokens * pricing.inputPerMillion + outputTokens * pricing.outputPerMillion) / 1_000_000
}

export function monthlyCost(requests: number, inputTokens: number, outputTokens: number, pricing: Pricing) {
  if (![requests, inputTokens, outputTokens].every(isNumber)) throw new Error('Requests and tokens must be nonnegative')
  const input = requests * inputTokens * pricing.inputPerMillion / 1_000_000
  const output = requests * outputTokens * pricing.outputPerMillion / 1_000_000
  return { input, output, total: input + output }
}

export function median(values: number[]): number | null {
  if (!values.length) return null
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

export function summarize(run: Run, pricing: Pricing) {
  const successes = run.items.filter(item => !item.error && item.status === 'completed')
  const timed = successes.map(item => item.latencyMs).filter(isNumber)
  const costed = run.items.filter(item => isNumber(item.inputTokens) && isNumber(item.outputTokens))
  const totalCost = costed.reduce((sum, item) => sum + estimateCost(item.inputTokens!, item.outputTokens!, pricing), 0)
  return {
    sample: run.items.length,
    success: successes.length,
    incomplete: run.items.filter(item => item.status === 'incomplete').length,
    errors: run.items.filter(item => item.error).length,
    latencySample: timed.length,
    medianLatency: median(timed),
    costSample: costed.length,
    meanCost: costed.length ? totalCost / costed.length : null,
    inputTokens: costed.reduce((sum, item) => sum + item.inputTokens!, 0),
    outputTokens: costed.reduce((sum, item) => sum + item.outputTokens!, 0),
  }
}

export function compatibleRuns(runs: Run[]): boolean {
  if (runs.length < 2 || runs.length > 4) return false
  if (new Set(runs.map(run => run.id)).size !== runs.length) return false
  const reference = runs[0]
  return runs.every(run => run.provider === reference.provider && run.resolvedModel === reference.resolvedModel &&
    run.task === reference.task && run.datasetVersion === reference.datasetVersion &&
    run.items.length === reference.items.length &&
    run.items.every((item, index) => item.index === reference.items[index].index && item.prompt === reference.items[index].prompt))
}

export type Filters = { provider: string; model: string; task: string; cap: string }

export function filterRuns(runs: Run[], filters: Filters): Run[] {
  return runs.filter(run =>
    (!filters.provider || run.provider === filters.provider) &&
    (!filters.model || run.model === filters.model) &&
    (!filters.task || run.task === filters.task) &&
    (!filters.cap || String(run.maxOutputTokens) === filters.cap))
}

export function sortRuns(runs: Run[], sort: string, pricing: Pricing): Run[] {
  return [...runs].sort((a, b) => {
    const sa = summarize(a, pricing); const sb = summarize(b, pricing)
    if (sort === 'cost') return (sa.meanCost ?? Infinity) - (sb.meanCost ?? Infinity)
    if (sort === 'latency') return (sa.medianLatency ?? Infinity) - (sb.medianLatency ?? Infinity)
    if (sort === 'date') return b.executedAt.localeCompare(a.executedAt)
    return a.maxOutputTokens - b.maxOutputTokens
  })
}

export function formatMicroUSD(value: number | null) {
  return value === null ? 'Unavailable' : `${(value * 1_000_000).toFixed(1)} µ$`
}

export function formatMs(value: number | null) {
  return value === null ? 'Unavailable' : `${Math.round(value).toLocaleString()} ms`
}
