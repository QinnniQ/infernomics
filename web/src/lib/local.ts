export type Model = { id: string; digest: string; family: string; parameterSize: string; quantization: string; downloadBytes: number }
export type LocalObservation = {
  id: string; experimentId: string; model: string; itemId: string; category: string; prompt: string
  repetition: number; response: string | null; status: 'completed' | 'incomplete' | 'unknown' | 'error'
  doneReason: string | null; wallMs: number | null; ollamaTotalMs: number | null; loadMs: number | null
  promptMs: number | null; generationMs: number | null; inputTokens: number | null
  cachedInputTokens: number | null; outputTokens: number | null; tokensPerSecond: number | null
  evaluation: { kind: string; passed: boolean | null; reason: string; rubric?: string[] }; error: string | null
}
export type LocalExperiment = {
  id: string; executedAt: string; datasetVersion: string; datasetSha256: string; split: 'test'
  runtime: 'Ollama'; runtimeVersion: string; hardware: { os: string; architecture: string; cpu: string; gpu: string; memoryBytes: number | null }
  generation: { temperature: number; seed: number; maxOutputTokens: number; contextTokens: number; thinking: boolean; warmup: string; orderSeed: number; timeoutSeconds: number; retries: number }
  repetitions: number; models: Model[]; codeRevision: string; protocol: string; limitations: string
}
export type LocalSnapshot = { schemaVersion: 2; evidenceClass: 'local-ollama'; experiment: LocalExperiment | null; observations: LocalObservation[] }

const nonnegative = (value: unknown) => value === null || (typeof value === 'number' && Number.isFinite(value) && value >= 0)

export function validateLocal(value: unknown): LocalSnapshot {
  if (!value || typeof value !== 'object') throw new Error('Local data missing')
  const data = value as LocalSnapshot
  if (data.schemaVersion !== 2 || data.evidenceClass !== 'local-ollama' || !Array.isArray(data.observations)) throw new Error('Unsupported local snapshot')
  if (data.experiment === null) {
    if (data.observations.length) throw new Error('Observations have no experiment')
    return data
  }
  const exp = data.experiment
  if (!exp || exp.runtime !== 'Ollama' || exp.split !== 'test' || !exp.id || typeof exp.datasetSha256 !== 'string' || exp.datasetSha256.length !== 64 || !Array.isArray(exp.models) || exp.models.length < 2 || !Number.isInteger(exp.repetitions) || exp.repetitions < 1) throw new Error('Invalid experiment')
  const modelIds = new Set(exp.models.map(model => model.id))
  if (modelIds.size !== exp.models.length || exp.models.some(model => !model.digest || !model.family || !model.parameterSize || !model.quantization || !Number.isInteger(model.downloadBytes) || model.downloadBytes < 0)) throw new Error('Invalid model metadata')
  const ids = new Set<string>()
  const prompts = new Map<string, string>()
  const coverage = new Set<string>()
  for (const row of data.observations) {
    if (!row.id || ids.has(row.id) || row.experimentId !== exp.id || !modelIds.has(row.model) || !row.itemId || !row.prompt || !Number.isInteger(row.repetition) || row.repetition < 0 || row.repetition >= exp.repetitions || (row.response !== null && typeof row.response !== 'string')) throw new Error('Invalid local observation identity')
    ids.add(row.id)
    if (prompts.has(row.itemId) && prompts.get(row.itemId) !== row.prompt) throw new Error('Prompt mismatch')
    prompts.set(row.itemId, row.prompt)
    if (!['completed', 'incomplete', 'unknown', 'error'].includes(row.status) || (row.status === 'error' && !row.error) || !row.evaluation || ![true, false, null].includes(row.evaluation.passed)) throw new Error('Invalid local outcome')
    for (const key of ['wallMs', 'ollamaTotalMs', 'loadMs', 'promptMs', 'generationMs', 'inputTokens', 'cachedInputTokens', 'outputTokens', 'tokensPerSecond'] as const) if (!nonnegative(row[key])) throw new Error(`Invalid ${key}`)
    for (const key of ['inputTokens', 'cachedInputTokens', 'outputTokens'] as const) if (row[key] !== null && !Number.isInteger(row[key])) throw new Error(`Invalid ${key}`)
    const slot = `${row.model}:${row.itemId}:${row.repetition}`
    if (coverage.has(slot)) throw new Error('Duplicate model-item repetition')
    coverage.add(slot)
  }
  if (!prompts.size || coverage.size !== prompts.size * modelIds.size * exp.repetitions) throw new Error('Incomplete comparison coverage')
  return data
}

export function localMedian(values: number[]): number | null {
  if (!values.length) return null
  const sorted = [...values].sort((a, b) => a - b)
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2
}

export function localStats(values: number[]) {
  if (!values.length) return { mean: null, min: null, max: null, sampleStdDev: null }
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length
  const variance = values.length > 1 ? values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (values.length - 1) : null
  return { mean, min: Math.min(...values), max: Math.max(...values), sampleStdDev: variance === null ? null : Math.sqrt(variance) }
}

export function summarizeLocal(rows: LocalObservation[]) {
  const completed = rows.filter(row => row.status === 'completed')
  const incomplete = rows.filter(row => row.status === 'incomplete').length
  const errors = rows.filter(row => row.status === 'error').length
  const assessed = rows.filter(row => row.evaluation.passed !== null)
  const latency = completed.flatMap(row => row.wallMs === null ? [] : [row.wallMs])
  const speed = completed.flatMap(row => row.tokensPerSecond === null ? [] : [row.tokensPerSecond])
  return { attempts: rows.length, completed: completed.length, incomplete, errors,
    assessed: assessed.length, passed: assessed.filter(row => row.evaluation.passed).length,
    latencyN: latency.length, medianLatency: localMedian(latency), latencyStats: localStats(latency),
    speedN: speed.length, medianSpeed: localMedian(speed), speedStats: localStats(speed) }
}
