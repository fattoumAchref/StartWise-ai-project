'use client'
import dynamic from 'next/dynamic'
import type { ComponentType } from 'react'
import type { Scenarios, MonteCarloResult, SeasonalityResult, Benchmark, BenchmarkExtra, KPIs } from '@/lib/types'

/** dynamic() drops Plotly prop types — widen so `data` / `layout` typecheck */
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false }) as ComponentType<Record<string, unknown>>

const MONTH_NAMES = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
const fmt = (v?: number | null) => v != null ? v.toLocaleString('fr-FR', { maximumFractionDigits: 0 }) : '—'

// ── Scenarios chart ──────────────────────────────────────────────────────────

export function ScenariosChart({ scenarios }: { scenarios?: Scenarios }) {
  if (!scenarios) return null
  const labels = ['Pessimiste', 'Réaliste', 'Optimiste']
  const keys = ['pessimiste', 'realiste', 'optimiste'] as const
  const revenues = keys.map(k => scenarios[k]?.revenue_12m ?? 0)
  const runways = keys.map(k => scenarios[k]?.runway_months ?? 0)
  const colors = ['#ef4444', '#3b82f6', '#22c55e']

  return (
    <Plot
      data={[
        { type: 'bar', name: 'Revenu 12m (TND)', x: labels, y: revenues, marker: { color: colors }, yaxis: 'y' },
        { type: 'scatter', mode: 'lines+markers', name: 'Runway (mois)', x: labels, y: runways, yaxis: 'y2', line: { color: '#f59e0b', width: 2 }, marker: { size: 8 } },
      ]}
      layout={{
        height: 260,
        margin: { t: 20, b: 30, l: 50, r: 50 },
        legend: { orientation: 'h', y: -0.25 },
        yaxis: { title: { text: 'Revenu (TND)', font: { size: 11 } } },
        yaxis2: { title: { text: 'Runway (mois)', font: { size: 11 } }, overlaying: 'y', side: 'right' },
        paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%' }}
    />
  )
}

// ── Monte Carlo chart ────────────────────────────────────────────────────────

export function MonteCarloChart({ mc }: { mc?: MonteCarloResult }) {
  if (!mc) return null
  const vals = [mc.p10, mc.p50, mc.p90].filter(v => v != null) as number[]
  if (vals.length === 0) return null

  return (
    <Plot
      data={[{
        type: 'bar',
        x: ['P10 (pessimiste)', 'P50 (médiane)', 'P90 (optimiste)'],
        y: vals,
        marker: { color: ['#ef4444', '#3b82f6', '#22c55e'] },
        text: vals.map(v => `${v.toFixed(1)}m`),
        textposition: 'outside',
      }]}
      layout={{
        height: 220,
        margin: { t: 20, b: 40, l: 50, r: 20 },
        yaxis: { title: { text: 'Mois de runway' } },
        paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%' }}
    />
  )
}

// ── Seasonality chart (full detail like Streamlit) ───────────────────────────

export function SeasonalityChart({ seasonality: seas }: { seasonality?: SeasonalityResult }) {
  if (!seas) return <p style={{ color: '#9ca3af', fontSize: '.83rem' }}>Données de saisonnalité non disponibles.</p>

  const levelStyle: Record<string, { bg: string; border: string; color: string; label: string }> = {
    HIGH:     { bg: '#e8f5e9', border: '#2e7d32', color: '#2e7d32', label: 'Confiance élevée — données client solides' },
    MEDIUM:   { bg: '#fff8e1', border: '#f57f17', color: '#f57f17', label: 'Confiance moyenne' },
    LOW:      { bg: '#fff3e0', border: '#e65100', color: '#e65100', label: 'Confiance faible' },
    VERY_LOW: { bg: '#fce4ec', border: '#c62828', color: '#c62828', label: 'Confiance très faible' },
    NONE:     { bg: '#f3e5f5', border: '#6a1b9a', color: '#6a1b9a', label: 'Estimation sectorielle pure (aucune donnée historique)' },
  }
  const style = levelStyle[seas.confidence_level || 'NONE'] || levelStyle['NONE']

  return (
    <div>
      {/* Confidence banner */}
      <div style={{
        background: style.bg, borderLeft: `4px solid ${style.border}`,
        padding: '10px 14px', borderRadius: 4, marginBottom: 12,
      }}>
        <div style={{ color: style.color, fontWeight: 700, fontSize: '.85rem' }}>{style.label}</div>
        {seas.reasoning && <div style={{ color: '#333', fontSize: '.81rem', marginTop: 4 }}>{seas.reasoning}</div>}
      </div>

      {/* KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '.5rem', marginBottom: 12 }}>
        {[
          { label: 'Tendance', value: seas.trend_direction || '—', sub: seas.trend_monthly_pct != null ? `${seas.trend_monthly_pct > 0 ? '+' : ''}${(seas.trend_monthly_pct * 100).toFixed(1)}%/mois` : undefined },
          { label: 'Forecast 3m', value: `${fmt(seas.forecast_3m)} TND` },
          { label: 'Forecast 6m', value: `${fmt(seas.forecast_6m)} TND` },
          { label: 'Forecast 12m', value: `${fmt(seas.forecast_12m)} TND`, sub: seas.forecast_12m_lower != null && seas.forecast_12m_upper != null ? `[${fmt(seas.forecast_12m_lower)} – ${fmt(seas.forecast_12m_upper)}]` : undefined },
        ].map(c => (
          <div key={c.label} style={{ background: '#f9fafb', borderRadius: 8, padding: '.5rem .75rem', border: '1px solid #e5e7eb' }}>
            <div style={{ fontSize: '.72rem', color: '#6b7280' }}>{c.label}</div>
            <div style={{ fontWeight: 700, fontSize: '.9rem', color: '#111827', marginTop: 2 }}>{c.value}</div>
            {c.sub && <div style={{ fontSize: '.72rem', color: '#9ca3af' }}>{c.sub}</div>}
          </div>
        ))}
      </div>

      {/* Sector seasonality index — 12 months bar chart */}
      {seas.sector_index && seas.sector_index.length === 12 && (
        <Plot
          data={[{
            type: 'bar',
            x: MONTH_NAMES,
            y: seas.sector_index,
            marker: {
              color: seas.sector_index.map(v =>
                v >= 1.05 ? '#4caf50' : v <= 0.88 ? '#f44336' : '#2196f3'
              ),
            },
            text: seas.sector_index.map(v => `${v.toFixed(2)}x`),
            textposition: 'outside',
          }]}
          layout={{
            title: { text: 'Indice de saisonnalité sectorielle (1.0 = moyenne)', font: { size: 13 } },
            height: 280,
            margin: { t: 40, b: 30, l: 40, r: 20 },
            yaxis: { range: [0.5, Math.max(...seas.sector_index) * 1.18], gridcolor: '#f0f0f0' },
            shapes: [{ type: 'line', x0: -0.5, x1: 11.5, y0: 1, y1: 1, line: { color: '#aaa', dash: 'dash', width: 1 } }],
            paper_bgcolor: 'transparent', plot_bgcolor: '#fafafa',
            showlegend: false,
          }}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: '100%' }}
        />
      )}

      {/* Anomalies + market context */}
      {seas.anomaly_months && seas.anomaly_months.length > 0 && (
        <div style={{ background: '#fff3e0', border: '1px solid #ffcc80', borderRadius: 6, padding: '8px 12px', marginTop: 8, fontSize: '.82rem', color: '#e65100' }}>
          ⚠ Anomalies détectées en {seas.anomaly_months.map(m => MONTH_NAMES[m - 1]).join(', ')} — revenus s'écartant du schéma sectoriel.
        </div>
      )}
      {seas.market_context && (
        <div style={{ fontSize: '.78rem', color: '#6b7280', marginTop: 6 }}>
          <strong>Contexte marché :</strong> {seas.market_context}
        </div>
      )}
      {seas.blend_weight_client != null && (
        <div style={{ fontSize: '.75rem', color: '#9ca3af', marginTop: 4 }}>
          Signal : {(seas.blend_weight_client * 100).toFixed(0)}% données client · {((1 - seas.blend_weight_client) * 100).toFixed(0)}% benchmarks sectoriels
        </div>
      )}
    </div>
  )
}

// ── Benchmark comparison chart ────────────────────────────────────────────────

export function BenchmarkChart({ bench, extra, kpis, ctx }: {
  bench?: Benchmark
  extra?: BenchmarkExtra
  kpis?: KPIs
  ctx?: { churn_rate?: number; secteur?: string }
}) {
  if (!bench) return null

  const labels: string[] = []
  const founderVals: number[] = []
  const sectorVals: number[] = []
  const colors: string[] = []

  if (bench.gross_margin_median != null && kpis?.gross_margin_pct != null) {
    labels.push('Marge brute (%)')
    founderVals.push(kpis.gross_margin_pct)
    sectorVals.push(bench.gross_margin_median * 100)
    colors.push(kpis.gross_margin_pct >= bench.gross_margin_median * 100 ? '#22c55e' : '#ef4444')
  }

  if (bench.churn_median != null && ctx?.churn_rate != null) {
    labels.push('Churn mensuel (%)')
    founderVals.push(ctx.churn_rate * 100)
    sectorVals.push(bench.churn_median * 100)
    colors.push(ctx.churn_rate <= bench.churn_median ? '#22c55e' : '#ef4444')
  }

  if (extra?.ltv_cac_ratio != null && kpis?.ltv_cac_ratio != null) {
    labels.push('LTV/CAC (x)')
    founderVals.push(kpis.ltv_cac_ratio)
    sectorVals.push(extra.ltv_cac_ratio)
    colors.push(kpis.ltv_cac_ratio >= extra.ltv_cac_ratio ? '#22c55e' : '#ef4444')
  }

  // CAC comparison — only show if both sides available and in plausible range
  if (bench.cac_median != null && kpis?.cac != null && bench.cac_median > 0) {
    labels.push('CAC (devise)')
    founderVals.push(kpis.cac)
    sectorVals.push(bench.cac_median)
    colors.push(kpis.cac <= bench.cac_median ? '#22c55e' : '#ef4444')
  }

  // LTV comparison
  if (bench.ltv_median != null && kpis?.ltv != null && bench.ltv_median > 0) {
    labels.push('LTV (devise)')
    founderVals.push(kpis.ltv)
    sectorVals.push(bench.ltv_median)
    colors.push(kpis.ltv >= bench.ltv_median ? '#22c55e' : '#ef4444')
  }

  if (labels.length === 0) return null

  return (
    <Plot
      data={[
        {
          type: 'bar', name: 'Votre startup',
          x: labels, y: founderVals,
          marker: { color: colors },
          text: founderVals.map(v => v.toFixed(1)),
          textposition: 'outside',
        },
        {
          type: 'bar', name: 'Médiane secteur',
          x: labels, y: sectorVals,
          marker: { color: '#94a3b8' },
          text: sectorVals.map(v => v.toFixed(1)),
          textposition: 'outside',
        },
      ]}
      layout={{
        barmode: 'group',
        height: 250,
        margin: { t: 20, b: 60, l: 40, r: 20 },
        legend: { orientation: 'h', y: -0.35 },
        paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%' }}
    />
  )
}
