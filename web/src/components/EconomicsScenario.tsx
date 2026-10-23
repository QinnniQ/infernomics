import { useState } from 'react'
import rawCatalog from '../data/model-catalog.v2.json'
import rawLocal from '../data/local-benchmark.json'
import { validateCatalog, type CatalogModel } from '../lib/catalog'
import { hostedScenario, localScenario, breakEvenMonths } from '../lib/economics'
import { validateLocal, summarizeLocal } from '../lib/local'

const catalog = validateCatalog(rawCatalog)
const local = validateLocal(rawLocal)
const hostedModels = catalog.models.filter(model => model.kind === 'hosted')
const money = (n: number | null) => n === null ? 'Unavailable' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(n)
const optional = (s: string) => s.trim() ? Number(s) : null
const rate = (m: CatalogModel, inputTokens: number) => {
  const p = m.pricing!
  const long = p.thresholdTokens !== null && inputTokens >= p.thresholdTokens
  return { inputPerMillion: long ? p.longInput! : p.input, outputPerMillion: long ? p.longOutput! : p.output }
}

export function EconomicsScenario() {
  const [requests, setRequests] = useState(10000)
  const [input, setInput] = useState(1000)
  const [output, setOutput] = useState(500)
  const [retry, setRetry] = useState(0)
  const [incomplete, setIncomplete] = useState(0)
  const [hostedId, setHostedId] = useState('gpt-4o-mini')
  const [localId, setLocalId] = useState(local.experiment?.models[0]?.id ?? '')
  const [watts, setWatts] = useState('')
  const [tariff, setTariff] = useState('')
  const [hardware, setHardware] = useState('')
  const [months, setMonths] = useState('')
  const hostedModel = hostedModels.find(m => m.id === hostedId)!
  const scenario = (m: CatalogModel) => hostedScenario({ requests, retryPercent: retry, incompletePercent: incomplete, inputTokens: input, outputTokens: output, ...rate(m, input) })
  const hosted = scenario(hostedModel)
  const selectedWithin = (hostedModel.contextTokens === null || input + output <= hostedModel.contextTokens) && (hostedModel.maxOutputTokens === null || output <= hostedModel.maxOutputTokens)
  const localMetric = localId ? summarizeLocal(local.observations.filter(o => o.model === localId)) : null
  const localCost = localScenario(hosted.attempts, localMetric?.medianLatency ?? null, optional(watts), optional(tariff), optional(hardware), optional(months))
  const breakEven = selectedWithin ? breakEvenMonths(hosted.total, localCost.electricity, optional(hardware)) : null
  return <section className="section shell scenario-section" id="scenario"><div className="section-head"><div><p className="section-kicker"><span />05 / SCENARIO MODEL</p><h2>Explore the economics.</h2><p>Hosted list prices and local operation are distinct evidence classes. Change the assumptions to inspect the formulas.</p></div></div>
    <div className="scenario-layout"><div className="scenario-form"><h3>Workload assumptions</h3><label className="scenario-hosted-select">Hosted price reference<select value={hostedId} onChange={e => setHostedId(e.target.value)}>{hostedModels.map(m => <option value={m.id} key={m.id}>{m.provider} · {m.name}</option>)}</select></label><div className="scenario-inputs">
      <label>Requests per month<input type="number" min="0" value={requests} onChange={e => setRequests(Math.max(0, Number(e.target.value) || 0))} /></label>
      <label>Average input tokens<input type="number" min="0" value={input} onChange={e => setInput(Math.max(0, Number(e.target.value) || 0))} /></label>
      <label>Average output tokens<input type="number" min="0" value={output} onChange={e => setOutput(Math.max(0, Number(e.target.value) || 0))} /></label>
      <label>Extra retries (%)<input type="number" min="0" max="100" value={retry} onChange={e => setRetry(Math.min(100, Math.max(0, Number(e.target.value) || 0)))} /></label>
      <label>Incomplete attempts retried (%)<input type="number" min="0" max="100" value={incomplete} onChange={e => setIncomplete(Math.min(100, Math.max(0, Number(e.target.value) || 0)))} /></label>
    </div><p>Attempts = requests × (1 + retry% + incomplete retry%). Every attempt is assumed to consume the entered tokens. Caching is excluded here; the comparison workspace has a documented cache assumption.</p><h3>Optional local assumptions</h3><div className="scenario-inputs">
      <label>Measured local model<select value={localId} onChange={e => setLocalId(e.target.value)}>{local.experiment?.models.map(m => <option key={m.id} value={m.id}>{m.id}</option>)}</select></label>
      <label>Average power draw (W)<input type="number" min="0" value={watts} onChange={e => setWatts(e.target.value)} placeholder="Measured or assumed" /></label>
      <label>Electricity price (USD/kWh)<input type="number" min="0" step="0.01" value={tariff} onChange={e => setTariff(e.target.value)} placeholder="Your tariff" /></label>
      <label>Upfront hardware cost (USD)<input type="number" min="0" value={hardware} onChange={e => setHardware(e.target.value)} placeholder="Optional" /></label>
      <label>Amortization (months)<input type="number" min="1" value={months} onChange={e => setMonths(e.target.value)} placeholder="Optional" /></label>
    </div></div><div className="scenario-results"><span>HOSTED API · LIST PRICE SCENARIO</span><strong>{selectedWithin ? money(hosted.total) : 'Outside limits'} <small>{selectedWithin ? '/ month' : ''}</small></strong><p>{hostedModel.provider} {hostedModel.name} · {hosted.attempts.toLocaleString()} attempts{selectedWithin ? ` · ${money(hosted.input)} input + ${money(hosted.output)} output` : ' · entered tokens exceed documented model limits'}</p><hr /><span>LOCAL · PROVIDER INFERENCE FEE</span><strong>$0 <small>API fee</small></strong><p>Electricity: {money(localCost.electricity)} · Energy: {localCost.energyKwh?.toFixed(2) ?? 'Unavailable'} kWh · Hardware amortization: {money(localCost.hardwareMonthly)}</p><p>Full operating cost is unknown: maintenance and other overhead are unmeasured.</p><hr /><span>ILLUSTRATIVE BREAK-EVEN</span><strong>{breakEven === null ? 'Unavailable' : `${breakEven.toFixed(1)} months`}</strong><p>Upfront hardware ÷ (hosted monthly estimate − modeled electricity). Requires positive savings and excludes other ownership costs.</p></div></div>
    <div className="hosted-prices"><h3>Official provider list prices</h3><p>Same hypothetical text token counts and attempt volume. No hosted quality or latency is inferred.</p><div className="hosted-prices-scroll"><table><thead><tr><th>Provider / model</th><th>Input / 1M</th><th>Output / 1M</th><th>Monthly scenario</th><th>Official source</th></tr></thead><tbody>{hostedModels.map(m => { const r = rate(m, input); const within = (m.contextTokens === null || input + output <= m.contextTokens) && (m.maxOutputTokens === null || output <= m.maxOutputTokens); return <tr key={m.id}><th>{m.provider}<small>{m.name} · {m.id}</small></th><td>{money(r.inputPerMillion)}</td><td>{money(r.outputPerMillion)}</td><td>{within ? money(scenario(m).total) : 'Outside model limits'}</td><td><a href={m.sources[0].url} target="_blank" rel="noreferrer">Source</a></td></tr> })}</tbody></table></div><p>Verified {catalog.verifiedOn}. xAI long-context rates apply at 200k prompt tokens. Rates exclude cache, batch, tools, taxes and regional premiums. Provider tokenizers differ; identical entered token counts do not imply identical billed text.</p></div>
    <p className="scenario-caveat">Local operation uses completed-request median wall time (n={localMetric?.latencyN ?? 0}); errors and incomplete attempts may differ. The price model is a scenario, not an invoice or forecast.</p>
  </section>
}
