import { describe, expect, it } from 'vitest'
import raw from '../data/hosted-prices.json'
import { validateHostedPrices } from './hostedPrices'
import { hostedScenario } from './economics'

describe('published hosted price references', () => {
  it('validates the versioned catalog and keeps estimates separate from measurements', () => {
    const catalog = validateHostedPrices(raw)
    expect(catalog.evidenceClass).toBe('published-list-price')
    expect(catalog.models.map(model => model.provider)).toContain('Anthropic')
    const haiku = catalog.models.find(model => model.id === 'claude-haiku-4-5')!
    const estimate = hostedScenario({ requests: 10000, retryPercent: 0, incompletePercent: 0,
      inputTokens: 1000, outputTokens: 500, inputPerMillion: haiku.inputPerMillion, outputPerMillion: haiku.outputPerMillion })
    expect(estimate.total).toBe(35)
  })
  it('rejects duplicate models and unofficial price sources', () => {
    expect(() => validateHostedPrices({ ...raw, models: [raw.models[0], raw.models[0]] })).toThrow()
    expect(() => validateHostedPrices({ ...raw, models: [{ ...raw.models[0], sourceUrl: 'https://example.com/prices' }] })).toThrow()
  })
})
