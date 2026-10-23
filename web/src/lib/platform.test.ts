import { describe, expect, it } from 'vitest'
import { archive, catalog, localV1, localV2 } from './data'
import { archiveByCap, archiveOptions, defaultWorkload, estimateLab, filterArchive, filterModels, modelFilterOptions, presets, quantiles, scenarioExport, selectedRepetition, sensitivity, suiteSnapshot, toggleModelSelection } from './platform'

describe('unified model catalogue', () => {
  it('derives only real provider, modality and evidence choices', () => {
    const options = modelFilterOptions(catalog)
    expect(options.providers).toEqual(['OpenAI', 'Anthropic', 'Google', 'xAI', 'Ollama'])
    expect(options.modalities).toContain('PDF')
    expect(options.evidence).toEqual(['archive', 'spec', 'local'])
    expect(filterModels(catalog, { provider: 'Anthropic', modality: 'image', evidence: 'spec' }).map(model => model.id)).toEqual(['claude-haiku-4-5-20251001', 'claude-sonnet-5'])
    expect(filterModels(catalog, { provider: 'Ollama', modality: 'image', evidence: 'all' })).toHaveLength(0)
  })
  it('caps selection without duplicating IDs', () => {
    expect(toggleModelSelection(['a', 'b'], 'a')).toEqual(['b'])
    expect(toggleModelSelection(['a', 'b'], 'a', 2)).toEqual(['b'])
    expect(toggleModelSelection(['a', 'b'], 'c', 2)).toEqual(['a', 'b'])
  })
})

describe('benchmark provenance and historical filters', () => {
  it('selects the exact frozen suite without pooling', () => {
    expect(suiteSnapshot('v1', localV1, localV2).experiment?.datasetVersion).toContain('local-v1')
    expect(suiteSnapshot('v2', localV1, localV2).experiment?.datasetVersion).toContain('local-v2')
    expect(suiteSnapshot('v1', localV1, localV2).observations).toHaveLength(24)
    expect(suiteSnapshot('v2', localV1, localV2).observations).toHaveLength(24)
    expect(selectedRepetition(1, localV1)).toBe(1)
    expect(selectedRepetition(1, localV2)).toBe(0)
    expect(localV1.experiment?.datasetSha256).not.toBe(localV2.experiment?.datasetSha256)
  })
  it('builds archive controls only from observations and intersects all filters', () => {
    const options = archiveOptions(archive)
    expect(options.caps).toEqual([50, 100, 200])
    expect(options.statuses.sort()).toEqual(['completed', 'incomplete'])
    expect(options.prompts).toHaveLength(20)
    const run = archive.runs[0]
    const row = run.items[0]
    const found = filterArchive(archive, { cap: String(run.maxOutputTokens), status: row.status, prompt: String(row.index), run: run.id })
    expect(found).toHaveLength(1)
    expect(found[0].item.id).toBe(row.id)
    expect(filterArchive(archive, { cap: '999', status: '', prompt: '', run: '' })).toHaveLength(0)
  })
  it('preserves all 60 attempts and completed-only latency denominators', () => {
    const caps = archiveByCap(archive)
    expect(caps.reduce((sum, row) => sum + row.attempts, 0)).toBe(60)
    expect(caps.reduce((sum, row) => sum + row.incomplete, 0)).toBe(28)
    expect(caps.map(row => row.latency.n)).toEqual(caps.map(row => row.completed))
    expect(quantiles([1, 2, 3, 4])).toEqual({ n: 4, min: 1, q1: 1.75, median: 2.5, q3: 3.25, max: 4 })
  })
})

describe('one Economics Lab workload', () => {
  it('keeps presets explicit and calculations additive for retries', () => {
    expect(presets.rag.workload.inputTokens).toBe(3500)
    const model = catalog.models.find(item => item.id === 'gpt-4o-mini')!
    const estimate = estimateLab(model, { ...defaultWorkload, requests: 1000, inputTokens: 1000, outputTokens: 500, retryPercent: 20, incompleteRetryPercent: 10, cachedInputPercent: 0 })!
    expect(estimate.attempts).toBe(1300)
    expect(estimate.inputCost).toBeCloseTo(.195)
    expect(estimate.outputCost).toBeCloseTo(.39)
  })
  it('applies only documented cache reads and respects context limits', () => {
    const openai = catalog.models.find(item => item.id === 'gpt-4o-mini')!
    const google = catalog.models.find(item => item.id === 'gemini-3.1-flash-lite')!
    const base = { ...defaultWorkload, requests: 1000, inputTokens: 1000, outputTokens: 100, retryPercent: 0, incompleteRetryPercent: 0 }
    expect(estimateLab(openai, { ...base, cachedInputPercent: 50 })!.inputCost).toBeCloseTo(.1125)
    expect(estimateLab(google, { ...base, cachedInputPercent: 50 })!.inputCost).toBeCloseTo(.25)
    expect(estimateLab(openai, { ...base, inputTokens: 128000, outputTokens: 1, cachedInputPercent: 0 })).toBeNull()
    expect(() => estimateLab(openai, { ...base, cachedInputPercent: 101 })).toThrow()
  })
  it('uses xAI long-context rates and exports assumptions with provenance', () => {
    const xai = catalog.models.find(item => item.id === 'grok-4.6')!
    const estimate = estimateLab(xai, { ...defaultWorkload, requests: 1, inputTokens: 200000, outputTokens: 1000, retryPercent: 0, incompleteRetryPercent: 0, cachedInputPercent: 50 })!
    expect(estimate.longContext).toBe(true)
    expect(estimate.inputCost).toBeCloseTo(.5)
    expect(estimate.outputCost).toBeCloseTo(.012)
    expect(sensitivity(xai, { ...defaultWorkload, requests: 100 }).map(row => row.multiplier)).toEqual([.5, 1, 2])
    const payload = scenarioExport(catalog, 'v2', ['grok-4.6'], defaultWorkload, { watts: null, tariff: null, hardware: null, months: null, modelId: 'phi3:latest' }, '2026-10-23T00:00:00Z')
    expect(payload.kind).toBe('infernomics-hypothetical-scenario')
    expect(payload.priceVerifiedOn).toBe(catalog.verifiedOn)
    expect(payload.estimates).toHaveLength(1)
    expect(payload.estimates[0].sourceUrls[0]).toContain('docs.x.ai')
  })
})
