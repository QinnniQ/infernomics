import { useState } from 'react'
import rawLocal from '../data/local-benchmark.json'
import { breakEvenMonths, hostedScenario, localScenario } from '../lib/economics'
import { summarizeLocal, validateLocal, type LocalSnapshot } from '../lib/local'
import type { Pricing } from '../lib/benchmark'

const local: LocalSnapshot | null = (() => { try { return validateLocal(rawLocal) } catch { return null } })()
const money = (value: number | null) => value === null ? 'Unavailable' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(value)
const number = (value: number | null) => value === null ? 'Unavailable' : value.toLocaleString(undefined, { maximumFractionDigits: 2 })
const optional = (value: string) => value.trim() === '' ? null : Number(value)

export function EconomicsScenario({ pricing }: { pricing: Pricing }) {
  const [requests, setRequests] = useState(10000)
  const [input, setInput] = useState(1000)
  const [output, setOutput] = useState(500)
  const [retry, setRetry] = useState(0)
  const [incomplete, setIncomplete] = useState(0)
  const [model, setModel] = useState(local?.experiment?.models[0]?.id ?? '')
  const [watts, setWatts] = useState('')
  const [tariff, setTariff] = useState('')
  const [hardware, setHardware] = useState('')
  const [months, setMonths] = useState('')
  const metrics = model && local?.experiment ? summarizeLocal(local.observations.filter(row => row.model === model)) : null
  const hosted = hostedScenario({ requests, retryPercent: retry, incompletePercent: incomplete,
    inputTokens: input, outputTokens: output, inputPerMillion: pricing.inputPerMillion, outputPerMillion: pricing.outputPerMillion })
  const localCost = localScenario(hosted.attempts, metrics?.medianLatency ?? null, optional(watts), optional(tariff), optional(hardware), optional(months))
  const breakEven = breakEvenMonths(hosted.total, localCost.electricity, optional(hardware))
  return <section className="section shell scenario-section" id="scenario"><div className="section-head"><div><p className="section-kicker"><span />05 / SCENARIO MODEL</p><h2>Explore the economics.</h2><p>Change the assumptions and see the formulas. Hosted list prices and local operation are distinct evidence classes.</p></div></div>
    <div className="scenario-layout"><div className="scenario-form"><h3>Workload assumptions</h3><div className="scenario-inputs">
      <label>Requests per month<input type="number" min="0" value={requests} onChange={e => setRequests(Math.max(0, Number(e.target.value) || 0))} /></label>
      <label>Average input tokens<input type="number" min="0" value={input} onChange={e => setInput(Math.max(0, Number(e.target.value) || 0))} /></label>
      <label>Average output tokens<input type="number" min="0" value={output} onChange={e => setOutput(Math.max(0, Number(e.target.value) || 0))} /></label>
      <label>Extra retries (%)<input type="number" min="0" max="100" value={retry} onChange={e => setRetry(Math.min(100, Math.max(0, Number(e.target.value) || 0)))} /></label>
      <label>Incomplete attempts retried (%)<input type="number" min="0" max="100" value={incomplete} onChange={e => setIncomplete(Math.min(100, Math.max(0, Number(e.target.value) || 0)))} /></label>
    </div><p>Attempts = requests × (1 + retry% + incomplete retry%). The two percentages represent separate additional attempts. Every attempt is assumed to use the entered tokens; actual retry usage can differ.</p><h3>Optional local assumptions</h3><div className="scenario-inputs">
      <label>Measured local model<select value={model} onChange={e => setModel(e.target.value)} disabled={!local?.experiment}>{local?.experiment ? local.experiment.models.map(m => <option key={m.id} value={m.id}>{m.id}</option>) : <option value="">No local measurements</option>}</select></label>
      <label>Average power draw (W)<input type="number" min="0" value={watts} onChange={e => setWatts(e.target.value)} placeholder="Enter measured or assumed" /></label>
      <label>Electricity price (USD/kWh)<input type="number" min="0" step="0.01" value={tariff} onChange={e => setTariff(e.target.value)} placeholder="Enter your tariff" /></label>
      <label>Upfront hardware cost (USD)<input type="number" min="0" value={hardware} onChange={e => setHardware(e.target.value)} placeholder="Optional" /></label>
      <label>Amortization (months)<input type="number" min="1" value={months} onChange={e => setMonths(e.target.value)} placeholder="Optional" /></label>
    </div></div><div className="scenario-results"><span>HOSTED API · LIST PRICE SCENARIO</span><strong>{money(hosted.total)} <small>/ month</small></strong><p>{number(hosted.attempts)} expected attempts · {money(hosted.input)} input + {money(hosted.output)} output</p><hr /><span>LOCAL · PROVIDER INFERENCE FEE</span><strong>$0 <small>API fee</small></strong><p>Electricity: {money(localCost.electricity)} · Energy: {number(localCost.energyKwh)} kWh · Hardware amortization: {money(localCost.hardwareMonthly)}</p><p>Full local operating cost is unavailable: maintenance, hardware ownership, and other overhead are not measured.</p><hr /><span>ILLUSTRATIVE BREAK-EVEN</span><strong>{breakEven === null ? 'Unavailable' : `${number(breakEven)} months`}</strong><p>{breakEven === null ? 'Enter power, tariff, and upfront hardware cost, and ensure hosted monthly price exceeds modeled electricity.' : 'Upfront hardware ÷ (hosted monthly estimate − modeled electricity). Excludes other ownership and service costs.'}</p></div></div>
    <p className="scenario-caveat">Local runtime uses completed-request median wall time (n={metrics?.latencyN ?? 0}); incomplete and error attempts may take different time. Token counts come from your workload assumption and can differ between tokenizers. The hosted price was verified {pricing.verifiedOn}; it is not a historical bill or a forecast.</p>
  </section>
}
