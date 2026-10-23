import { describe, expect, it } from 'vitest'
import raw from '../data/model-catalog.v2.json'
import { estimateModelCost, validateCatalog } from './catalog'

const catalog = validateCatalog(raw)
describe('provider catalogue', () => {
  it('validates official provenance and required providers', () => {
    expect(new Set(catalog.models.map(model => model.provider))).toEqual(new Set(['OpenAI', 'Anthropic', 'Google', 'xAI', 'Ollama']))
    const forged = structuredClone(raw)
    forged.models[0].sources[0].url = 'https://example.com/pricing'
    expect(() => validateCatalog(forged)).toThrow()
  })
  it('switches xAI pricing at the documented 200k prompt threshold', () => {
    const grok = catalog.models.find(model => model.id === 'grok-4.6')!
    const basic = { requests: 1, inputTokens: 199999, outputTokens: 1000, retryPercent: 0, cachedInputPercent: 0 }
    expect(estimateModelCost(grok, basic)?.longContext).toBe(false)
    expect(estimateModelCost(grok, { ...basic, inputTokens: 200000 })?.total).toBeCloseTo(.812)
  })
  it('never presents local model cost as a measured dollar amount', () => {
    expect(estimateModelCost(catalog.models.find(model => model.id === 'phi3:latest')!, { requests: 1, inputTokens: 1, outputTokens: 1, retryPercent: 0, cachedInputPercent: 0 })).toBeNull()
  })
})
