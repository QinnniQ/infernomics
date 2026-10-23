import { describe, expect, it } from 'vitest'
import raw from '../data/local-benchmark.json'
import { localMedian, localStats, summarizeLocal, validateLocal, type LocalObservation } from './local'

describe('local evidence', () => {
  it('validates the real matched held-out publication', () => {
    const data = validateLocal(raw)
    expect(data.experiment?.models).toHaveLength(2)
    expect(data.observations).toHaveLength(24)
    expect(() => validateLocal({ ...data, observations: [data.observations[0], data.observations[0]] })).toThrow()
  })
  it('calculates medians and keeps failed attempts in denominators', () => {
    expect(localMedian([4, 1, 9, 2])).toBe(3)
    expect(localMedian([])).toBeNull()
    expect(localStats([1, 2, 3])).toMatchObject({ mean: 2, min: 1, max: 3, sampleStdDev: 1 })
    const base = { status: 'completed', wallMs: 100, tokensPerSecond: 20, evaluation: { passed: true } } as LocalObservation
    const rows = [base, { ...base, status: 'incomplete', evaluation: { passed: false } }, { ...base, status: 'error', wallMs: null, tokensPerSecond: null, evaluation: { passed: null } }] as LocalObservation[]
    expect(summarizeLocal(rows)).toMatchObject({ attempts: 3, completed: 1, incomplete: 1, errors: 1, assessed: 2, passed: 1, latencyN: 1, medianLatency: 100 })
  })
})
