import type { CatalogModel, ModelCatalog, Provider, Workload } from './catalog'
import { estimateModelCost } from './catalog'
import type { Benchmark, Observation, Run } from './benchmark'
import { median } from './benchmark'
import type { LocalSnapshot } from './local'

export type Suite = 'v2' | 'v1'
export type EvidenceFilter = 'all' | 'local' | 'archive' | 'spec'
export type ModelFilters = { provider: Provider | 'All'; modality: string; evidence: EvidenceFilter }
export type ArchiveFilters = { cap: string; status: string; prompt: string; run: string }
export type WorkloadPreset = 'service' | 'rag' | 'documents' | 'extraction' | 'custom'
export type LabWorkload = Workload & { incompleteRetryPercent: number }

export const presets: Record<Exclude<WorkloadPreset, 'custom'>, { label: string; note: string; workload: LabWorkload }> = {
  service: { label: 'Customer service', note: 'Illustrative: short customer question and concise answer.', workload: { requests: 50000, inputTokens: 650, outputTokens: 220, retryPercent: 2, incompleteRetryPercent: 0, cachedInputPercent: 0 } },
  rag: { label: 'RAG search', note: 'Illustrative: retrieved passages included in every prompt.', workload: { requests: 20000, inputTokens: 3500, outputTokens: 450, retryPercent: 3, incompleteRetryPercent: 0, cachedInputPercent: 0 } },
  documents: { label: 'Document processing', note: 'Illustrative text tokens only; file, image and tool charges are excluded.', workload: { requests: 5000, inputTokens: 12000, outputTokens: 900, retryPercent: 2, incompleteRetryPercent: 0, cachedInputPercent: 0 } },
  extraction: { label: 'Structured extraction', note: 'Illustrative text extraction, including repeated schema instructions.', workload: { requests: 100000, inputTokens: 900, outputTokens: 120, retryPercent: 1, incompleteRetryPercent: 0, cachedInputPercent: 0 } },
}

export const defaultWorkload: LabWorkload = { ...presets.service.workload }

export function suiteSnapshot(suite: Suite, v1: LocalSnapshot, v2: LocalSnapshot): LocalSnapshot {
  return suite === 'v2' ? v2 : v1
}

export function selectedRepetition(requested: number, snapshot: LocalSnapshot): number {
  const count = snapshot.experiment?.repetitions ?? 1
  return Math.min(Math.max(0, Math.trunc(requested) || 0), count - 1)
}

export function modelEvidence(model: CatalogModel): EvidenceFilter {
  if (model.kind === 'local') return 'local'
  return model.measurement === 'historical-archive-only' ? 'archive' : 'spec'
}

export function filterModels(catalog: ModelCatalog, filters: ModelFilters): CatalogModel[] {
  return catalog.models.filter(model =>
    (filters.provider === 'All' || model.provider === filters.provider) &&
    (!filters.modality || model.inputModalities.some(value => value.toLowerCase() === filters.modality.toLowerCase()) || model.outputModalities.some(value => value.toLowerCase() === filters.modality.toLowerCase())) &&
    (filters.evidence === 'all' || modelEvidence(model) === filters.evidence))
}

export function modelFilterOptions(catalog: ModelCatalog) {
  return {
    providers: [...new Set(catalog.models.map(model => model.provider))],
    modalities: [...new Set(catalog.models.flatMap(model => [...model.inputModalities, ...model.outputModalities]))].sort(),
    evidence: [...new Set(catalog.models.map(modelEvidence))],
  }
}

export function toggleModelSelection(current: string[], id: string, maximum = 5): string[] {
  return current.includes(id) ? current.filter(value => value !== id) : current.length < maximum ? [...current, id] : current
}

export function archiveOptions(benchmark: Benchmark) {
  return {
    caps: [...new Set(benchmark.runs.map(run => run.maxOutputTokens))].sort((a, b) => a - b),
    statuses: [...new Set(benchmark.runs.flatMap(run => run.items.map(item => item.status)))],
    prompts: [...new Map(benchmark.runs.flatMap(run => run.items.map(item => [item.index, item.prompt] as const))).entries()].sort((a, b) => a[0] - b[0]),
    runs: benchmark.runs.map(run => ({ id: run.id, cap: run.maxOutputTokens, date: run.executedAt })),
  }
}

export type ArchiveRow = { run: Run; item: Observation }
export function filterArchive(benchmark: Benchmark, filters: ArchiveFilters): ArchiveRow[] {
  return benchmark.runs.flatMap(run =>
    (filters.cap && String(run.maxOutputTokens) !== filters.cap) || (filters.run && run.id !== filters.run)
      ? [] : run.items.filter(item =>
        (!filters.status || item.status === filters.status) &&
        (!filters.prompt || String(item.index) === filters.prompt)).map(item => ({ run, item })))
}

export function quantiles(values: number[]) {
  const sorted = [...values].sort((a, b) => a - b)
  const at = (p: number) => {
    if (!sorted.length) return null
    const index = (sorted.length - 1) * p
    const low = Math.floor(index)
    return sorted[low] + (sorted[Math.ceil(index)] - sorted[low]) * (index - low)
  }
  return { n: sorted.length, min: sorted[0] ?? null, q1: at(.25), median: median(sorted), q3: at(.75), max: sorted.at(-1) ?? null }
}

export function archiveByCap(benchmark: Benchmark) {
  return benchmark.runs.map(run => {
    const completed = run.items.filter(item => item.status === 'completed' && !item.error)
    return { run, attempts: run.items.length, completed: completed.length,
      incomplete: run.items.filter(item => item.status === 'incomplete').length,
      latency: quantiles(completed.flatMap(item => item.latencyMs === null ? [] : [item.latencyMs])) }
  })
}

export function estimateLab(model: CatalogModel, workload: LabWorkload) {
  if (!Number.isFinite(workload.incompleteRetryPercent) || workload.incompleteRetryPercent < 0 || workload.incompleteRetryPercent > 100 || workload.retryPercent > 100) throw new Error('Invalid retry percentage')
  return estimateModelCost(model, { ...workload, retryPercent: workload.retryPercent + workload.incompleteRetryPercent })
}

export function sensitivity(model: CatalogModel, workload: LabWorkload) {
  return [0.5, 1, 2].map(multiplier => ({ multiplier, estimate: estimateLab(model, { ...workload, requests: workload.requests * multiplier }) }))
}

export function scenarioExport(catalog: ModelCatalog, suite: Suite, selected: string[], workload: LabWorkload, local: { watts: number | null; tariff: number | null; hardware: number | null; months: number | null; modelId: string }, generatedAt: string) {
  return {
    kind: 'infernomics-hypothetical-scenario', generatedAt, catalogueVersion: catalog.catalogVersion,
    priceVerifiedOn: catalog.verifiedOn, currency: catalog.currency, experimentSuite: suite,
    assumptions: { ...workload, local },
    estimates: catalog.models.filter(model => selected.includes(model.id)).map(model => ({ modelId: model.id, provider: model.provider, sourceUrls: model.sources.map(source => source.url), estimate: estimateLab(model, workload) })),
    limitations: ['List-price calculation, not a bill or forecast', 'Same entered token counts assumed across different provider tokenizers', 'Cache hits require actual eligibility and writes are excluded', 'No model quality or hosted latency inferred'],
  }
}
