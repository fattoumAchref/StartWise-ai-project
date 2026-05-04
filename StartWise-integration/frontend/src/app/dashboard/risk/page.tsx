'use client'
import { useState, useEffect } from 'react'
import {
  TriangleAlert, ShieldAlert, ShieldCheck, ShieldQuestion,
  Loader2, Search, Building2, Globe, AlertTriangle, Users,
  TrendingDown, Scale, DollarSign, Megaphone,
} from 'lucide-react'
import { getA2AState } from '@/services/cfo'

// ─── Types ───────────────────────────────────────────────────────────────────

interface SimilarCase {
  startup:     string | null
  sector:      string | null
  country:     string | null
  funding:     string | null
  cause:       string[]
  description: string
  score:       number
}

interface RiskPayload {
  global_risk:     number
  monte_carlo:     { risk: number; ci: [number, number]; conf: number }
  conflict_score:  number
  uncertainty:     number
  rag:             { risk: number; confidence: number; avg_similarity: number; similar_cases: SimilarCase[] }
  sector_score:    { sector: string | null; risk: number; confidence: number }
  agent_risks:     { finance: number; marketing: number; legal: number; investissement: number }
  metrics:         { stability: number; ablation: number[]; conflict_density: number; signal_labels: string[] }
  conflicts:       { conflict: string; agents: string[]; severity: number }[]
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function riskLevel(score: number): { label: string; color: string; bg: string; border: string } {
  if (score >= 0.75) return { label: 'CRITICAL', color: '#dc2626', bg: '#fef2f2', border: '#fca5a5' }
  if (score >= 0.5)  return { label: 'HIGH',     color: '#ea580c', bg: '#fff7ed', border: '#fdba74' }
  if (score >= 0.25) return { label: 'MEDIUM',   color: '#ca8a04', bg: '#fefce8', border: '#fde047' }
  return                     { label: 'LOW',      color: '#16a34a', bg: '#f0fdf4', border: '#86efac' }
}

function pct(v: number) { return `${Math.round(v * 100)}%` }

function makeId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    const bytes = new Uint8Array(16)
    crypto.getRandomValues(bytes)
    bytes[6] = (bytes[6] & 0x0f) | 0x40
    bytes[8] = (bytes[8] & 0x3f) | 0x80
    const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0'))
    return `${hex[0]}${hex[1]}${hex[2]}${hex[3]}-${hex[4]}${hex[5]}-${hex[6]}${hex[7]}-${hex[8]}${hex[9]}-${hex[10]}${hex[11]}${hex[12]}${hex[13]}${hex[14]}${hex[15]}`
  }
  return `${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}`
}

function RiskBar({ label, value, icon: Icon }: { label: string; value: number; icon: React.ElementType }) {
  const lv = riskLevel(value)
  return (
    <div style={{ marginBottom: '0.75rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.3rem' }}>
        <Icon style={{ width: 13, height: 13, color: lv.color, flexShrink: 0 }} />
        <span style={{ fontSize: '0.78rem', color: 'var(--foreground)', fontWeight: 500 }}>{label}</span>
        <span style={{ marginLeft: 'auto', fontSize: '0.75rem', fontWeight: 700, color: lv.color }}>{pct(value)}</span>
      </div>
      <div style={{ height: 6, borderRadius: 99, background: 'var(--muted,#e5e7eb)', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: pct(value), background: lv.color, borderRadius: 99, transition: 'width .4s ease' }} />
      </div>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function RiskPage() {
  // ── Form state ──
  const [description, setDescription] = useState('')
  const [sector,      setSector]       = useState('')
  const [country,     setCountry]      = useState('Tunisia')

  // ── Analysis state ──
  const [loading,  setLoading]  = useState(false)
  const [result,   setResult]   = useState<RiskPayload | null>(null)
  const [error,    setError]    = useState<string | null>(null)

  // ── A2A secondary state (finance-triggered) ──
  const [a2aRisk, setA2aRisk] = useState<any>(null)

  // Pre-fill from ideation localStorage
  useEffect(() => {
    const summary = localStorage.getItem('startwise_summary') || ''
    const idea    = localStorage.getItem('startwise_business_idea') || ''
    if (idea)    setDescription(idea)
    else if (summary) {
      // Extract first ~300 chars as description
      const clean = summary.replace(/^#+.*$/gm, '').replace(/\n+/g, ' ').trim().slice(0, 300)
      setDescription(clean)
    }
    // Try to pull sector from financial data
    try {
      const fd = localStorage.getItem('startwise_financial_data')
      if (fd) {
        const parsed = JSON.parse(fd)
        if (parsed?.financial_context?.sector) setSector(parsed.financial_context.sector)
      }
    } catch { /* ignore */ }
  }, [])

  // Background A2A poll (secondary data, non-blocking)
  useEffect(() => {
    getA2AState().then(data => {
      if (data?.risk_level) setA2aRisk(data)
    }).catch(() => {})
  }, [])

  // ── Run analysis ──
  async function runAnalysis() {
    if (!description.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const taskId = makeId()
      const resp = await fetch('http://localhost:8003/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jsonrpc: '2.0',
          id: makeId(),
          method: 'tasks/send',
          params: {
            id: taskId,
            message: {
              role: 'user',
              parts: [{
                type: 'data',
                data: {
                  description: description.trim(),
                  sector:      sector.trim() || undefined,
                  country:     country.trim() || 'Tunisia',
                  agent_outputs: [],
                },
              }],
            },
          },
        }),
      })

      const json = await resp.json()

      if (json.error) {
        setError(json.error.message || 'Risk agent returned an error')
        return
      }

      // result.artifacts[0].parts[0].data
      const taskResult = json.result
      if (taskResult?.status?.state === 'failed') {
        const errPart = taskResult?.artifacts?.[0]?.parts?.[0]
        setError(errPart?.text || 'Risk agent failed')
        return
      }

      const artifacts = taskResult?.artifacts
      if (!artifacts?.length) { setError('No artifacts returned'); return }

      const part = artifacts[0]?.parts?.[0]
      if (!part?.data && part?.text) { setError(part.text); return }
      const payload: RiskPayload = part?.data
      setResult(payload)
    } catch (e: any) {
      setError(e?.message || 'Could not reach risk agent — make sure it is running on port 8003')
    } finally {
      setLoading(false)
    }
  }

  // ─── Render ───────────────────────────────────────────────────────────────

  const lv = result ? riskLevel(result.global_risk) : null

  return (
    <div style={{ padding: '2rem', maxWidth: 900, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.75rem' }}>
        <TriangleAlert style={{ width: 22, height: 22, color: '#ef4444', flexShrink: 0 }} />
        <div>
          <h1 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--foreground)', margin: 0 }}>
            Risk Agent
          </h1>
          <p style={{ fontSize: '0.78rem', color: '#6b7280', margin: 0, marginTop: 2 }}>
            Multi-dimensional risk analysis powered by FAISS RAG on 500+ failed startup cases
          </p>
        </div>
      </div>

      {/* Input card */}
      <div style={{
        border: '1.5px solid var(--border,#e5e7eb)', borderRadius: 12,
        padding: '1.25rem', marginBottom: '1.5rem',
        background: 'var(--card,#fff)',
      }}>
        <p style={{ fontSize: '0.8rem', fontWeight: 600, color: '#6b7280', marginBottom: '0.9rem', marginTop: 0 }}>
          STARTUP DESCRIPTION
        </p>

        <textarea
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="Describe your startup idea, product, target market…"
          rows={4}
          style={{
            width: '100%', boxSizing: 'border-box',
            border: '1.5px solid var(--border,#e5e7eb)', borderRadius: 8,
            padding: '0.65rem 0.85rem', fontSize: '0.85rem',
            color: 'var(--foreground)', background: 'var(--background)',
            resize: 'vertical', outline: 'none', fontFamily: 'inherit',
          }}
        />

        <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 160 }}>
            <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block', marginBottom: '0.3rem' }}>
              Sector
            </label>
            <input
              value={sector}
              onChange={e => setSector(e.target.value)}
              placeholder="e.g. SaaS, FinTech, E-commerce"
              style={{
                width: '100%', boxSizing: 'border-box',
                border: '1.5px solid var(--border,#e5e7eb)', borderRadius: 8,
                padding: '0.5rem 0.75rem', fontSize: '0.83rem',
                color: 'var(--foreground)', background: 'var(--background)', outline: 'none',
              }}
            />
          </div>
          <div style={{ flex: 1, minWidth: 160 }}>
            <label style={{ fontSize: '0.75rem', color: '#6b7280', display: 'block', marginBottom: '0.3rem' }}>
              Country
            </label>
            <input
              value={country}
              onChange={e => setCountry(e.target.value)}
              placeholder="e.g. Tunisia, France, USA"
              style={{
                width: '100%', boxSizing: 'border-box',
                border: '1.5px solid var(--border,#e5e7eb)', borderRadius: 8,
                padding: '0.5rem 0.75rem', fontSize: '0.83rem',
                color: 'var(--foreground)', background: 'var(--background)', outline: 'none',
              }}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end' }}>
            <button
              onClick={runAnalysis}
              disabled={loading || !description.trim()}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.45rem',
                padding: '0.55rem 1.25rem', borderRadius: 8,
                background: loading || !description.trim() ? '#9ca3af' : '#ef4444',
                color: '#fff', border: 'none', cursor: loading || !description.trim() ? 'not-allowed' : 'pointer',
                fontSize: '0.85rem', fontWeight: 600, transition: 'background .2s',
              }}
            >
              {loading
                ? <><Loader2 style={{ width: 14, height: 14 }} className="animate-spin" /> Analyzing…</>
                : <><Search style={{ width: 14, height: 14 }} /> Analyze Risk</>
              }
            </button>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          border: '1.5px solid #fca5a5', borderRadius: 10,
          padding: '0.9rem 1.1rem', background: '#fef2f2',
          marginBottom: '1.25rem', fontSize: '0.85rem', color: '#dc2626',
        }}>
          {error}
        </div>
      )}

      {/* Results */}
      {result && lv && (
        <>
          {/* Global risk banner */}
          <div style={{
            border: `1.5px solid ${lv.border}`, borderRadius: 12,
            padding: '1rem 1.25rem', background: lv.bg,
            display: 'flex', alignItems: 'center', gap: '1rem',
            marginBottom: '1.25rem',
          }}>
            <div style={{
              width: 50, height: 50, borderRadius: '50%',
              background: '#fff', border: `2px solid ${lv.border}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}>
              {lv.label === 'LOW'
                ? <ShieldCheck style={{ width: 22, height: 22, color: lv.color }} />
                : lv.label === 'MEDIUM'
                  ? <ShieldQuestion style={{ width: 22, height: 22, color: lv.color }} />
                  : <ShieldAlert style={{ width: 22, height: 22, color: lv.color }} />
              }
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '0.74rem', color: '#6b7280', fontWeight: 500, marginBottom: 3 }}>
                Global risk score
              </div>
              <div style={{ fontSize: '1.35rem', fontWeight: 800, color: lv.color }}>
                {lv.label}
                <span style={{ fontSize: '0.88rem', fontWeight: 500, color: '#6b7280', marginLeft: '0.6rem' }}>
                  {pct(result.global_risk)} failure probability
                </span>
              </div>
            </div>
            <div style={{ textAlign: 'right', fontSize: '0.75rem', color: '#6b7280' }}>
              <div>{result.conflicts.length} conflict{result.conflicts.length !== 1 ? 's' : ''} detected</div>
              <div style={{ marginTop: 2 }}>{result.rag.similar_cases?.length ?? 0} similar failed startups</div>
            </div>
          </div>

          {/* Two-column: domains + monte carlo */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem', marginBottom: '1.25rem' }}>

            {/* Domain risks */}
            <div style={{
              border: '1.5px solid var(--border,#e5e7eb)', borderRadius: 12,
              padding: '1.1rem 1.25rem', background: 'var(--card,#fff)',
            }}>
              <p style={{ margin: '0 0 0.9rem', fontSize: '0.78rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Risk by Domain
              </p>
              <RiskBar label="Financial"   value={result.agent_risks.finance}        icon={DollarSign} />
              <RiskBar label="Marketing"   value={result.agent_risks.marketing}      icon={Megaphone} />
              <RiskBar label="Legal"       value={result.agent_risks.legal}          icon={Scale} />
              <RiskBar label="Investment"  value={result.agent_risks.investissement} icon={Building2} />
            </div>

            {/* Monte Carlo + supplementary */}
            <div style={{
              border: '1.5px solid var(--border,#e5e7eb)', borderRadius: 12,
              padding: '1.1rem 1.25rem', background: 'var(--card,#fff)',
            }}>
              <p style={{ margin: '0 0 0.9rem', fontSize: '0.78rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Simulation Metrics
              </p>
              {[
                { label: 'Monte Carlo failure rate', value: result.monte_carlo.risk, sub: `CI [${pct(result.monte_carlo.ci[0])} – ${pct(result.monte_carlo.ci[1])}]` },
                { label: 'Sector benchmark risk',    value: result.sector_score.risk, sub: result.sector_score.sector || 'Unknown sector' },
                { label: 'RAG similarity risk',      value: result.rag.risk, sub: `avg similarity ${Math.round(result.rag.avg_similarity * 100)}%` },
                { label: 'Uncertainty',              value: result.uncertainty, sub: `stability σ² ${result.metrics.stability.toFixed(4)}` },
              ].map(({ label, value, sub }) => {
                const lv2 = riskLevel(value)
                return (
                  <div key={label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.7rem' }}>
                    <div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--foreground)', fontWeight: 500 }}>{label}</div>
                      <div style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: 1 }}>{sub}</div>
                    </div>
                    <span style={{
                      fontSize: '0.78rem', fontWeight: 700, color: lv2.color,
                      background: lv2.bg, border: `1px solid ${lv2.border}`,
                      padding: '0.2rem 0.55rem', borderRadius: 99,
                    }}>
                      {pct(value)}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Similar failed startups (RAG) */}
          {(result.rag.similar_cases?.length ?? 0) > 0 && (
            <div style={{
              border: '1.5px solid var(--border,#e5e7eb)', borderRadius: 12,
              padding: '1.1rem 1.25rem', marginBottom: '1.25rem',
              background: 'var(--card,#fff)',
            }}>
              <p style={{ margin: '0 0 0.9rem', fontSize: '0.78rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Similar Failed Startups
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {result.rag.similar_cases.map((c, i) => (
                  <div key={i} style={{
                    border: '1px solid var(--border,#e5e7eb)', borderRadius: 8,
                    padding: '0.75rem 1rem', display: 'flex', gap: '0.9rem', alignItems: 'flex-start',
                  }}>
                    <div style={{
                      width: 36, height: 36, borderRadius: '50%',
                      background: '#fef2f2', border: '1px solid #fca5a5',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                    }}>
                      <TrendingDown style={{ width: 16, height: 16, color: '#ef4444' }} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--foreground)' }}>
                          {c.startup || 'Unknown startup'}
                        </span>
                        {c.sector && (
                          <span style={{ fontSize: '0.7rem', color: '#6b7280', background: 'var(--muted,#f3f4f6)', padding: '0.1rem 0.45rem', borderRadius: 99 }}>
                            {c.sector}
                          </span>
                        )}
                        {c.country && (
                          <span style={{ fontSize: '0.7rem', color: '#6b7280', display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Globe style={{ width: 10, height: 10 }} />{c.country}
                          </span>
                        )}
                        <span style={{
                          marginLeft: 'auto', fontSize: '0.7rem', fontWeight: 700,
                          color: riskLevel(c.score).color,
                        }}>
                          {Math.round(c.score * 100)}% similarity
                        </span>
                      </div>
                      {c.cause.length > 0 && (
                        <div style={{ marginTop: '0.35rem', display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                          {c.cause.slice(0, 4).map((cause, j) => (
                            <span key={j} style={{
                              fontSize: '0.68rem', padding: '0.15rem 0.45rem', borderRadius: 99,
                              background: '#fff7ed', border: '1px solid #fdba74', color: '#ea580c',
                            }}>
                              {cause}
                            </span>
                          ))}
                        </div>
                      )}
                      {c.funding && (
                        <div style={{ marginTop: '0.3rem', fontSize: '0.72rem', color: '#9ca3af' }}>
                          Funding: {c.funding}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Conflicts */}
          {result.conflicts.length > 0 && (
            <div style={{
              border: '1.5px solid #fde047', borderRadius: 12,
              padding: '1.1rem 1.25rem', marginBottom: '1.25rem',
              background: '#fefce8',
            }}>
              <p style={{ margin: '0 0 0.9rem', fontSize: '0.78rem', fontWeight: 700, color: '#ca8a04', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <AlertTriangle style={{ width: 13, height: 13 }} />
                Detected Conflicts
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                {result.conflicts.map((c, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.65rem' }}>
                    <span style={{
                      fontSize: '0.7rem', fontWeight: 700, color: riskLevel(c.severity).color,
                      background: riskLevel(c.severity).bg, border: `1px solid ${riskLevel(c.severity).border}`,
                      padding: '0.15rem 0.45rem', borderRadius: 99, flexShrink: 0, marginTop: 1,
                    }}>
                      {Math.round(c.severity * 100)}%
                    </span>
                    <div>
                      <p style={{ margin: 0, fontSize: '0.83rem', color: '#374151', fontWeight: 500 }}>{c.conflict}</p>
                      {c.agents.length > 0 && (
                        <p style={{ margin: '0.2rem 0 0', fontSize: '0.72rem', color: '#9ca3af' }}>
                          Agents: {c.agents.join(', ')}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Secondary: A2A finance-triggered risk data */}
      {a2aRisk?.risk_level && (
        <div style={{
          border: '1.5px dashed var(--border,#e5e7eb)', borderRadius: 12,
          padding: '1rem 1.25rem', marginTop: result ? '1rem' : 0,
          background: 'var(--muted,#f9fafb)',
        }}>
          <p style={{ margin: '0 0 0.5rem', fontSize: '0.75rem', fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Finance Agent Risk Signal
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{
              fontSize: '0.9rem', fontWeight: 700,
              color: riskLevel(parseFloat(a2aRisk.risk_score || '0.5') / 10).color,
            }}>
              {a2aRisk.risk_level}
            </span>
            {a2aRisk.risk_score && (
              <span style={{ fontSize: '0.8rem', color: '#6b7280' }}>
                Score {parseFloat(a2aRisk.risk_score).toFixed(1)} / 10
              </span>
            )}
          </div>
        </div>
      )}

      {/* Empty state — shown only if no result yet and no error */}
      {!result && !loading && !error && (
        <div style={{
          border: '1.5px dashed var(--border,#e5e7eb)', borderRadius: 12,
          padding: '2.5rem 2rem', textAlign: 'center',
          background: 'var(--card,#fff)',
        }}>
          <div style={{
            width: 48, height: 48, borderRadius: '50%',
            background: '#fef2f2', display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 1rem',
          }}>
            <Users style={{ width: 22, height: 22, color: '#ef4444' }} />
          </div>
          <p style={{ fontWeight: 600, color: 'var(--foreground)', marginBottom: '0.4rem', marginTop: 0 }}>
            Ready to analyze your startup risks
          </p>
          <p style={{ fontSize: '0.82rem', color: '#6b7280', lineHeight: 1.6, maxWidth: 460, margin: '0 auto' }}>
            Fill in your startup description above and click <strong>Analyze Risk</strong>.
            The risk agent uses a database of 500+ failed startups to find similar cases
            and compute financial, legal, marketing, and investment risks.
          </p>
        </div>
      )}

    </div>
  )
}
