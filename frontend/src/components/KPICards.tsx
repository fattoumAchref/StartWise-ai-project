'use client'
import type { KPIs, MonteCarloResult, Benchmark, BenchmarkExtra } from '@/lib/types'

interface Props {
  kpis?: KPIs
  mc?: MonteCarloResult
  bench?: Benchmark
  extra?: BenchmarkExtra
  phase?: string
}

const fmt = (v: unknown, suffix = '') => {
  if (v == null) return '—'
  try { return Number(v).toLocaleString('fr-FR', { maximumFractionDigits: 1 }) + suffix }
  catch { return String(v) }
}
const pct = (v: unknown) => v != null ? `${(Number(v) * 100).toFixed(1)}%` : '—'

export default function KPICards({ kpis, mc, bench, extra, phase }: Props) {
  if (!kpis) return null

  const ltvCac = kpis.ltv && kpis.cac && kpis.cac > 0 ? kpis.ltv / kpis.cac : null

  const cards = [
    { label: 'Runway', value: kpis.cash_out_alert === 'RENTABLE' ? 'Cash-flow positif ✓' : kpis.runway_months != null ? `${kpis.runway_months.toFixed(1)} mois` : '—', sub: mc?.p50 != null ? `P50 Monte Carlo: ${mc.p50.toFixed(1)}m` : undefined },
    { label: 'Burn mensuel', value: kpis.burn_net != null ? fmt(kpis.burn_net, ' TND') : '—', sub: kpis.cash_out_alert === 'CRITIQUE' ? '🔴 Critique' : kpis.cash_out_alert === 'ATTENTION' ? '🟠 Attention' : undefined },
    { label: 'MRR', value: fmt(kpis.mrr, ' TND'), sub: kpis.arr != null ? `ARR: ${fmt(kpis.arr, ' TND')}` : undefined },
    { label: 'Gross Margin', value: kpis.gross_margin_pct != null ? `${kpis.gross_margin_pct.toFixed(1)}%` : '—', sub: bench?.gross_margin_median != null ? `Bench: ${(bench.gross_margin_median * 100).toFixed(1)}%` : kpis.gross_margin_status || undefined },
    { label: 'LTV/CAC', value: kpis.ltv_cac_ratio != null ? `${kpis.ltv_cac_ratio.toFixed(1)}x` : (ltvCac != null ? `${ltvCac.toFixed(1)}x` : '—'), sub: kpis.ltv_cac_status || undefined },
    { label: 'Survie 12m', value: mc?.proba_survie_12m != null ? `${(mc.proba_survie_12m * 100).toFixed(0)}%` : '—', sub: 'Monte Carlo ×1000' },
    { label: 'Breakeven', value: kpis.breakeven_months != null ? (kpis.breakeven_months === 0 ? 'Atteint ✓' : `${kpis.breakeven_months} mois`) : '—', sub: undefined },
    { label: 'Phase', value: phase || '—', sub: undefined },
  ].filter(c => c.value !== '—')

  return (
    <div className="kpi-grid">
      {cards.map(c => (
        <div className="kpi-card" key={c.label}>
          <div className="kpi-label">{c.label}</div>
          <div className="kpi-value">{c.value}</div>
          {c.sub && <div className="kpi-sub">{c.sub}</div>}
        </div>
      ))}
    </div>
  )
}
