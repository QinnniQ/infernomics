export type Scenario = { requests: number; retryPercent: number; incompletePercent: number; inputTokens: number; outputTokens: number; inputPerMillion: number; outputPerMillion: number }

export function hostedScenario(s: Scenario) {
  const values = Object.values(s)
  if (values.some(value => !Number.isFinite(value) || value < 0) || s.retryPercent > 100 || s.incompletePercent > 100) throw new Error('Invalid scenario inputs')
  const attempts = s.requests * (1 + s.retryPercent / 100 + s.incompletePercent / 100)
  const input = attempts * s.inputTokens * s.inputPerMillion / 1_000_000
  const output = attempts * s.outputTokens * s.outputPerMillion / 1_000_000
  return { attempts, input, output, total: input + output }
}

export function localScenario(attempts: number, latencyMs: number | null, watts: number | null, usdPerKwh: number | null, hardwareCost: number | null, amortizationMonths: number | null) {
  if ([attempts, latencyMs, watts, usdPerKwh, hardwareCost, amortizationMonths].some(value => value !== null && (!Number.isFinite(value) || value < 0))) throw new Error('Invalid local assumptions')
  if (amortizationMonths === 0) throw new Error('Amortization period must be positive')
  const energyKwh = latencyMs !== null && watts !== null ? attempts * latencyMs / 3_600_000 * watts / 1000 : null
  const electricity = energyKwh !== null && usdPerKwh !== null ? energyKwh * usdPerKwh : null
  const hardwareMonthly = hardwareCost !== null && amortizationMonths !== null ? hardwareCost / amortizationMonths : null
  return { energyKwh, electricity, hardwareMonthly,
    knownMonthlyTotal: electricity !== null && hardwareMonthly !== null ? electricity + hardwareMonthly : null }
}

export function breakEvenMonths(hostedMonthly: number, localElectricityMonthly: number | null, upfrontHardware: number | null): number | null {
  if (localElectricityMonthly === null || upfrontHardware === null || hostedMonthly <= localElectricityMonthly) return null
  return upfrontHardware / (hostedMonthly - localElectricityMonthly)
}
