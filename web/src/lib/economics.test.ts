import { describe, expect, it } from 'vitest'
import { breakEvenMonths, hostedScenario, localScenario } from './economics'

describe('scenario economics', () => {
  it('calculates transparent attempts and USD token cost', () => {
    const result = hostedScenario({ requests: 1000, retryPercent: 10, incompletePercent: 5, inputTokens: 1000, outputTokens: 500, inputPerMillion: .15, outputPerMillion: .6 })
    expect(result.attempts).toBeCloseTo(1150)
    expect(result.input).toBeCloseTo(.1725)
    expect(result.output).toBeCloseTo(.345)
    expect(result.total).toBeCloseTo(.5175)
  })
  it('keeps unknown energy cost unavailable and handles zero usage', () => {
    expect(localScenario(100, 2000, null, null, null, null).electricity).toBeNull()
    expect(hostedScenario({ requests: 0, retryPercent: 0, incompletePercent: 0, inputTokens: 0, outputTokens: 0, inputPerMillion: 0, outputPerMillion: 0 }).total).toBe(0)
  })
  it('uses measured or supplied assumptions for energy and break-even', () => {
    const local = localScenario(3600, 1000, 100, .2, 120, 12)
    expect(local.energyKwh).toBeCloseTo(.1)
    expect(local.electricity).toBeCloseTo(.02)
    expect(local.knownMonthlyTotal).toBeCloseTo(10.02)
    expect(breakEvenMonths(20, .02, 120)).toBeCloseTo(120 / 19.98)
    expect(breakEvenMonths(10, null, 120)).toBeNull()
  })
  it('rejects invalid rates', () => {
    expect(() => hostedScenario({ requests: 1, retryPercent: 110, incompletePercent: 0, inputTokens: 1, outputTokens: 1, inputPerMillion: 1, outputPerMillion: 1 })).toThrow()
    expect(() => localScenario(1, 100, 50, .2, 10, 0)).toThrow()
  })
})
