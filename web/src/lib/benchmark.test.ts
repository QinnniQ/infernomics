import { describe, expect, it } from 'vitest'
import raw from '../data/benchmark.json'
import { compatibleRuns, estimateCost, filterRuns, median, monthlyCost, sortRuns, summarize, validateBenchmark } from './benchmark'

const data = validateBenchmark(raw)

describe('published benchmark', () => {
  it('validates and preserves matching prompts for all exported runs', () => {
    expect(data.runs).toHaveLength(3)
    expect(compatibleRuns(data.runs)).toBe(true)
    expect(data.runs.every(run => run.items.length === 20)).toBe(true)
  })

  it('rejects malformed and duplicate run records', () => {
    expect(() => validateBenchmark({ ...data, runs: [data.runs[0], data.runs[0]] })).toThrow()
    expect(() => validateBenchmark({ ...data, runs: [{ ...data.runs[0], items: [{ ...data.runs[0].items[0], inputTokens: -1 }] }] })).toThrow()
  })

  it('rejects an incompatible prompt set', () => {
    const changed = { ...data.runs[1], items: [{ ...data.runs[1].items[0], prompt: 'different' }, ...data.runs[1].items.slice(1)] }
    expect(compatibleRuns([data.runs[0], changed])).toBe(false)
  })

  it('uses the mean of the two middle observations for even-sized medians', () => {
    expect(median([10, 2, 4, 8])).toBe(6)
    expect(median([])).toBeNull()
  })

  it('calculates only from recorded token counts and current USD list prices', () => {
    expect(estimateCost(1000, 500, data.pricing)).toBeCloseTo(0.00045)
    expect(monthlyCost(30_000, 1000, 500, data.pricing)).toEqual({ input: 4.5, output: 9, total: 13.5 })
    expect(() => estimateCost(-1, 1, data.pricing)).toThrow()
    expect(summarize(data.runs[0], data.pricing).costSample).toBe(20)
    expect(data.runs.map(run => summarize(run, data.pricing).incomplete)).toEqual([14, 10, 4])
  })

  it('filters by recorded configuration without changing the source runs', () => {
    expect(filterRuns(data.runs, { provider: 'OpenAI', model: '', task: '', cap: '50' })).toHaveLength(1)
    expect(filterRuns(data.runs, { provider: '', model: 'unknown', task: '', cap: '' })).toHaveLength(0)
    expect(data.runs).toHaveLength(3)
  })

  it('sorts by observed latency and derived cost without mutating source order', () => {
    expect(sortRuns(data.runs, 'latency', data.pricing).map(run => run.maxOutputTokens)).toEqual([100, 50, 200])
    expect(sortRuns(data.runs, 'cost', data.pricing).map(run => run.maxOutputTokens)).toEqual([50, 100, 200])
    expect(data.runs.map(run => run.maxOutputTokens)).toEqual([50, 100, 200])
  })
})
