import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { ArrowDownRight, ArrowRight, ArrowUpRight, Check, ChevronDown, CircleHelp, Clock3, Coins, ExternalLink, Github, Layers3, Menu, ShieldCheck, SlidersHorizontal, X } from 'lucide-react'
import rawData from './data/benchmark.json'
import { compatibleRuns, estimateCost, filterRuns, formatMicroUSD, formatMs, monthlyCost, sortRuns, summarize, validateBenchmark, type Filters } from './lib/benchmark'
import { LocalComparison } from './components/LocalComparison'
import { ProviderWorkspace } from './components/ProviderWorkspace'
import { EconomicsScenario } from './components/EconomicsScenario'
import { Methodology } from './components/Methodology'
import rawLocal from './data/local-v2-benchmark.json'
import { summarizeLocal, validateLocal } from './lib/local'
import './styles.css'
import './research.css'

const snapshot = (() => { try { return validateBenchmark(rawData) } catch { return null } })()
const runs = snapshot ? [...snapshot.runs].sort((a, b) => a.maxOutputTokens - b.maxOutputTokens) : []
const pricing = snapshot?.pricing
const localSnapshot = (() => { try { return validateLocal(rawLocal) } catch { return null } })()
const repo = 'https://github.com/QinnniQ/infernomics'
const initial = new URLSearchParams(window.location.search)

function fmtDate(value: string) {
  return new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(value))
}

function currency(value: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(value)
}

function IconMark() {
  return <span className="brand-mark" aria-hidden="true"><span /><span /><span /></span>
}

function SectionKicker({ children }: { children: React.ReactNode }) {
  return <p className="section-kicker"><span />{children}</p>
}

function App() {
  if (!snapshot || !pricing) return <main className="data-error"><h1>Benchmark data unavailable</h1><p>The published snapshot could not be validated. Please try a later release or inspect the source repository.</p><a href={repo}>View source code</a></main>
  const [filters, setFilters] = useState<Filters>({
    provider: initial.get('provider') || '', model: initial.get('model') || '',
    task: initial.get('task') || '', cap: initial.get('cap') || '',
  })
  const [sort, setSort] = useState(initial.get('sort') || 'cap')
  const [selected, setSelected] = useState<string[]>(() => {
    const selectedIds = initial.get('compare')?.split(',').filter(id => runs.some(run => run.id === id)) || []
    return selectedIds.length ? selectedIds : runs.slice(0, 3).map(run => run.id)
  })
  const [promptIndex, setPromptIndex] = useState(Number(initial.get('prompt') ?? '2'))
  const [detailId, setDetailId] = useState<string | null>(null)
  const [frequency, setFrequency] = useState<'day' | 'month'>('day')
  const [requests, setRequests] = useState(1000)
  const [inputTokens, setInputTokens] = useState(1000)
  const [outputTokens, setOutputTokens] = useState(500)
  const [mobileNav, setMobileNav] = useState(false)
  const [copied, setCopied] = useState(false)

  function writeUrl(nextFilters = filters, nextSort = sort, nextSelected = selected, nextPrompt = promptIndex) {
    const params = new URLSearchParams()
    Object.entries(nextFilters).forEach(([key, value]) => { if (value) params.set(key, value) })
    if (nextSort !== 'cap') params.set('sort', nextSort)
    params.set('compare', nextSelected.join(','))
    if (nextPrompt) params.set('prompt', String(nextPrompt))
    window.history.replaceState(null, '', `${window.location.pathname}?${params.toString()}${window.location.hash}`)
  }

  const visible = useMemo(() => sortRuns(filterRuns(runs, filters), sort, pricing), [filters, sort])
  const compared = runs.filter(run => selected.includes(run.id))
  const comparisonValid = compatibleRuns(compared)
  const activePrompt = Number.isInteger(promptIndex) && promptIndex >= 0 && promptIndex < 20 ? promptIndex : 0
  const monthlyRequests = frequency === 'day' ? requests * 30 : requests
  const costs = monthlyCost(monthlyRequests, inputTokens, outputTokens, pricing)
  const detail = runs.find(run => run.id === detailId)
  const archiveAttempts = runs.reduce((total, run) => total + run.items.length, 0)
  const archiveIncomplete = runs.reduce((total, run) => total + run.items.filter(item => item.status === 'incomplete').length, 0)
  const localExperiment = localSnapshot?.experiment
  const localRows = localSnapshot?.observations ?? []

  useEffect(() => {
    const id = decodeURIComponent(window.location.hash.slice(1))
    if (id) document.getElementById(id)?.scrollIntoView({ behavior: 'auto' })
  }, [])

  useEffect(() => {
    if (!detailId) return
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const close = document.querySelector<HTMLButtonElement>('.modal .icon-button')
    close?.focus()
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setDetailId(null)
      if (event.key !== 'Tab') return
      const focusable = [...document.querySelectorAll<HTMLElement>('.modal button, .modal summary, .modal a, .modal input, .modal select')]
      if (!focusable.length) return
      const first = focusable[0]; const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => { document.removeEventListener('keydown', onKeyDown); previous?.focus() }
  }, [detailId])

  function changeFilter(name: keyof Filters, value: string) {
    const next = { ...filters, [name]: value }
    setFilters(next); writeUrl(next)
  }
  function toggleCompare(id: string) {
    const next = selected.includes(id) ? selected.filter(item => item !== id) : selected.length < 4 ? [...selected, id] : selected
    setSelected(next); writeUrl(filters, sort, next)
  }
  async function share() {
    writeUrl()
    try { await navigator.clipboard.writeText(window.location.href); setCopied(true); window.setTimeout(() => setCopied(false), 2500) }
    catch { setCopied(false) }
  }

  return <>
    <a className="skip-link" href="#main">Skip to content</a>
    <header className="site-header">
      <div className="shell header-inner">
        <a className="brand" href="#top" aria-label="Infernomics home"><IconMark /><span>infernomics<span className="brand-dot">.</span></span></a>
        <button className="mobile-menu" type="button" aria-label={mobileNav ? 'Close navigation' : 'Open navigation'} aria-expanded={mobileNav} onClick={() => setMobileNav(!mobileNav)}>{mobileNav ? <X size={21} /> : <Menu size={21} />}</button>
        <nav className={mobileNav ? 'nav-links open' : 'nav-links'} aria-label="Primary">
          <a href="#workspace" onClick={() => setMobileNav(false)}>Compare models</a>
          <a href="#explorer" onClick={() => setMobileNav(false)}>Historical archive</a>
          <a href="#calculator" onClick={() => setMobileNav(false)}>Economics</a>
          <a href="#methodology" onClick={() => setMobileNav(false)}>Methodology</a>
        </nav>
        <a className="header-github" aria-label="Source code on GitHub" href={repo} target="_blank" rel="noreferrer"><Github size={17} /><span>Source code</span><ArrowUpRight size={14} /></a>
      </div>
    </header>

    <main id="main">
      <section className="hero shell" id="top">
        <div className="hero-copy">
          <div className="eyebrow"><span className="eyebrow-pulse" />THE INFERENCE DECISION DESK<span className="eyebrow-rule" />OPEN BENCHMARK DATA</div>
          <h1>Every token has a cost. <em>Every model has a trade-off.</em></h1>
          <p className="hero-lead">Compare five providers through documented prices and capabilities, inspect recorded local responses, and model your workload. Each conclusion stays within its evidence.</p>
          <div className="hero-actions"><a className="button button-primary" href="#workspace">Open workspace <ArrowRight size={18} /></a><a className="button button-text" href="#methodology">Explore methodology <ArrowDownRight size={18} /></a></div>
          <div className="hero-proof"><ShieldCheck size={17} /><span>Saved measurements · No account · No live API calls</span></div>
        </div>
        {localExperiment ? <div className="hero-panel local-hero" aria-label="Local model comparison overview">
          <div className="panel-top"><span><span className="live-dot" />LOCAL MODEL STUDY</span><span>MEASURED / TEST</span></div>
          <div className="panel-heading"><span>One protocol. Two models.</span><span className="panel-tag">OLLAMA · LOCAL</span></div>
          <div className="panel-sub">{localExperiment.datasetVersion} · {localExperiment.repetitions} repetitions per prompt</div>
          <div className="panel-chart-title"><span>Completed attempts</span><span>ALL ATTEMPTS IN DENOMINATOR</span></div>
          <div className="hero-bars">{localExperiment.models.map(model => { const s = summarizeLocal(localRows.filter(row => row.model === model.id)); return <div className="hero-bar-row" key={model.id}><span>{model.id}</span><div className="hero-bar-track"><div style={{ width: `${s.attempts ? s.completed / s.attempts * 100 : 0}%` }} /></div><strong>{s.completed}/{s.attempts}</strong></div> })}</div>
          <div className="panel-foot"><span>Objective checks and responses are inspectable below</span><span>{localRows.length} attempts</span></div>
        </div> : <div className="hero-panel" aria-label="Historical benchmark snapshot overview">
          <div className="panel-top"><span><span className="live-dot" />HISTORICAL SNAPSHOT</span><span>ARCHIVE / 2026</span></div>
          <div className="panel-heading"><span>GPT-4o mini</span><span className="panel-tag">CHAT · FEB 2026</span></div>
          <div className="panel-sub">One model, {runs.length} output limits, identical prompts.</div>
          <div className="panel-chart-title"><span>Median end-to-end latency</span><span>LOWER IS BETTER ↓</span></div>
          <div className="hero-bars">
            {runs.map(run => { const s = summarize(run, pricing); return <div className="hero-bar-row" key={run.id}><span>{run.maxOutputTokens} tokens</span><div className="hero-bar-track"><div style={{ width: `${Math.max(9, (s.medianLatency || 0) / 2300 * 100)}%` }} /></div><strong>{formatMs(s.medianLatency)}</strong></div> })}
          </div>
          <div className="panel-foot"><span>Completed only · n = {runs.map(run => summarize(run, pricing).latencySample).join(' / ')}</span><span>{runs[0]?.items.length ?? 0} prompts / setting</span></div>
        </div>}
      </section>

      <section className="insight-strip"><div className="shell insight-inner">
        <div><span className="insight-icon"><Layers3 size={18} /></span><span><strong>{localExperiment ? localExperiment.models.length + ' local models' : runs.length + ' archive configurations'}</strong><small>{localExperiment ? 'Matched held-out prompts' : 'Same model and prompt set'}</small></span></div>
        <div><span className="insight-icon"><Clock3 size={18} /></span><span><strong>{archiveAttempts} archived attempts</strong><small>{archiveIncomplete} ended at the output cap</small></span></div>
        <div><span className="insight-icon"><Coins size={18} /></span><span><strong>Transparent cost estimates</strong><small>Current USD list price, no discounts</small></span></div>
      </div></section>

      <ProviderWorkspace />
      <LocalComparison />
      <section className="section shell" id="explorer">
        <div className="section-head"><div><SectionKicker>02 / HISTORICAL API ARCHIVE</SectionKicker><h2>Explore the original evidence.</h2><p>Filter recorded GPT-4o-mini runs and see how output limits changed completion. This archive is separate from local model measurements.</p></div><div className="section-side">DATA RECORDED <strong>18 FEB 2026</strong><span>Pricing checked 15 Oct 2026</span></div></div>
        <div className="notice"><CircleHelp size={18} /><div><strong>Scope of this snapshot</strong><span>All published chat runs use one model. Of 60 attempts, 28 ended incomplete at the output limit. Quality was not evaluated, so no quality ranking or cross-model recommendation is shown. Current list prices estimate cost from recorded tokens; they are not historical bills.</span></div></div>
        <div className="explorer-card">
          <div className="toolbar"><div className="toolbar-title"><SlidersHorizontal size={18} /><strong>Refine results</strong><span>{visible.length} of {runs.length} runs</span></div><button className="link-button" type="button" onClick={() => { const empty = { provider: '', model: '', task: '', cap: '' }; setFilters(empty); writeUrl(empty) }}>Clear filters</button></div>
          <div className="filter-grid">
            <label>Provider<select value={filters.provider} onChange={event => changeFilter('provider', event.target.value)}><option value="">All providers</option><option value="OpenAI">OpenAI</option></select></label>
            <label>Model<select value={filters.model} onChange={event => changeFilter('model', event.target.value)}><option value="">All models</option><option value="gpt-4o-mini">gpt-4o-mini</option></select></label>
            <label>Task<select value={filters.task} onChange={event => changeFilter('task', event.target.value)}><option value="">All tasks</option><option value="General chat prompts">General chat prompts</option></select></label>
            <label>Output limit<select value={filters.cap} onChange={event => changeFilter('cap', event.target.value)}><option value="">All settings</option>{runs.map(run => <option key={run.id} value={run.maxOutputTokens}>{run.maxOutputTokens} tokens</option>)}</select></label>
            <label>Sort by<select value={sort} onChange={event => { setSort(event.target.value); writeUrl(filters, event.target.value) }}><option value="cap">Output limit</option><option value="cost">Est. cost (low first)</option><option value="latency">Median latency (fast first)</option><option value="date">Date (newest)</option></select></label>
          </div>
          <div className="chart-block"><div className="chart-heading"><div><h3>Latency vs estimated request cost</h3><p>Each point is one 20-prompt run. Median latency covers completed responses only; mean recalculated cost covers all attempts.</p></div><span>↙ LOWER / BETTER</span></div>
            <div className="scatter-wrap"><svg className="scatter" viewBox="0 0 800 270" role="img" aria-labelledby="scatter-title scatter-desc"><title id="scatter-title">Cost versus latency for filtered benchmark runs</title><desc id="scatter-desc">The table after this chart provides the exact figures and accessible run details.</desc><line x1="74" y1="18" x2="74" y2="218" className="axis" /><line x1="74" y1="218" x2="760" y2="218" className="axis" /><line x1="74" y1="118" x2="760" y2="118" className="gridline" /><text x="74" y="249" className="axis-label">0</text><text x="694" y="249" className="axis-label">MEDIAN LATENCY (MS) →</text><text x="5" y="24" className="axis-label">µ$ / REQ</text>{visible.map(run => { const s = summarize(run, pricing); const x = 74 + ((s.medianLatency || 0) / 2400) * 650; const y = 218 - ((s.meanCost || 0) * 1_000_000 / 80) * 190; return <g key={run.id}><circle cx={x} cy={y} r="11" className="chart-point" /><text x={x + 20} y={y + 5} className="point-label">{run.maxOutputTokens} tokens</text></g> })}</svg></div>
            <p className="chart-caption">Cost is derived from recorded input and output tokens at the verified list price. It excludes taxes, discounts, and other charges.</p>
          </div>
          <div className="table-scroll"><table><caption className="sr-only">Filtered benchmark results with exact metrics and run details</caption><thead><tr><th scope="col">Configuration</th><th scope="col">Median latency <small>measured</small></th><th scope="col">Cost / request <small>estimated</small></th><th scope="col">Complete <small>observed</small></th><th scope="col">Quality</th><th scope="col" aria-label="Actions"></th></tr></thead><tbody>{visible.map(run => { const s = summarize(run, pricing); return <tr key={run.id}><th scope="row"><span className="model-name">{run.model}</span><span className="cell-sub">max output {run.maxOutputTokens} tokens · {fmtDate(run.executedAt)}</span></th><td className="metric-cell">{formatMs(s.medianLatency)}<span className="cell-sub">n = {s.latencySample}</span></td><td className="metric-cell">{formatMicroUSD(s.meanCost)}<span className="cell-sub">n = {s.costSample}</span></td><td className="metric-cell">{s.success}/{s.sample}<span className="cell-sub">{s.incomplete} truncated · {s.errors} errors</span></td><td><span className="unavailable">Not scored</span></td><td><button className="table-action" type="button" onClick={() => setDetailId(run.id)} aria-label={`Inspect run with ${run.maxOutputTokens} output tokens`}>Inspect <ArrowUpRight size={15} /></button></td></tr> })}</tbody></table></div>
          {!visible.length && <div className="empty-state"><h3>No runs match these filters.</h3><p>Clear the filters to see the published benchmark configurations.</p></div>}
          <div className="table-footer"><span>3 documented runs · 60 observations · 1 model</span><button className="link-button" type="button" onClick={share}>{copied ? <Check size={15} /> : <ArrowUpRight size={15} />}{copied ? 'Link copied' : 'Copy filtered view'}</button></div>
        </div>
      </section>

      <section className="section section-tinted" id="comparison"><div className="shell">
        <div className="section-head"><div><SectionKicker>03 / ARCHIVE RESPONSE COMPARISON</SectionKicker><h2>Same prompt. Different limits.</h2><p>Compare two or three recorded configurations for identical prompts. Response quality was not independently scored.</p></div><div className="section-side">CONTROLLED VARIABLE <strong>MAX OUTPUT TOKENS</strong><span>Other generation settings were not logged</span></div></div>
        <div className="comparison-controls"><fieldset><legend>Choose configurations <span>(select 2–3)</span></legend><div className="chip-row">{runs.map(run => <label className={selected.includes(run.id) ? 'chip selected' : 'chip'} key={run.id}><input type="checkbox" checked={selected.includes(run.id)} onChange={() => toggleCompare(run.id)} disabled={!selected.includes(run.id) && selected.length >= 4} /><span>{run.maxOutputTokens} token limit</span></label>)}</div></fieldset><label className="prompt-select">Test prompt <span>{activePrompt + 1} of 20</span><select value={activePrompt} onChange={event => { const next = Number(event.target.value); setPromptIndex(next); writeUrl(filters, sort, selected, next) }}>{runs[0].items.map(item => <option key={item.index} value={item.index}>{String(item.index + 1).padStart(2, '0')} · {item.prompt}</option>)}</select></label></div>
        {comparisonValid ? <><div className="prompt-card"><span>IDENTICAL INPUT / PROMPT {String(activePrompt + 1).padStart(2, '0')}</span><p>{runs[0].items[activePrompt].prompt}</p></div><div className="response-grid" style={{ gridTemplateColumns: `repeat(${compared.length}, minmax(0, 1fr))` }}>{compared.map(run => { const item = run.items[activePrompt]; const cost = item.inputTokens !== null && item.outputTokens !== null ? estimateCost(item.inputTokens, item.outputTokens, pricing) : null; return <article className="response-card" key={run.id}><div className="response-top"><div><span className="response-index">0{run.maxOutputTokens === 50 ? 1 : run.maxOutputTokens === 100 ? 2 : 3}</span><h3>{run.maxOutputTokens} token limit</h3><small>{run.resolvedModel}</small></div><span className={item.error || item.status !== 'completed' ? 'status error' : 'status'}>{item.error || item.status !== 'completed' ? 'Incomplete' : 'Completed'}</span></div><div className="response-content"><span>RECORDED RESPONSE</span><p>{item.response || 'No response recorded.'}</p></div><div className="response-metrics"><div><span>INPUT / OUTPUT</span><strong>{item.inputTokens ?? '—'} / {item.outputTokens ?? '—'} <small>tokens</small></strong></div><div><span>LATENCY</span><strong>{formatMs(item.latencyMs)}</strong></div><div><span>EST. COST</span><strong>{formatMicroUSD(cost)}</strong></div><div><span>QUALITY</span><strong>Not scored</strong></div></div></article> })}</div><p className="compare-caveat"><CircleHelp size={16} />Responses were generated in separate sequential runs. Timing also reflects network and service conditions, and incomplete attempts are excluded from displayed latency medians. A lower output limit does not isolate a model speed effect. No quality conclusion can be drawn from these examples alone.</p></> : <div className="empty-state"><h3>Select at least two compatible runs.</h3><p>Only runs with the same model snapshot, task, dataset, and prompts can be compared here.</p></div>}
      </div></section>

      <section className="section shell" id="calculator"><div className="section-head"><div><SectionKicker>04 / HISTORICAL API COST</SectionKicker><h2>Put a price on the archive.</h2><p>Estimate the archived OpenAI model's monthly token cost. <a href="#workspace">Compare documented rates across all five providers</a> in the workspace above. No requests are sent.</p></div><div className="section-side">PRICE BASIS <strong>USD LIST PRICE</strong><span>Verified 15 Oct 2026</span></div></div>
        <div className="calculator-grid"><div className="calc-form"><div className="calc-top"><Coins size={20} /><strong>Workload inputs</strong></div><label>Model<select value="gpt-4o-mini" onChange={() => undefined}><option value="gpt-4o-mini">gpt-4o-mini (legacy model)</option></select></label><div className="request-label"><span>Request volume</span><div className="segmented" role="group" aria-label="Request frequency"><button type="button" className={frequency === 'day' ? 'active' : ''} onClick={() => setFrequency('day')}>Per day</button><button type="button" className={frequency === 'month' ? 'active' : ''} onClick={() => setFrequency('month')}>Per month</button></div></div><input aria-label={`Requests per ${frequency}`} type="number" min="0" max="1000000000" value={requests} onChange={event => setRequests(Math.min(1_000_000_000, Math.max(0, Number(event.target.value) || 0)))} /><div className="input-pair"><label>Avg. input tokens / request<input type="number" min="0" max="1000000" value={inputTokens} onChange={event => setInputTokens(Math.min(1_000_000_000, Math.max(0, Number(event.target.value) || 0)))} /></label><label>Avg. output tokens / request<input type="number" min="0" max="1000000" value={outputTokens} onChange={event => setOutputTokens(Math.min(1_000_000_000, Math.max(0, Number(event.target.value) || 0)))} /></label></div><p className="form-note">Uses 30 days per month for daily volume. Enter your expected uncached token use.</p></div><div className="calc-result"><span className="result-label">PROJECTED MONTHLY COST</span><strong className="result-total">{currency(costs.total)}</strong><span className="result-requests">for {monthlyRequests.toLocaleString()} requests / month</span><div className="cost-breakdown"><div><span>Input tokens <small>${pricing.inputPerMillion.toFixed(2)} / 1M</small></span><strong>{currency(costs.input)}</strong></div><div><span>Output tokens <small>${pricing.outputPerMillion.toFixed(2)} / 1M</small></span><strong>{currency(costs.output)}</strong></div><div className="total-row"><span>Total estimate</span><strong>{currency(costs.total)}</strong></div></div><p>List-price estimate, not a billing forecast. This model is marked deprecated by the provider. Excludes cached-token discounts, batch pricing, taxes, tools, retries, and provider-specific charges.</p><a href={pricing.sourceUrl} target="_blank" rel="noreferrer">View pricing source <ExternalLink size={14} /></a></div></div>
      </section>

      <EconomicsScenario />
      <Methodology />
      <section className="section method-section" id="archive-methodology"><div className="shell"><div className="section-head"><div><SectionKicker>07 / HISTORICAL ARCHIVE METHODS</SectionKicker><h2>What the original archive means.</h2><p>Open methods and explicit limits make these results useful without pretending they answer more than they can.</p></div></div><div className="method-grid"><article><span className="method-number">01</span><h3>Experiment design</h3><p>Twenty fixed, general-purpose chat prompts were sent to the OpenAI Responses API for each of three output caps: 50, 100, and 200 tokens. The requested alias was <code>gpt-4o-mini</code>; responses report the resolved snapshot <code>gpt-4o-mini-2024-07-18</code>.</p></article><article><span className="method-number">02</span><h3>Measured and derived</h3><p>Input/output token counts and elapsed wall time were stored per request. Latency starts immediately before the SDK request and stops after its response, including network and provider processing. The explorer reports median completed-request latency (n=6, 10, or 16 depending on the cap). Cost is recalculated from those tokens using a current USD list price.</p></article><article><span className="method-number">03</span><h3>What is missing</h3><p>No chat quality rubric, human review, or judge score exists for these runs. Twenty-eight of 60 attempts ended incomplete because the output cap was reached. Time to first token, retries, temperature, prompt-template version, and original billing records were not captured. The 20 prompts are a small convenience sample, not a representative workload.</p></article><article><span className="method-number">04</span><h3>Build and release</h3><p>A read-only Python export validates archived SQLite rows and publishes only necessary fields. A static TypeScript/React frontend calculates summaries in the browser. The production build is prepared for Cloudflare Pages static hosting; Python benchmark jobs run separately and require explicit API credentials and cost approval.</p></article></div><div className="method-bottom"><div><ShieldCheck size={22} /><span><strong>Reproducible by inspection</strong><small>Run IDs, dataset hash, observations, formulas, and source code are available in the repository.</small></span></div><a href={`${repo}/blob/main/README.md`} target="_blank" rel="noreferrer">Read the technical documentation <ArrowUpRight size={17} /></a></div></div></section>
    </main>
    <footer className="footer"><div className="shell footer-inner"><div><a className="brand" href="#top"><IconMark /><span>infernomics<span className="brand-dot">.</span></span></a><p>Evidence for better inference decisions.</p></div><div className="footer-links"><a href="#explorer">Explorer</a><a href="#methodology">Methodology</a><a href={repo} target="_blank" rel="noreferrer">GitHub <ArrowUpRight size={13} /></a></div><span className="footer-note">Archived measurements · Current prices are estimates</span></div></footer>

    {detail && <div className="modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) setDetailId(null) }}><div className="modal" role="dialog" aria-modal="true" aria-labelledby="detail-title"><div className="modal-header"><div><SectionKicker>RUN DETAILS</SectionKicker><h2 id="detail-title">{detail.model} · {detail.maxOutputTokens} tokens</h2></div><button type="button" className="icon-button" aria-label="Close run details" onClick={() => setDetailId(null)}><X size={21} /></button></div><div className="modal-body"><dl className="detail-list"><div><dt>Run ID</dt><dd><code>{detail.id}</code></dd></div><div><dt>Executed</dt><dd>{new Date(detail.executedAt).toLocaleString('en', { timeZone: 'UTC' })} UTC</dd></div><div><dt>Provider / requested model</dt><dd>{detail.provider} / {detail.model}</dd></div><div><dt>Resolved model</dt><dd>{detail.resolvedModel}</dd></div><div><dt>Task / dataset hash</dt><dd>{detail.task}<br /><code className="wrap-code">{detail.datasetVersion}</code></dd></div><div><dt>Evaluation</dt><dd>No quality assessment. Completion status is recorded.</dd></div><div><dt>Latency definition</dt><dd>Elapsed SDK request/response wall time, milliseconds; successful responses only in median.</dd></div><div><dt>Cost basis</dt><dd>Derived USD list-price estimate from observed tokens. Archived cost values excluded.</dd></div></dl><h3>Observations <span>({detail.items.length})</span></h3><div className="observation-list">{detail.items.map(item => <details key={item.id}><summary><span>#{String(item.index + 1).padStart(2, '0')} · {item.prompt}</span><span>{formatMs(item.latencyMs)} <ChevronDown size={15} /></span></summary><div><p><strong>Response</strong><br />{item.response || 'No response recorded'}</p><p><strong>Recorded tokens:</strong> {item.inputTokens ?? '—'} input / {item.outputTokens ?? '—'} output · <strong>Status:</strong> {item.status}{item.incompleteReason ? ` (${item.incompleteReason})` : ""}</p><p><strong>Est. request cost:</strong> {item.inputTokens !== null && item.outputTokens !== null ? formatMicroUSD(estimateCost(item.inputTokens, item.outputTokens, pricing)) : 'Unavailable'}</p><small>Observation ID: {item.id}</small></div></details>)}</div></div></div></div>}
  </>
}

createRoot(document.getElementById('root')!).render(<App />)
