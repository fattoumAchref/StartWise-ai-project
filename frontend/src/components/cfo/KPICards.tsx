'use client'
import type { KPIs, MonteCarloResult, Benchmark, BenchmarkExtra } from '@/lib/types'

interface Props {
  kpis?: KPIs
  mc?: MonteCarloResult
  bench?: Benchmark
  extra?: BenchmarkExtra
  phase?: string
  expertMode?: boolean
}

const fmt = (v: unknown, suffix = '') => {
  if (v == null) return '—'
  try { return Number(v).toLocaleString('fr-FR', { maximumFractionDigits: 1 }) + suffix }
  catch { return String(v) }
}

export default function KPICards({ kpis, mc, bench, phase, expertMode }: Props) {
  if (!kpis) return null

  const ltvCac = kpis.ltv && kpis.cac && kpis.cac > 0 ? kpis.ltv / kpis.cac : null

  const runwayValue = kpis.cash_out_alert === 'RENTABLE'
    ? (expertMode ? 'Cash-flow+ ✓' : 'Rentable ✓')
    : kpis.runway_months != null ? `${kpis.runway_months.toFixed(1)} mois` : '—'

  const burnAlert = kpis.cash_out_alert === 'CRITIQUE' ? '🔴 Critique — agissez vite'
    : kpis.cash_out_alert === 'ATTENTION' ? '🟠 Attention' : undefined

  const phaseLabel = phase
    ? (expertMode ? phase : phase === 'SEED' ? 'Démarrage' : phase === 'TRACTION' ? 'Croissance' : phase === 'FUNDRAISING' ? 'Recherche fonds' : phase)
    : '—'

  type Card = { label: string; value: string; sub?: string; hint?: string }

  const cards: Card[] = expertMode ? [
    { label: 'Runway', value: runwayValue, sub: mc?.p50 != null ? `P50: ${mc.p50.toFixed(1)}m` : undefined },
    { label: 'Burn net/mois', value: kpis.burn_net != null ? fmt(kpis.burn_net, ' TND') : '—', sub: burnAlert },
    { label: 'MRR', value: fmt(kpis.mrr, ' TND'), sub: kpis.arr != null ? `ARR: ${fmt(kpis.arr, ' TND')}` : undefined },
    { label: 'Gross Margin', value: kpis.gross_margin_pct != null ? `${kpis.gross_margin_pct.toFixed(1)}%` : '—', sub: bench?.gross_margin_median != null ? `Bench: ${(bench.gross_margin_median * 100).toFixed(1)}%` : kpis.gross_margin_status || undefined },
    { label: 'LTV/CAC', value: kpis.ltv_cac_ratio != null ? `${kpis.ltv_cac_ratio.toFixed(1)}x` : (ltvCac != null ? `${ltvCac.toFixed(1)}x` : '—'), sub: kpis.ltv_cac_status || undefined },
    { label: 'Survie 12m', value: mc?.proba_survie_12m != null ? `${(mc.proba_survie_12m * 100).toFixed(0)}%` : '—', sub: 'Monte Carlo ×1000' },
    { label: 'Breakeven', value: kpis.breakeven_months != null ? (kpis.breakeven_months === 0 ? 'Atteint ✓' : `${kpis.breakeven_months} mois`) : '—' },
    { label: 'Phase', value: phaseLabel },
  ] : [
    { label: 'Autonomie', value: runwayValue, sub: burnAlert, hint: 'Temps restant avant manque de trésorerie' },
    { label: 'Dépenses/mois', value: kpis.burn_net != null ? fmt(Math.abs(kpis.burn_net), ' TND') : '—', hint: 'Ce que vous dépensez chaque mois' },
    { label: 'Revenus/mois', value: fmt(kpis.mrr, ' TND'), hint: 'Revenus récurrents mensuels' },
    { label: 'Marge', value: kpis.gross_margin_pct != null ? `${kpis.gross_margin_pct.toFixed(0)}%` : '—', hint: 'Ce que vous gardez sur chaque vente' },
    { label: 'Rentabilité client', value: kpis.ltv_cac_ratio != null ? `${kpis.ltv_cac_ratio.toFixed(1)}x` : (ltvCac != null ? `${ltvCac.toFixed(1)}x` : '—'), hint: 'Ratio valeur client / coût acquisition (>3 = bon)' },
    { label: 'Chances survie 1 an', value: mc?.proba_survie_12m != null ? `${(mc.proba_survie_12m * 100).toFixed(0)}%` : '—', hint: 'Probabilité de tenir 12 mois (simulation)' },
    { label: 'Équilibre', value: kpis.breakeven_months != null ? (kpis.breakeven_months === 0 ? 'Atteint ✓' : `Dans ${kpis.breakeven_months} mois`) : '—', hint: 'Quand revenus = dépenses' },
    { label: 'Stade', value: phaseLabel, hint: 'Votre phase de développement' },
  ]

  const filtered = cards.filter(c => c.value !== '—')

  return (
    <div className="kpi-grid">
      {filtered.map(c => (
        <div className="kpi-card" key={c.label}>
          <div className="kpi-label">{c.label}</div>
          <div className="kpi-value">{c.value}</div>
          {c.sub && <div className="kpi-sub">{c.sub}</div>}
          {!expertMode && c.hint && <div className="kpi-sub" style={{ color: '#94a3b8', fontSize: '.7rem', marginTop: 2 }}>{c.hint}</div>}
        </div>
      ))}
    </div>
  )
}
