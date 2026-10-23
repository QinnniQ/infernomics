import type { archiveByCap } from '../lib/platform'

type Row = ReturnType<typeof archiveByCap>[number]
const fmt = (n: number | null) => n === null ? '—' : Math.round(n).toLocaleString('en-US')

export function LatencyRangeChart({ rows }: { rows: Row[] }) {
  const domain = Math.max(1, ...rows.map(row => row.latency.max ?? 0))
  const pct = (n: number | null) => `${(n ?? 0) / domain * 100}%`
  return <div className="latency-range-chart"><div className="inline-heading"><strong>Completed-request latency ranges</strong><small>Client wall time · milliseconds · n shown per cap</small></div><p className="fineprint">Thin line: observed minimum to maximum. Thick band: middle 50% (Q1–Q3). Marker: median. Only completed responses with recorded timing.</p>{rows.map(row => <div className="range-row" key={row.run.id}><span>{row.run.maxOutputTokens} cap</span><div className="range-track" role="img" aria-label={`${row.run.maxOutputTokens} output-token cap: minimum ${fmt(row.latency.min)} ms, Q1 ${fmt(row.latency.q1)} ms, median ${fmt(row.latency.median)} ms, Q3 ${fmt(row.latency.q3)} ms, maximum ${fmt(row.latency.max)} ms, n=${row.latency.n}`}><i style={{ left: pct(row.latency.min), width: `${((row.latency.max ?? 0) - (row.latency.min ?? 0)) / domain * 100}%` }} /><b style={{ left: pct(row.latency.q1), width: `${((row.latency.q3 ?? 0) - (row.latency.q1 ?? 0)) / domain * 100}%` }} /><em style={{ left: pct(row.latency.median) }} /></div><strong>{fmt(row.latency.median)} ms <small>n={row.latency.n}</small></strong></div>)}<div className="range-axis"><span>0</span><span>{fmt(domain / 2)} ms</span><span>{fmt(domain)} ms</span></div></div>
}
