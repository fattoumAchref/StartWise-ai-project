'use client'

/**
 * CrossAgentPanel
 * ===============
 * Shows the live A2A agent network — who said what to whom.
 *
 * Reads from /api/a2a/network which returns:
 *   agents: { finance_agent: {...}, investment_agent: {...}, risk_agent: {...},
 *             marketing_agent: {...}, legal_agent: {...} }
 *   conversation_log: [{ from, to, type, timestamp, confidence }]
 *
 * Used on every agent page as a compact "Agent Network" panel below the
 * main content, giving users visibility into cross-agent communication.
 */

import { useState, useEffect, useCallback } from 'react'
import { getA2ANetwork } from '@/services/cfo'
import {
  DollarSign, Building2, TriangleAlert, Megaphone, Scale,
  ArrowRightLeft, RefreshCw, Wifi, WifiOff,
} from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

interface AgentState { [key: string]: string }

interface ConvEntry {
  direction:  string
  from:       string
  to:         string[]
  type:       string
  message_id: string
  timestamp:  string
  confidence: number
}

interface NetworkData {
  available:        boolean
  agents:           Record<string, AgentState>
  conversation_log: ConvEntry[]
  agent_ids:        string[]
}

interface Props {
  /** Which agent page is this panel on — highlighted differently */
  currentAgent?: string
  /** Auto-refresh interval (ms). 0 = no auto-refresh. Default 8000. */
  refreshInterval?: number
}

// ── Agent metadata ────────────────────────────────────────────────────────────

const AGENT_META: Record<string, {
  label: string
  icon: React.FC<{ style?: React.CSSProperties }>
  color: string
  bg: string
  border: string
}> = {
  finance_agent: {
    label: 'Finance',
    icon: DollarSign,
    color: '#16a34a',
    bg: '#f0fdf4',
    border: '#86efac',
  },
  investment_agent: {
    label: 'Investment',
    icon: Building2,
    color: '#6366f1',
    bg: '#eef2ff',
    border: '#c7d2fe',
  },
  risk_agent: {
    label: 'Risk',
    icon: TriangleAlert,
    color: '#dc2626',
    bg: '#fef2f2',
    border: '#fca5a5',
  },
  marketing_agent: {
    label: 'Marketing',
    icon: Megaphone,
    color: '#d97706',
    bg: '#fffbeb',
    border: '#fde68a',
  },
  legal_agent: {
    label: 'Legal',
    icon: Scale,
    color: '#0891b2',
    bg: '#ecfeff',
    border: '#a5f3fc',
  },
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function agentHasData(state: AgentState): boolean {
  return Object.keys(state).length > 0 && !!state.last_updated
}

function primarySignal(agentId: string, state: AgentState): string | null {
  // Return the most meaningful single signal for the compact card
  if (agentId === 'finance_agent') {
    const phase = state.financial_context_phase || state.startup_phase
    if (phase) return `Phase: ${phase}`
    return null
  }
  if (agentId === 'investment_agent') {
    if (state.investment_rating) return state.investment_rating
    if (state.investment_agent_rating) return state.investment_agent_rating
    return null
  }
  if (agentId === 'risk_agent') {
    if (state.risk_level) return state.risk_level
    if (state.risk_agent_level) return state.risk_agent_level
    return null
  }
  if (agentId === 'marketing_agent') {
    if (state.financial_context_sector) return `Secteur: ${state.financial_context_sector}`
    return null
  }
  if (agentId === 'legal_agent') {
    if (state.legal_agent_level) return state.legal_agent_level
    if (state.startup_sector) return `Secteur: ${state.startup_sector}`
    return null
  }
  return null
}

function fmtTime(iso: string): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return '' }
}

function shortType(type: string): string {
  return type
    .replace('financial_analysis', 'fin.analysis')
    .replace('investment.recommendation', 'invest.rec')
    .replace('investment.clarification_request', 'invest.clarif?')
    .replace('finance.clarification_response', 'fin.clarif→')
    .replace('risk.assessment', 'risk.assess')
    .replace('marketing.analysis', 'mktg.analysis')
    .replace('legal.assessment', 'legal.assess')
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function CrossAgentPanel({ currentAgent, refreshInterval = 8000 }: Props) {
  const [network, setNetwork]     = useState<NetworkData | null>(null)
  const [loading, setLoading]     = useState(true)
  const [showLog, setShowLog]     = useState(false)

  const fetchNetwork = useCallback(async () => {
    try {
      const data = await getA2ANetwork()
      setNetwork(data)
    } catch { /* silent */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    fetchNetwork()
    if (refreshInterval > 0) {
      const id = setInterval(fetchNetwork, refreshInterval)
      return () => clearInterval(id)
    }
  }, [fetchNetwork, refreshInterval])

  if (loading) return null
  if (!network?.available) {
    return (
      <div style={{
        marginTop: '2rem',
        border: '1px solid #e5e7eb',
        borderRadius: 10,
        padding: '.75rem 1rem',
        display: 'flex', alignItems: 'center', gap: '.5rem',
        fontSize: '.76rem', color: '#9ca3af',
      }}>
        <WifiOff style={{ width: 13, height: 13 }} />
        Réseau A2A non disponible (Redis requis)
      </div>
    )
  }

  const agentIds = network.agent_ids || Object.keys(AGENT_META)
  const log      = network.conversation_log || []

  return (
    <div style={{ marginTop: '2rem' }}>
      {/* Section header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '.5rem',
        marginBottom: '1rem',
      }}>
        <ArrowRightLeft style={{ width: 15, height: 15, color: '#6366f1' }} />
        <span style={{ fontSize: '.82rem', fontWeight: 600, color: '#374151' }}>
          Réseau A2A — Communication inter-agents
        </span>
        <span style={{
          marginLeft: 'auto',
          display: 'flex', alignItems: 'center', gap: '.3rem',
          fontSize: '.7rem', color: '#10b981',
        }}>
          <Wifi style={{ width: 11, height: 11 }} />
          actif
        </span>
        <button
          onClick={fetchNetwork}
          style={{
            background: 'none', border: 'none', cursor: 'pointer', padding: 2,
            color: '#9ca3af',
          }}
          title="Rafraîchir"
        >
          <RefreshCw style={{ width: 12, height: 12 }} />
        </button>
      </div>

      {/* Agent status grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))',
        gap: '.6rem',
        marginBottom: '1rem',
      }}>
        {agentIds.map(agentId => {
          const meta    = AGENT_META[agentId]
          if (!meta) return null
          const state   = network.agents[agentId] || {}
          const hasData = agentHasData(state)
          const signal  = primarySignal(agentId, state)
          const isCurrent = agentId === currentAgent
          const Icon    = meta.icon

          return (
            <div key={agentId} style={{
              border: isCurrent
                ? `2px solid ${meta.border}`
                : `1.5px solid ${hasData ? meta.border : '#e5e7eb'}`,
              borderRadius: 8,
              padding: '.6rem .75rem',
              background: hasData ? meta.bg : '#fafafa',
              opacity: hasData ? 1 : 0.6,
              position: 'relative',
            }}>
              {/* Active dot */}
              {hasData && (
                <span style={{
                  position: 'absolute', top: 6, right: 6,
                  width: 6, height: 6, borderRadius: '50%',
                  background: meta.color,
                }} />
              )}

              <div style={{ display: 'flex', alignItems: 'center', gap: '.4rem', marginBottom: '.3rem' }}>
                <Icon style={{ width: 13, height: 13, color: hasData ? meta.color : '#9ca3af' }} />
                <span style={{
                  fontSize: '.72rem', fontWeight: 600,
                  color: hasData ? meta.color : '#9ca3af',
                }}>
                  {meta.label}
                </span>
              </div>

              {signal ? (
                <div style={{ fontSize: '.68rem', color: '#374151', fontWeight: 500 }}>
                  {signal}
                </div>
              ) : (
                <div style={{ fontSize: '.66rem', color: '#9ca3af' }}>
                  {hasData ? 'actif' : 'en attente'}
                </div>
              )}

              {state.last_updated && (
                <div style={{ fontSize: '.62rem', color: '#9ca3af', marginTop: '.2rem' }}>
                  {fmtTime(state.last_updated)}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Conversation log toggle */}
      {log.length > 0 && (
        <div>
          <button
            onClick={() => setShowLog(v => !v)}
            style={{
              background: 'none', border: '1px solid #e5e7eb',
              borderRadius: 6, padding: '.3rem .7rem',
              fontSize: '.72rem', color: '#6b7280', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '.35rem',
            }}
          >
            <ArrowRightLeft style={{ width: 11, height: 11 }} />
            {showLog ? 'Masquer' : 'Voir'} le journal A2A ({log.length} messages)
          </button>

          {showLog && (
            <div style={{
              marginTop: '.6rem',
              border: '1px solid #e5e7eb',
              borderRadius: 8,
              overflow: 'hidden',
              fontSize: '.71rem',
            }}>
              {/* Header row */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: '90px 1fr 1fr 90px 50px',
                gap: '.5rem',
                padding: '.4rem .75rem',
                background: '#f9fafb',
                fontWeight: 600, color: '#6b7280',
                borderBottom: '1px solid #e5e7eb',
              }}>
                <span>Heure</span>
                <span>De</span>
                <span>Type</span>
                <span>Vers</span>
                <span>Conf.</span>
              </div>

              {log.slice(0, 20).map((entry, i) => {
                const fromMeta = AGENT_META[entry.from]
                return (
                  <div key={i} style={{
                    display: 'grid',
                    gridTemplateColumns: '90px 1fr 1fr 90px 50px',
                    gap: '.5rem',
                    padding: '.35rem .75rem',
                    background: i % 2 === 0 ? '#fff' : '#fafafa',
                    borderBottom: i < log.length - 1 ? '1px solid #f3f4f6' : 'none',
                    alignItems: 'center',
                  }}>
                    <span style={{ color: '#9ca3af' }}>{fmtTime(entry.timestamp)}</span>
                    <span style={{ color: fromMeta?.color || '#374151', fontWeight: 500 }}>
                      {fromMeta?.label || entry.from}
                    </span>
                    <span style={{
                      color: '#374151',
                      background: '#f3f4f6',
                      borderRadius: 4, padding: '1px 5px',
                      display: 'inline-block',
                    }}>
                      {shortType(entry.type)}
                    </span>
                    <span style={{ color: '#6b7280' }}>
                      {Array.isArray(entry.to)
                        ? entry.to.map(t => AGENT_META[t]?.label || t).join(', ')
                        : entry.to}
                    </span>
                    <span style={{ color: '#9ca3af' }}>
                      {entry.confidence ? `${Math.round(Number(entry.confidence) * 100)}%` : '—'}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
