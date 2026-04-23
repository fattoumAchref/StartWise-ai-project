'use client'
import { useState, useEffect, useRef, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import dynamic from 'next/dynamic'

import type { Message, AppState, A2AState, Analysis, Benchmark, BenchmarkExtra, FinancialContext, Validation } from '@/lib/types'
import { sendMessage, getState, getA2AState, toggleWhatif, downloadPdf, newConversation, restoreConversation, deleteConversation, uploadFile, resetSession, sendClarification } from '@/lib/api'
import Sidebar from '@/components/Sidebar'
import KPICards from '@/components/KPICards'
import { ScenariosChart, MonteCarloChart, SeasonalityChart, BenchmarkChart } from '@/components/Charts'
import A2APanel from '@/components/A2APanel'

// Dynamic import for plotly (no SSR)
dynamic(() => import('react-plotly.js'), { ssr: false })

// ── Helpers ──────────────────────────────────────────────────────────────────

const EXAMPLES = [
  'Mon burn rate est 8 000 TND/mois, j\'ai 45 000 TND en caisse et 3 200 TND de revenu mensuel.',
  'SaaS B2B, 12 clients à 800 TND/mois, churn 2%, marketing 1 500 TND/mois.',
  'Startup fintech, je cherche à lever 500k TND. Burn 15k/mois, cash 80k TND.',
]

const SECTIONS = [
  { id: 'scenarios', label: '📊 Scénarios' },
  { id: 'montecarlo', label: '🎲 Monte Carlo' },
  { id: 'seasonality', label: '📅 Saisonnalité' },
  { id: 'benchmarks', label: '🏆 Benchmarks' },
  { id: 'investment', label: '💼 Recommandation Investissement' },
]

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [whatifMode, setWhatifMode] = useState(false)
  const [openSections, setOpenSections] = useState<Set<string>>(new Set())
  const [analysis, setAnalysis] = useState<Analysis | undefined>()
  const [ctx, setCtx] = useState<FinancialContext | undefined>()
  const [validation, setValidation] = useState<Validation | undefined>()
  const [bench, setBench] = useState<Benchmark | undefined>()
  const [extra, setExtra] = useState<BenchmarkExtra | undefined>()
  const [benchText, setBenchText] = useState<string>('')
  const [conversations, setConversations] = useState<AppState['conversations']>([])
  const [a2a, setA2a] = useState<A2AState | undefined>()
  const [a2aPublishTime, setA2aPublishTime] = useState<number | undefined>()
  const [a2aElapsed, setA2aElapsed] = useState(0)

  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  // Load state on mount
  useEffect(() => {
    getState().then(data => {
      if (data.messages?.length) setMessages(data.messages)
      if (data.financial_context) setCtx(data.financial_context)
      if (data.validation) setValidation(data.validation)
      if (data.analysis) setAnalysis(data.analysis)
      if (data.bench) setBench(data.bench)
      if (data.bench_extra) setExtra(data.bench_extra)
      if (data.bench_text) setBenchText(data.bench_text)
      if (data.conversations) setConversations(data.conversations)
      if (data.a2a_publish_time) setA2aPublishTime(data.a2a_publish_time)
      if (data.whatif_mode) setWhatifMode(data.whatif_mode)
    }).catch(() => {})
  }, [])

  // A2A polling — only when a publish is pending
  const pollA2A = useCallback(async () => {
    try {
      const data = await getA2AState()
      setA2a(data)
    } catch { /* */ }
  }, [])

  useEffect(() => {
    if (!a2aPublishTime) return
    const TIMEOUT_S = 120  // stop polling after 2 minutes — agent either responded or stayed silent
    const interval = setInterval(() => {
      const elapsed = Math.floor(Date.now() / 1000 - a2aPublishTime)
      setA2aElapsed(elapsed)
      if (elapsed < TIMEOUT_S) {
        pollA2A()
      } else {
        // Agent silent or timed out — stop polling, clear pending state
        clearInterval(interval)
        setA2aPublishTime(undefined)
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [a2aPublishTime, pollA2A])

  // Section toggle
  const toggleSection = (id: string) => {
    setOpenSections(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  // Send message
  const handleSend = async (text?: string) => {
    const msg = (text ?? input).trim()
    if (!msg || loading) return
    setInput('')
    setLoading(true)
    setMessages(prev => [...prev, { role: 'user', content: msg }])

    try {
      const data = await sendMessage(msg)
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply || data.data_text || '' }])
      if (data.analysis) setAnalysis(data.analysis)
      if (data.financial_context) setCtx(data.financial_context)
      if (data.validation) setValidation(data.validation)
      if (data.bench) setBench(data.bench)
      if (data.bench_extra) setExtra(data.bench_extra)
      if (data.bench_text) setBenchText(data.bench_text)
      if (data.a2a_publish_time) {
        setA2aPublishTime(data.a2a_publish_time)
        setA2aElapsed(0)
      }
      // Auto-ouvrir toutes les sections quand l'analyse arrive
      if (data.analysis?.kpis) {
        setOpenSections(new Set(['scenarios', 'montecarlo', 'seasonality', 'benchmarks', 'investment']))
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Erreur lors de la requête.' }])
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const handleToggleWhatif = async () => {
    const data = await toggleWhatif()
    setWhatifMode(data.whatif_mode)
  }

  const handlePdf = async () => {
    try {
      const blob = await downloadPdf()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.style.display = 'none'
      a.href = url
      a.download = `startwise_${new Date().toISOString().slice(0, 10)}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      // Revoke after a delay so the browser finishes reading the blob
      setTimeout(() => URL.revokeObjectURL(url), 10000)
    } catch {
      alert('Erreur génération PDF — vérifiez que vous avez soumis vos données financières.')
    }
  }

  const handleNewConv = async () => {
    await newConversation()
    setMessages([]); setCtx(undefined); setValidation(undefined)
    setAnalysis(undefined); setBench(undefined); setExtra(undefined); setBenchText('')
    setA2a(undefined); setA2aPublishTime(undefined); setWhatifMode(false)
    setOpenSections(new Set())
    const updated = await getState()
    setConversations(updated.conversations || [])
  }

  const handleRestore = async (id: string) => {
    const data = await restoreConversation(id)
    setMessages(data.messages || [])
  }

  const handleReset = async () => {
    await resetSession()
    setMessages([]); setCtx(undefined); setValidation(undefined)
    setAnalysis(undefined); setBench(undefined); setExtra(undefined); setBenchText('')
    setA2a(undefined); setA2aPublishTime(undefined); setWhatifMode(false)
    setOpenSections(new Set()); setConversations([])
  }

  const handleUpload = (data: unknown) => {
    const d = data as { data_text?: string; analysis?: Analysis; financial_context?: FinancialContext; validation?: Validation; bench?: Benchmark }
    if (d.data_text) setMessages(prev => [...prev, { role: 'assistant', content: d.data_text! }])
    if (d.analysis) setAnalysis(d.analysis)
    if (d.financial_context) setCtx(d.financial_context)
    if (d.validation) setValidation(d.validation)
    if (d.bench) setBench(d.bench)
  }

  const hasAnalysis = !!(analysis?.kpis)
  const hasA2APending = !!a2aPublishTime && !a2a?.investment_rating

  return (
    <div className="layout">
      {/* Sidebar */}
      <Sidebar
        ctx={ctx}
        validation={validation}
        conversations={conversations}
        onNewConv={handleNewConv}
        onRestore={(_msgs) => {
          // reload full state after restore
          getState().then(d => {
            setMessages(d.messages || [])
            if (d.financial_context) setCtx(d.financial_context)
            if (d.validation) setValidation(d.validation)
            if (d.analysis) setAnalysis(d.analysis)
          })
        }}
        onReset={handleReset}
        onUpload={handleUpload}
      />

      {/* Main */}
      <div className="main">
        {/* Action bar — visible only when analysis is available */}
        {hasAnalysis && (
          <div className="action-bar">
            {SECTIONS.map(s => (
              <button
                key={s.id}
                className={`act-btn ${openSections.has(s.id) ? 'active' : ''}`}
                onClick={() => toggleSection(s.id)}
              >{s.label}</button>
            ))}
            <button className="act-btn" onClick={handlePdf}>📄 Télécharger PDF</button>
            <button
              className={`act-btn ${whatifMode ? 'active' : ''}`}
              onClick={handleToggleWhatif}
            >⚡ {whatifMode ? 'Mode What-If actif' : 'Simuler un scénario'}</button>
          </div>
        )}

        {/* Single scrollable region: chat + panels */}
        <div className="content-scroll">
        <div className="chat-area">
          {messages.length === 0 ? (
            <div className="chat-welcome">
              <div className="chat-title">StartWise CFO</div>
              <div className="chat-sub">
                Décrivez votre startup en langage naturel — analyse financière complète en quelques secondes.
              </div>
              <div className="chips">
                {EXAMPLES.map(e => (
                  <button key={e} className="chip" onClick={() => handleSend(e)}>
                    {e.slice(0, 55)}…
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, i) => (
              <div key={i} className={`msg msg-${m.role}`}>
                <div className={`bubble bubble-${m.role}`}>
                  {m.role === 'assistant' ? (
                    <div className="md">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                    </div>
                  ) : m.content}
                </div>
              </div>
            ))
          )}
          {loading && (
            <div className="msg msg-assistant">
              <div className="bubble bubble-assistant" style={{ color: '#9ca3af' }}>
                <span className="spinner" style={{ marginRight: 8 }} />Analyse en cours…
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Expandable panels */}
        {hasAnalysis && (
          <div className="panels">
            {/* KPI cards always visible when analysis ready */}
            <div style={{ padding: '.25rem 0' }}>
              <KPICards
                kpis={analysis?.kpis}
                mc={analysis?.monte_carlo}
                bench={bench}
                extra={extra}
                phase={analysis?.phase}
              />
            </div>

            {/* Scenarios */}
            {openSections.has('scenarios') && (
              <div className="panel">
                <div className="panel-header" onClick={() => toggleSection('scenarios')}>
                  📊 Projections 3 scénarios <span>{openSections.has('scenarios') ? '▲' : '▼'}</span>
                </div>
                <div className="panel-body">
                  <ScenariosChart scenarios={analysis?.scenarios} />
                </div>
              </div>
            )}

            {/* Monte Carlo */}
            {openSections.has('montecarlo') && (
              <div className="panel">
                <div className="panel-header" onClick={() => toggleSection('montecarlo')}>
                  🎲 Monte Carlo Runway (×1000) <span>▲</span>
                </div>
                <div className="panel-body">
                  <MonteCarloChart mc={analysis?.monte_carlo} />
                  {analysis?.monte_carlo?.proba_survie_12m != null && (
                    <p style={{ fontSize: '.82rem', color: '#6b7280', marginTop: '.5rem' }}>
                      Probabilité de survie à 12 mois : <strong>{(analysis.monte_carlo.proba_survie_12m * 100).toFixed(0)}%</strong>
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Seasonality */}
            {openSections.has('seasonality') && (
              <div className="panel">
                <div className="panel-header" onClick={() => toggleSection('seasonality')}>
                  📅 Prévision saisonnalité <span>▲</span>
                </div>
                <div className="panel-body">
                  <SeasonalityChart seasonality={analysis?.seasonality} />
                </div>
              </div>
            )}

            {/* Benchmarks */}
            {openSections.has('benchmarks') && (
              <div className="panel">
                <div className="panel-header" onClick={() => toggleSection('benchmarks')}>
                  🏆 Benchmarks sectoriels <span>▲</span>
                </div>
                <div className="panel-body">
                  {!bench ? (
                    <p style={{ color: '#9ca3af', fontSize: '.83rem' }}>
                      Aucun benchmark disponible. Ajoutez une <code>TAVILY_API_KEY</code> dans <code>.env</code> pour activer la recherche web en temps réel.
                    </p>
                  ) : benchText ? (
                    /* Rich markdown analysis from _format_benchmark_result */
                    <div className="md" style={{ fontSize: '.84rem' }}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{benchText}</ReactMarkdown>
                      {/* Comparison chart below the analysis */}
                      <BenchmarkChart bench={bench} extra={extra} kpis={analysis?.kpis} ctx={ctx} />
                    </div>
                  ) : (
                    /* Fallback: simple table if bench_text not yet loaded */
                    <>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                        <span style={{
                          background: bench.source?.includes('tavily') ? '#fff3e0' : '#e8f5e9',
                          color: bench.source?.includes('tavily') ? '#e65100' : '#2e7d32',
                          border: `1px solid ${bench.source?.includes('tavily') ? '#ffcc80' : '#a5d6a7'}`,
                          borderRadius: 4, padding: '2px 8px', fontSize: '.74rem', fontWeight: 600
                        }}>
                          {bench.source?.includes('tavily') ? 'Tavily live' : 'ChromaDB cache'}
                        </span>
                        <span style={{ color: '#6b7280', fontSize: '.83rem' }}>
                          Similarité : <strong>{bench.similarity_score ? `${(bench.similarity_score * 100).toFixed(0)}%` : '—'}</strong>
                        </span>
                      </div>
                      <BenchmarkChart bench={bench} extra={extra} kpis={analysis?.kpis} ctx={ctx} />
                    </>
                  )}
                </div>
              </div>
            )}

            {/* Investment recommendation */}
            {(openSections.has('investment') || hasA2APending) && (
              <div className="panel">
                <div className="panel-header" onClick={() => toggleSection('investment')}>
                  💼 Recommandation InvestmentAgent <span>{openSections.has('investment') ? '▲' : '▼'}</span>
                </div>
                <div className="panel-body">
                  {a2a ? (
                    <A2APanel
                      a2a={a2a}
                      elapsedSeconds={a2aElapsed}
                      onClarificationSent={() => { setA2aElapsed(0) }}
                    />
                  ) : a2aPublishTime ? (
                    <div style={{ color: '#9ca3af', fontSize: '.83rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="spinner" />
                      En attente de l&apos;InvestmentAgent… ({a2aElapsed}s)
                    </div>
                  ) : (
                    <div style={{ color: '#9ca3af', fontSize: '.83rem' }}>
                      InvestmentAgent n&apos;a pas encore reçu de données — soumettez votre analyse financière d&apos;abord.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
        </div> {/* end content-scroll */}

        {/* Input */}
        <div className="input-bar">
          {whatifMode && (
            <div style={{
              background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: 8,
              padding: '.4rem .75rem', fontSize: '.8rem', color: '#d97706',
              marginBottom: '.5rem', display: 'flex', justifyContent: 'space-between'
            }}>
              <span>⚡ Mode simulation — décrivez un scénario hypothétique</span>
              <button onClick={handleToggleWhatif} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#d97706' }}>✕</button>
            </div>
          )}
          <div className="input-row">
            <textarea
              ref={textareaRef}
              className="input-box"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder={whatifMode ? 'Ex: Que se passe-t-il si mon revenu double ?' : 'Décrivez votre startup ou posez une question…'}
              rows={1}
            />
            <button
              className={`icon-btn ${whatifMode ? 'active' : ''}`}
              onClick={handleToggleWhatif}
              title="Mode simulation What-If"
            >⚡</button>
            <button
              className="send-btn"
              onClick={() => handleSend()}
              disabled={loading || !input.trim()}
            >
              {loading ? <span className="spinner" /> : '→'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
