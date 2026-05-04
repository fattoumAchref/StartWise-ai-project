'use client'
import '../finance/finance.css'
import { useState, useEffect, useRef, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import dynamic from 'next/dynamic'
import {
  AlertTriangle, CheckCircle2, BrainCircuit,
  Download, FlaskConical, History, Upload, Lock, Lightbulb, X, MessageCircle, FileText,
} from 'lucide-react'

import type { Message, AppState, A2AState, Analysis, Benchmark, BenchmarkExtra, FinancialContext, Validation } from '@/lib/types'
import { sendMessage, getState, getA2AState, toggleWhatif, downloadPdf, newConversation, restoreConversation, deleteConversation, uploadFile, prefetchBenchmarks } from '@/services/cfo'
import { updateWorkflowStatus, markStepAsCompleted } from '@/services/agents'
import KPICards from '@/components/cfo/KPICards'
import { ScenariosChart, MonteCarloChart, SeasonalityChart, BenchmarkChart } from '@/components/cfo/Charts'

dynamic(() => import('react-plotly.js'), { ssr: false })

type EntryPath = 'ideation' | 'audit' | 'none'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n?: number | null, suffix = '', decimals = 1): string {
  if (n == null) return '—'
  return `${n.toFixed(decimals)}${suffix}`
}

function runwayColor(months?: number | null) {
  if (months == null) return 'neutral'
  if (months < 3) return 'critical'
  if (months < 6) return 'warning'
  return 'positive'
}

function cashAlertColor(alert?: string) {
  if (!alert) return 'neutral'
  if (alert === 'CRITIQUE') return 'critical'
  if (alert === 'ATTENTION') return 'warning'
  return 'positive'
}

function survieColor(p?: number | null) {
  if (p == null) return 'neutral'
  if (p < 0.4) return 'critical'
  if (p < 0.7) return 'warning'
  return 'positive'
}

function confidencePhrase(analysis?: Analysis, validation?: Validation): string {
  if (!analysis?.kpis) return "Soumettez vos données pour démarrer l'analyse"
  const score = validation?.data_quality_score
  if (score != null && score >= 0.8) return 'Analyse haute fiabilité — données complètes'
  if (score != null && score >= 0.6) return 'Analyse partielle — complétez vos données'
  const level = analysis.confidence?.level
  if (level === 'HIGH') return 'Analyse haute fiabilité'
  if (level === 'MEDIUM') return 'Analyse partielle — ajoutez des données pour améliorer'
  return 'Analyse en construction — continuez à enrichir vos données'
}

function modeText(expertMode: boolean, expertCopy: string, beginnerCopy: string): string {
  return expertMode ? expertCopy : beginnerCopy
}

function extractNarrativeFromMessages(messages: Message[]): string {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const m = messages[i]
    if (m.role !== 'assistant' || !m.content?.trim()) continue
    const c = m.content.trim()
    if (
      c.includes('## Idée reçue') ||
      c.includes('## Idee recue') ||
      c.includes('### Données extraites') ||
      c.includes('### Donnees extraites') ||
      c.includes('### Positionnement sectoriel')
    ) return c
  }
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const m = messages[i]
    if (m.role !== 'assistant' || !m.content?.trim()) continue
    const c = m.content.trim()
    if (!c.toLowerCase().includes('erreur lors de la requête') && c.length > 40) return c
  }
  return ''
}

function composeIdeaNarrative(idea: string, summary: string, expertMode: boolean): string {
  const cleanIdea = (idea || '').trim()
  const cleanSummary = (summary || '').trim()
  if (!cleanIdea && !cleanSummary) return ''
  if (expertMode) {
    return [
      '## Analyse initiale (Business Idea)',
      '',
      cleanIdea ? `**Business Idea:** ${cleanIdea}` : '',
      cleanSummary ? `**Contexte ideation:** ${cleanSummary.slice(0, 1200)}` : '',
      '',
      '**Prochaine etape:** le CFO affine ensuite l analyse via vos reponses chiffrables ou qualitatives.',
    ].filter(Boolean).join('\n')
  }
  return [
    '## Premier regard sur votre idee',
    '',
    cleanIdea ? `Votre projet: **${cleanIdea}**` : '',
    cleanSummary ? `Ce que nous avons compris: ${cleanSummary.slice(0, 1000)}` : '',
    '',
    "Ensuite, votre CFO vous posera des questions simples pour rendre l'analyse plus precise.",
  ].filter(Boolean).join('\n')
}

function getIdeationContextFromStorage() {
  if (typeof window === 'undefined') return { idea: '', summary: '', track: '' }
  const track = localStorage.getItem('startwise_track') || ''
  let summary =
    localStorage.getItem('startwise_summary') ||
    localStorage.getItem('sw_ideation_summary') ||
    ''
  let idea =
    localStorage.getItem('startwise_business_idea') ||
    localStorage.getItem('sw_ideation_business_idea') ||
    ''

  // Hard fallback: serialized ideation payload
  if ((!summary || !idea) && localStorage.getItem('sw_ideation_data')) {
    try {
      const raw = localStorage.getItem('sw_ideation_data') || '{}'
      const parsed = JSON.parse(raw) as { summary?: string; businessIdea?: string; business_idea?: string }
      if (!summary) summary = parsed.summary || ''
      if (!idea) idea = parsed.businessIdea || parsed.business_idea || ''
    } catch {
      // noop
    }
  }

  // Existing startup track — onboarding stores startup info in product_audit_draft,
  // NOT in startwise_summary. Extract it so viability assessment has context to work with.
  if (!summary && !idea && track === 'startup') {
    try {
      const draft = JSON.parse(localStorage.getItem('startwise_product_audit_draft') || '{}') as {
        startup_name?: string; product_description?: string; website_url?: string
      }
      idea = draft.startup_name || ''
      // Build a minimal summary from startup description so the backend can
      // produce a CFO pre-analysis and ask for the right financial data.
      const desc = draft.product_description || ''
      const site = draft.website_url ? ` (site: ${draft.website_url})` : ''
      if (idea || desc) {
        summary = [
          idea ? `## Business Idea\n${idea}${site}` : '',
          desc ? `## Description\n${desc}` : '',
        ].filter(Boolean).join('\n\n')
      }
    } catch {
      // noop
    }
  }

  return { idea, summary, track }
}

// ── Question routing — maps agent questions to their relevant block ────────────
// Agent questions come from validation.questions_to_ask (dynamic, per session).
// We route them to the block where the answer belongs.

const BLOCK_QUESTION_KEYWORDS: Record<string, string[]> = {
  block1: ['burn', 'cash', 'runway', 'trésorerie', 'liquidit', 'dépens', 'coût', 'solde', 'capital', 'charges'],
  block2: ['revenu', 'client', 'churn', 'cac', 'marge', 'ltv', 'mrr', 'prix', 'recette', 'arpu', 'vente', 'acquis', 'rétent'],
  block3: ['scénario', 'croissance', 'projection', 'trajectoire', 'objectif', 'prévision'],
  block4: ['simulation', 'probabilit', 'survie', 'risque', 'incertitude'],
  block5: ['saison', 'historique', 'tendance', 'cycle', 'pic', 'creux', 'période'],
  block6: ['secteur', 'benchmark', 'concurrent', 'comparaison', 'industrie', 'marché'],
}

function routeQuestions(questions: string[]): Record<string, string[]> {
  const result: Record<string, string[]> = {
    block1: [], block2: [], block3: [], block4: [], block5: [], block6: [], unmatched: [],
  }
  for (const q of questions) {
    const qLower = q.toLowerCase()
    let matched = false
    for (const [blockId, keywords] of Object.entries(BLOCK_QUESTION_KEYWORDS)) {
      if (keywords.some(kw => qLower.includes(kw))) {
        result[blockId].push(q)
        matched = true
        break
      }
    }
    if (!matched) result.unmatched.push(q)
  }
  return result
}

type PendingBlock = {
  id: string
  title: string
  expertGoal: string
  beginnerGoal: string
  questions: string[]
  missingFields: string[]
}

function buildPendingBlocks(
  routedQuestions: Record<string, string[]>,
  missing: string[],
): PendingBlock[] {
  const orderedBlocks = ['block1', 'block2', 'block3', 'block4', 'block5', 'block6']
  return orderedBlocks
    .map((id) => {
      const questions = routedQuestions[id] || []
      const blockFields = BLOCK_FIELD_MAP[id] || []
      const missingFields = blockFields.filter(f => missing.some(m => m === f || m.startsWith(f)))
      const meta = BLOCK_META[id]
      return {
        id,
        title: meta?.title || id,
        expertGoal: meta?.expertGoal || '',
        beginnerGoal: meta?.beginnerGoal || '',
        questions,
        missingFields,
      }
    })
    .filter((b) => b.questions.length > 0 || b.missingFields.length > 0)
}

// ── Field metadata ─────────────────────────────────────────────────────────────

const FIELD_META: Record<string, { expertLabel: string; beginnerLabel: string }> = {
  mrr:             { expertLabel: 'MRR (revenu mensuel recurrent)', beginnerLabel: 'Combien vous gagnez environ chaque mois' },
  monthly_revenue: { expertLabel: "Chiffre d'affaires mensuel",     beginnerLabel: 'Vos revenus mensuels aproximatifs' },
  burn_rate:       { expertLabel: 'Burn rate mensuel',              beginnerLabel: 'Combien vous depensez chaque mois' },
  cash_balance:    { expertLabel: 'Tresorerie disponible',          beginnerLabel: 'Argent disponible aujourd hui' },
  initial_cash:    { expertLabel: 'Capital initial',                beginnerLabel: 'Argent de depart de votre projet' },
  churn_rate:      { expertLabel: 'Taux de churn',                  beginnerLabel: 'Clients perdus chaque mois (meme estimation)' },
  cac:             { expertLabel: 'CAC (cout d acquisition)',       beginnerLabel: 'Combien coute en moyenne obtenir un client' },
  n_clients:       { expertLabel: 'Nombre de clients actifs',       beginnerLabel: 'Combien de clients actifs actuellement' },
  prix_client:     { expertLabel: 'ARPU / revenu moyen par client', beginnerLabel: 'Combien paie un client en moyenne' },
}

// Which missing fields belong to which block
const BLOCK_FIELD_MAP: Record<string, string[]> = {
  block1: ['burn_rate', 'cash_balance', 'initial_cash'],
  block2: ['mrr', 'monthly_revenue', 'cac', 'churn_rate', 'n_clients', 'prix_client'],
}

// ── Raw input field — quick field data entry in a block ────────────────────────

function fieldLabel(fieldKey: string, expertMode: boolean): string {
  const info = FIELD_META[fieldKey]
  if (!info) return fieldKey
  return modeText(expertMode, info.expertLabel, info.beginnerLabel)
}

function BlockMiniComposer({
  contextLabel,
  expertMode,
  onAnswer,
  onFileAnswer,
  disabled,
}: {
  contextLabel: string
  expertMode: boolean
  onAnswer: (msg: string) => void
  onFileAnswer: (file: File, contextLabel: string) => void
  disabled?: boolean
}) {
  const [val, setVal] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const submit = () => {
    if (!val.trim() || disabled) return
    // Include question label + default currency hint so the parser extracts the right field.
    onAnswer(`${contextLabel}: ${val.trim()} (monnaie par defaut: TND/DT — preciser si USD, EUR ou autre)`)
    setVal('')
  }
  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
  }
  return (
    <div className="raw-input-group">
      <span className="raw-input-label">
        {modeText(expertMode, 'Réponse (Ex: 5 000 TND/mois)', 'Répondez avec un chiffre — une estimation suffit')}
      </span>
      <div className="raw-input-row">
        <textarea
          className="raw-input-field"
          placeholder={modeText(
            expertMode,
            'Ex: 5 000 TND · 12 000 USD · environ 3 000 DT/mois...',
            'Ex: environ 5 000 dinars par mois (ou USD/EUR si hors Tunisie).',
          )}
          value={val}
          onChange={e => setVal(e.target.value)}
          onKeyDown={handleKey}
          rows={2}
          disabled={disabled}
        />
      </div>
      <div className="raw-input-row">
        <button className="raw-input-btn" onClick={submit} disabled={!val.trim() || disabled}>
          {modeText(expertMode, 'Envoyer au CFO', 'Envoyer ma réponse')}
        </button>
        <button className="raw-input-btn" type="button" onClick={() => fileRef.current?.click()} disabled={disabled}>
          {modeText(expertMode, 'Joindre un fichier', 'Ajouter un fichier')}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.txt,.pdf,.docx,.xlsx,.json"
          style={{ display: 'none' }}
          onChange={e => {
            const file = e.target.files?.[0]
            if (file) onFileAnswer(file, contextLabel)
            e.target.value = ''
          }}
        />
      </div>
    </div>
  )
}

// ── Per-block inline Q&A — shows ONE question at a time, with answer input ────
// This replaces the old "go to agent panel" redirect. Each block is self-contained.

function BlockInlineQA({
  blockId,
  routedQuestions,
  missing,
  expertMode,
  onAnswer,
  onFileAnswer,
  onAnswered,
  feedback,
  isLoading,
}: {
  blockId: string
  routedQuestions: Record<string, string[]>
  missing: string[]
  expertMode: boolean
  onAnswer: (msg: string) => void
  onFileAnswer: (file: File, contextLabel: string) => void
  onAnswered?: (question: string) => void
  feedback?: { text: string; type: 'success'|'warn'|'error'|'info' }
  isLoading?: boolean
}) {
  const blockQs = routedQuestions[blockId] || []
  const blockFields = BLOCK_FIELD_MAP[blockId] || []
  const missingForBlock = blockFields.filter(f => missing.some(m => m === f || m.startsWith(f)))

  const currentQuestion = blockQs[0] || null
  const currentMissingField = !currentQuestion ? (missingForBlock[0] || null) : null
  const displayQuestion = currentQuestion || (currentMissingField ? fieldLabel(currentMissingField, expertMode) : null)

  const totalPending = blockQs.length + missingForBlock.length

  // Always show the section if there's a question OR pending feedback to show.
  if (!displayQuestion && !feedback && !isLoading) return null

  const feedbackColor = feedback?.type === 'success' ? '#16a34a' : feedback?.type === 'error' ? '#dc2626' : '#d97706'
  const feedbackBg   = feedback?.type === 'success' ? 'hsl(142 76% 96%)' : feedback?.type === 'error' ? 'hsl(0 86% 97%)' : 'hsl(45 96% 96%)'

  return (
    <div className="block-qa-section">
      {/* Loading indicator — only for this block, not the global chat */}
      {isLoading && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '.45rem', fontSize: '.78rem', color: '#3b82f6', padding: '.35rem 0' }}>
          <span className="spinner" style={{ width: 12, height: 12 }} />
          <span>{modeText(expertMode, 'CFO traite votre réponse…', 'Votre CFO réfléchit…')}</span>
        </div>
      )}
      {/* Inline result — shown inside this block, not in a global banner */}
      {feedback && feedback.text !== '...' && (
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '.4rem', padding: '.5rem .6rem', borderRadius: 8,
                      background: feedbackBg, border: `1px solid ${feedbackColor}33`,
                      fontSize: '.79rem', color: feedbackColor, lineHeight: 1.5, marginBottom: '.3rem' }}>
          <span style={{ flexShrink: 0 }}>{feedback.type === 'success' ? '✓' : feedback.type === 'error' ? '✗' : '⚠'}</span>
          <span>{feedback.text}</span>
        </div>
      )}
      {displayQuestion && (
        <div className="block-qa-item">
          <div className="block-qa-question">
            <MessageCircle style={{ width: 12, height: 12, flexShrink: 0, marginTop: 2 }} />
            <span>{displayQuestion}</span>
          </div>
          <BlockMiniComposer
            contextLabel={displayQuestion}
            expertMode={expertMode}
            onAnswer={(msg) => {
              if (displayQuestion) onAnswered?.(displayQuestion)
              onAnswer(msg)
            }}
            onFileAnswer={onFileAnswer}
            disabled={isLoading}
          />
        </div>
      )}
      {totalPending > 1 && !isLoading && (
        <p style={{ fontSize: '.72rem', color: '#94a3b8', marginTop: '.3rem' }}>
          {modeText(
            expertMode,
            `+${totalPending - 1} autre(s) question(s) après votre réponse`,
            `Répondez — la suite apparaîtra automatiquement (${totalPending - 1} de plus)`,
          )}
        </p>
      )}
    </div>
  )
}

const BLOCK_META: Record<string, { title: string; expertGoal: string; beginnerGoal: string }> = {
  block1: {
    title: 'Bloc 1 - Situation globale',
    expertGoal: 'Objectif: fiabiliser runway, cash-out alert et niveau de risque court terme.',
    beginnerGoal: "Objectif: comprendre si votre tresorerie tient et ou se situe l'urgence."
  },
  block2: {
    title: 'Bloc 2 - KPIs business',
    expertGoal: 'Objectif: consolider les unit economics (LTV/CAC, marge, efficacite acquisition).',
    beginnerGoal: 'Objectif: verifier si votre modele gagne assez par client.'
  },
  block3: {
    title: 'Bloc 3 - Scenarios',
    expertGoal: 'Objectif: affiner les hypotheses de croissance sur les trois trajectoires.',
    beginnerGoal: "Objectif: voir ce qui se passe si ca va mieux, pareil ou moins bien."
  },
  block4: {
    title: 'Bloc 4 - Monte Carlo',
    expertGoal: "Objectif: reduire l'incertitude statistique sur la probabilite de survie.",
    beginnerGoal: 'Objectif: estimer vos chances de tenir dans plusieurs cas possibles.'
  },
  block5: {
    title: 'Bloc 5 - Saisonnalite',
    expertGoal: 'Objectif: mieux calibrer les variations mensuelles de revenus.',
    beginnerGoal: 'Objectif: anticiper les mois forts et les mois faibles.'
  },
  block6: {
    title: 'Bloc 6 - Benchmarks',
    expertGoal: 'Objectif: positionner vos KPI par rapport aux medians sectoriels.',
    beginnerGoal: 'Objectif: comparer vos chiffres a des startups similaires.'
  },
}

function AgentGuidance({
  expertMode,
  validation,
  routedQuestions,
  pendingBlocks,
  onAnswer,
  onFileAnswer,
}: {
  expertMode: boolean
  validation?: Validation
  routedQuestions: Record<string, string[]>
  pendingBlocks: PendingBlock[]
  onAnswer: (msg: string) => void
  onFileAnswer: (file: File, contextLabel: string) => void
}) {
  const missing = validation?.missing_critical || []
  const questions = Object.values(routedQuestions).flat().filter(Boolean)
  const totalPending = pendingBlocks.reduce((acc, b) => acc + b.questions.length + b.missingFields.length, 0)

  const general = modeText(
    expertMode,
    'Le CFO a besoin de precisions pour augmenter la fiabilite des KPI, des scenarios et des benchmarks.',
    "Pour bien vous guider, votre CFO a besoin de quelques infos en plus sur votre situation.",
  )

  return (
    <div className="agent-guidance-card">
      <div className="agent-guidance-title">
        <BrainCircuit style={{ width: 14, height: 14 }} />
        <span>{modeText(expertMode, 'Guidance agent (general + detail)', 'Ce dont votre CFO a besoin')}</span>
        <span className="questions-hub-count">{totalPending}</span>
      </div>
      <p className="agent-guidance-general">{general}</p>
      {missing.length > 0 ? (
        <div className="agent-guidance-section">
          <span className="agent-guidance-label">{modeText(expertMode, 'Detail - informations a completer', 'Infos a ajouter')}</span>
          <ul className="agent-guidance-list">
            {missing.map((f) => (
              <li key={f}>{fieldLabel(f, expertMode)}</li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="agent-guidance-section">
          <span className="agent-guidance-label">{modeText(expertMode, 'Detail - informations a completer', 'Infos a ajouter')}</span>
          <ul className="agent-guidance-list">
            <li>{modeText(expertMode, 'Aucune information critique manquante detectee.', 'Aucune info bloquante manquante pour le moment.')}</li>
          </ul>
        </div>
      )}
      {questions.length > 0 ? (
        <div className="agent-guidance-section">
          <span className="agent-guidance-label">{modeText(expertMode, 'Detail - questions dynamiques de l agent', 'Questions posees par votre CFO')}</span>
          <ul className="agent-guidance-list">
            {questions.slice(0, 6).map((q, i) => <li key={i}>{q}</li>)}
          </ul>
        </div>
      ) : (
        <div className="agent-guidance-section">
          <span className="agent-guidance-label">{modeText(expertMode, 'Detail - questions dynamiques de l agent', 'Questions posees par votre CFO')}</span>
          <ul className="agent-guidance-list">
            <li>{modeText(expertMode, 'Aucune question ouverte en attente.', 'Pas de question en attente pour le moment.')}</li>
          </ul>
        </div>
      )}
      {pendingBlocks.length > 0 && (
        <div className="questions-hub-list" style={{ marginTop: '.7rem' }}>
          {pendingBlocks.map((block) => (
            <div key={block.id} className="questions-hub-group">
              <div className="questions-hub-group-head">
                <span className="questions-hub-block">{block.title}</span>
                <span className="questions-hub-state active">{modeText(expertMode, 'Requis', 'A completer')}</span>
                <span className="questions-hub-goal">{modeText(expertMode, block.expertGoal, block.beginnerGoal)}</span>
              </div>
              {block.questions.length > 0 && (
                <ul className="agent-guidance-list">
                  {block.questions.map((q, i) => <li key={`${block.id}_q_${i}`}>{q}</li>)}
                </ul>
              )}
              {block.missingFields.length > 0 && (
                <ul className="agent-guidance-list">
                  {block.missingFields.map((f) => <li key={`${block.id}_m_${f}`}>{fieldLabel(f, expertMode)}</li>)}
                </ul>
              )}
              <BlockMiniComposer
                contextLabel={block.title}
                expertMode={expertMode}
                onAnswer={onAnswer}
                onFileAnswer={onFileAnswer}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Situation card ─────────────────────────────────────────────────────────────

function SituationCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color: string }) {
  return (
    <div className={`situation-card ${color}`}>
      <span className="situation-card-label">{label}</span>
      <span className="situation-card-value">{value}</span>
      {sub && <span className="situation-card-sub">{sub}</span>}
    </div>
  )
}

// ── Block 1 — Situation globale ────────────────────────────────────────────────

function Block1({ analysis, expertMode, routedQuestions, missing, onAnswer, onFileAnswer, onAnswered, feedback, isLoading }: {
  analysis?: Analysis; expertMode: boolean
  routedQuestions: Record<string, string[]>; missing: string[]
  onAnswer: (msg: string) => void
  onFileAnswer: (file: File, contextLabel: string) => void
  onAnswered?: (question: string) => void
  feedback?: { text: string; type: 'success'|'warn'|'error'|'info' }
  isLoading?: boolean
}) {
  const kpis = analysis?.kpis
  const mc = analysis?.monte_carlo
  const hasData = !!kpis
  const runway = kpis?.runway_months
  const cashAlert = kpis?.cash_out_alert
  const phase = analysis?.phase
  const survie = mc?.proba_survie_12m
  const confidence = analysis?.confidence

  return (
    <>
      <div className="situation-grid">
        <SituationCard
          label={expertMode ? 'Runway (mois)' : 'Autonomie financière'}
          value={hasData ? fmt(runway, ' mois') : '?'}
          sub={expertMode ? 'cash_balance ÷ burn_net'
            : runway == null ? 'Après analyse'
            : runway < 3 ? 'Urgent — agir maintenant'
            : runway < 6 ? 'Vigilance requise' : 'Situation correcte'}
          color={runwayColor(runway)}
        />
        <SituationCard
          label={expertMode ? 'Cash-Out Alert' : 'Trésorerie'}
          value={hasData ? (cashAlert || 'OK') : '?'}
          sub={expertMode ? 'kpis.cash_out_alert'
            : cashAlert === 'CRITIQUE' ? 'Risque immédiat de manque de liquidités'
            : cashAlert === 'ATTENTION' ? 'Vigilance requise sur les dépenses'
            : hasData ? 'Situation saine' : 'Après analyse'}
          color={cashAlertColor(cashAlert)}
        />
        <SituationCard
          label={expertMode ? 'Phase startup' : 'Stade de développement'}
          value={hasData ? (phase || '—') : '?'}
          sub={expertMode ? 'route_by_phase()'
            : phase === 'SEED' ? 'Focus : valider le modèle'
            : phase === 'TRACTION' ? 'Focus : accélérer la croissance'
            : phase === 'FUNDRAISING' ? 'Focus : préparer la levée'
            : 'Après analyse'}
          color="neutral"
        />
        <SituationCard
          label={expertMode ? 'Survie 12m — Monte Carlo' : 'Chances de survie à 1 an'}
          value={hasData && survie != null ? `${(survie * 100).toFixed(0)}%` : '?'}
          sub={expertMode ? 'P(survie) sur 1000 simulations'
            : survie != null ? 'Sur 1000 scénarios simulés' : 'Après analyse'}
          color={survieColor(survie)}
        />
      </div>

      {kpis?.cash_out_alert === 'CRITIQUE' && (
        <div className="alert-banner alert-critique">
          <AlertTriangle style={{ width: 15, height: 15, flexShrink: 0, marginTop: 1 }} />
          <span>Trésorerie critique — votre startup risque de manquer de liquidités. Agissez en priorité.</span>
        </div>
      )}
      {kpis?.cash_out_alert === 'ATTENTION' && (
        <div className="alert-banner alert-attention">
          <AlertTriangle style={{ width: 15, height: 15, flexShrink: 0, marginTop: 1 }} />
          <span>Vigilance trésorerie — surveillez vos dépenses et explorez des revenus supplémentaires.</span>
        </div>
      )}
      {kpis?.cash_out_alert === 'RENTABLE' && (
        <div className="alert-banner alert-rentable">
          <CheckCircle2 style={{ width: 15, height: 15, flexShrink: 0, marginTop: 1 }} />
          <span>Situation saine — votre startup génère plus qu'elle ne dépense.</span>
        </div>
      )}
      {kpis?.alertes?.slice(0, 2).map((a, i) => (
        <div key={i} className="alert-banner alert-attention">
          <AlertTriangle style={{ width: 15, height: 15, flexShrink: 0, marginTop: 1 }} />
          <span>{a}</span>
        </div>
      ))}

      {confidence?.score != null && (
        <div className="confidence-bar-wrapper">
          <div className="confidence-bar-label">
            <span>{expertMode ? 'Data Quality Score' : "Fiabilité de l'analyse"}</span>
            <span style={{ fontWeight: 700 }}>{(confidence.score * 100).toFixed(0)}%</span>
          </div>
          <div className="confidence-bar">
            <div className="confidence-bar-fill" style={{ width: `${confidence.score * 100}%` }} />
          </div>
        </div>
      )}

      {!hasData && (
        <p style={{ fontSize: '.82rem', color: '#94a3b8', marginTop: '.5rem', lineHeight: 1.6 }}>
          {expertMode
            ? 'Pipeline CFO non exécuté. Requis : burn_rate, cash_balance, monthly_revenue.'
            : 'Renseignez burn rate, trésorerie et revenus pour lancer votre analyse complète.'}
        </p>
      )}

      <BlockInlineQA
        blockId="block1" routedQuestions={routedQuestions}
        missing={missing} expertMode={expertMode}
        onAnswer={onAnswer} onFileAnswer={onFileAnswer}
        onAnswered={onAnswered}
        feedback={feedback} isLoading={isLoading}
      />
    </>
  )
}

// ── Block 5 — Seasonality text input ──────────────────────────────────────────

function SeasonalityTextInput({ expertMode, onSubmit, disabled }: {
  expertMode: boolean; onSubmit: (msg: string) => void; disabled?: boolean
}) {
  const [val, setVal] = useState('')
  const submit = () => {
    if (!val.trim() || disabled) return
    onSubmit(`Voici mon historique de revenus mensuels pour la saisonnalité: ${val.trim()}. Analyse la saisonnalité et mets à jour mes projections.`)
    setVal('')
  }
  return (
    <div className="raw-input-group" style={{ marginTop: '.7rem' }}>
      <span className="raw-input-label">
        {expertMode
          ? 'Historique de revenus mensuel (revenue_history) — texte libre'
          : 'Saisissez vos revenus mois par mois (texte libre)'}
      </span>
      <div className="raw-input-row">
        <textarea
          className="raw-input-field"
          placeholder={expertMode
            ? 'Ex: Jan 5000, Fév 4500, Mar 6200, Avr 7100 ... (TND par défaut)'
            : 'Ex: Janvier 5 000 DT, Février 4 500 DT, Mars 6 200 DT...'}
          value={val}
          onChange={e => setVal(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
          rows={3}
          disabled={disabled}
        />
      </div>
      <button className="raw-input-btn" onClick={submit} disabled={!val.trim() || disabled}>
        {expertMode ? 'Analyser la saisonnalité' : 'Envoyer mes données'}
      </button>
    </div>
  )
}

// ── Block 4 — Monte Carlo summary ─────────────────────────────────────────────

function MonteCarloSummary({ mc, expertMode, onPrefillChat }: {
  mc?: Analysis['monte_carlo']; expertMode: boolean; onPrefillChat: (t: string) => void
}) {
  if (!mc) return null
  const raw = mc as Record<string, number>
  const p10 = raw.p10_months
  const p50 = raw.p50_months
  const p90 = raw.p90_months
  const survie = mc.proba_survie_12m

  if (expertMode) {
    return (
      <div className="mc-tiles">
        {p10 != null && <div className="mc-tile p10"><span className="mc-tile-label">P10 — pessimiste</span><span className="mc-tile-value">{p10.toFixed(1)}m</span><span className="mc-tile-sub">runway minimum</span></div>}
        {p50 != null && <div className="mc-tile p50"><span className="mc-tile-label">P50 — médiane</span><span className="mc-tile-value">{p50.toFixed(1)}m</span><span className="mc-tile-sub">runway probable</span></div>}
        {p90 != null && <div className="mc-tile p90"><span className="mc-tile-label">P90 — optimiste</span><span className="mc-tile-value">{p90.toFixed(1)}m</span><span className="mc-tile-sub">runway max</span></div>}
      </div>
    )
  }

  return (
    <div style={{ marginTop: '.75rem' }}>
      {survie != null && (
        <p style={{ fontSize: '.88rem', color: '#374151', marginBottom: '.8rem', lineHeight: 1.65 }}>
          Sur <strong>1 000 scénarios simulés</strong>, votre startup a{' '}
          <strong style={{ color: survie >= 0.7 ? '#15803d' : survie >= 0.4 ? '#d97706' : '#dc2626' }}>
            {(survie * 100).toFixed(0)}% de chances
          </strong>{' '}
          de survivre 12 mois.{p50 != null && ` Runway médian : ${p50.toFixed(1)} mois.`}
        </p>
      )}
      <p style={{ fontSize: '.74rem', color: '#6366f1', marginBottom: '.5rem' }}>
        Simulez des hypothèses dans le chat libre →
      </p>
      <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap' }}>
        <button className="suggestion-chip" onClick={() => onPrefillChat('Que se passe-t-il si je réduis mes coûts de 20% ?')}>
          Réduire les coûts de 20%
        </button>
        <button className="suggestion-chip" onClick={() => onPrefillChat('Que se passe-t-il si mes revenus augmentent de 30% en 3 mois ?')}>
          Revenus +30% en 3 mois
        </button>
      </div>
    </div>
  )
}

// ── Block 7 — Guide stratégique ───────────────────────────────────────────────

const UNLOCK_GUIDE = [
  { field: 'mrr',          title: 'Ajoutez votre revenu mensuel',    desc: 'Débloque : Gross Margin, LTV/CAC, Break-even, Benchmarks' },
  { field: 'burn_rate',    title: 'Ajoutez votre burn rate mensuel', desc: 'Débloque : Runway précis, Cash-out alert, Monte Carlo affiné' },
  { field: 'cash_balance', title: 'Ajoutez votre trésorerie',        desc: 'Débloque : Runway exact, Probabilité de survie à 12 mois' },
  { field: 'churn_rate',   title: 'Ajoutez votre taux de churn',     desc: 'Débloque : LTV/CAC ratio, Analyse de rétention client' },
  { field: 'cac',          title: 'Ajoutez votre CAC',               desc: 'Débloque : LTV/CAC, Efficacité marketing, Benchmark' },
]

function BlockStrategicGuide({ validation, analysis, hasAnalysis, loading, routedQuestions, onPrefillChat, entryPath, expertMode }: {
  validation?: Validation; analysis?: Analysis; hasAnalysis: boolean; loading: boolean
  routedQuestions: Record<string, string[]>; onPrefillChat: (t: string) => void
  entryPath: EntryPath; expertMode: boolean
}) {
  const unmatchedQs = routedQuestions.unmatched || []
  const missing = validation?.missing_critical || []
  const phase = analysis?.phase

  if (!hasAnalysis && loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '.65rem', color: '#3b82f6', fontSize: '.84rem', padding: '.25rem 0' }}>
        <span className="spinner" style={{ width: 14, height: 14 }} />
        <span>Analyse en cours — votre CFO prépare votre bilan…</span>
      </div>
    )
  }

  if (!hasAnalysis && entryPath !== 'ideation') {
    return (
      <div className="unlock-list">
        <div className="unlock-item">
          <div className="unlock-item-icon">1</div>
          <div className="unlock-item-body">
            <div className="unlock-item-title">Décrivez votre situation financière</div>
            <div className="unlock-item-desc">Burn rate, trésorerie, revenus — ces 3 données lancent l'analyse complète.</div>
            <button className="unlock-chip-send" onClick={() => onPrefillChat("Mon burn rate est ___ TND/mois, j'ai ___ TND en trésorerie et ___ TND de revenus mensuels.")}>
              Utiliser ce modèle dans le chat →
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (!hasAnalysis) return null

  const missingItems = UNLOCK_GUIDE.filter(g => missing.includes(g.field))

  return (
    <div className="unlock-list">
      {unmatchedQs.length === 0 && missingItems.length === 0 && (
        <div className="alert-banner alert-rentable" style={{ marginBottom: '.25rem' }}>
          <CheckCircle2 style={{ width: 15, height: 15, flexShrink: 0 }} />
          <span>Toutes les données essentielles sont renseignées. Votre analyse est complète.</span>
        </div>
      )}

      {/* Strategic questions that don't fit a specific block — go to chat */}
      {unmatchedQs.map((q, i) => (
        <div key={`uq_${i}`} className="unlock-item">
          <div className="unlock-item-icon" style={{ background: '#ede9fe', borderColor: '#c4b5fd', color: '#7c3aed' }}>?</div>
          <div className="unlock-item-body">
            <div className="unlock-item-title">Question stratégique de votre CFO</div>
            <div className="unlock-item-desc">{q}</div>
            <button className="unlock-chip-send" onClick={() => onPrefillChat(q)} style={{ borderColor: '#c4b5fd', color: '#7c3aed', background: '#ede9fe' }}>
              Répondre dans le chat libre →
            </button>
          </div>
        </div>
      ))}

      {/* Still-missing fields not yet covered by blocks 1/2 */}
      {missingItems.map(item => (
        <div key={item.field} className="unlock-item">
          <div className="unlock-item-icon"><Lock style={{ width: 11, height: 11 }} /></div>
          <div className="unlock-item-body">
            <div className="unlock-item-title">{item.title}</div>
            <div className="unlock-item-desc">{item.desc}</div>
          </div>
        </div>
      ))}

      {/* Phase-specific strategic advice */}
      {phase === 'SEED' && (
        <div className="unlock-item">
          <div className="unlock-item-icon"><Lightbulb style={{ width: 11, height: 11 }} /></div>
          <div className="unlock-item-body">
            <div className="unlock-item-title">Phase SEED — Focus</div>
            <div className="unlock-item-desc">
              {expertMode
                ? 'Cibles : LTV/CAC > 3, Gross Margin > 60%, Burn Multiple < 2. Validez le PMF avant de scaler.'
                : "Validez que vos clients paient et restent avant d'augmenter vos dépenses."}
            </div>
          </div>
        </div>
      )}
      {phase === 'TRACTION' && (
        <div className="unlock-item">
          <div className="unlock-item-icon"><Lightbulb style={{ width: 11, height: 11 }} /></div>
          <div className="unlock-item-body">
            <div className="unlock-item-title">Phase TRACTION — Focus</div>
            <div className="unlock-item-desc">
              {expertMode
                ? 'Optimisez CAC Payback < 12 mois et NRR > 100%. Préparez le deck investisseur.'
                : "Réduisez le coût d'acquisition et diminuez le churn avant de scaler."}
            </div>
          </div>
        </div>
      )}
      {phase === 'FUNDRAISING' && (
        <div className="unlock-item">
          <div className="unlock-item-icon"><Lightbulb style={{ width: 11, height: 11 }} /></div>
          <div className="unlock-item-body">
            <div className="unlock-item-title">Phase FUNDRAISING — Focus</div>
            <div className="unlock-item-desc">
              {expertMode
                ? 'Mettez en avant MRR growth MoM, NRR, pipeline ARR. Préparez la data room.'
                : "Préparez vos chiffres clés : croissance mensuelle, rétention, coût d'acquisition."}
            </div>
          </div>
        </div>
      )}

      <div className="unlock-item">
        <div className="unlock-item-icon"><FlaskConical style={{ width: 11, height: 11 }} /></div>
        <div className="unlock-item-body">
          <div className="unlock-item-title">Explorez des scénarios</div>
          <div className="unlock-item-desc">Utilisez le chat libre pour tester des hypothèses — réduction des coûts, nouvelle levée, nouveaux marchés.</div>
          <button className="unlock-chip-send" onClick={() => onPrefillChat('Que se passe-t-il si mes revenus augmentent de 20% le mois prochain ?')}>
            Tester dans le chat →
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Smart suggestions (chat libre) ────────────────────────────────────────────

function SmartSuggestions({ analysis, hasAnalysis, onPrefillChat, loading }: {
  analysis?: Analysis; hasAnalysis: boolean; onPrefillChat: (t: string) => void; loading: boolean
}) {
  if (loading || !hasAnalysis) return null

  const items: Array<{ label: string; template: string }> = []
  const runway = analysis?.kpis?.runway_months
  if (runway != null && runway < 6)
    items.push({ label: 'Comment prolonger ma runway ?', template: 'Comment puis-je prolonger ma runway ? Quelles dépenses réduire en priorité ?' })
  if (analysis?.phase === 'SEED')
    items.push({ label: 'Préparer une levée de fonds', template: 'Comment me préparer à une levée de fonds en phase SEED ?' })
  if (analysis?.phase === 'FUNDRAISING')
    items.push({ label: 'KPIs pour investisseurs', template: 'Quels KPIs mettre en avant pour convaincre un investisseur ?' })
  items.push({ label: 'Simuler +30% revenus', template: 'Que se passe-t-il si mes revenus augmentent de 30% ?' })
  items.push({ label: "C'est quoi le LTV/CAC ?", template: "Qu'est-ce que le LTV/CAC et comment l'améliorer ?" })

  return (
    <div className="suggestions-bar">
      <span className="suggestions-label">Suggestions</span>
      {items.slice(0, 4).map((s, i) => (
        <button key={i} className="suggestion-chip" onClick={() => onPrefillChat(s.template)}>
          {s.label}
        </button>
      ))}
    </div>
  )
}

// ── History modal ─────────────────────────────────────────────────────────────

function HistoryModal({ conversations, onRestore, onDelete, onNew, onClose }: {
  conversations: AppState['conversations']
  onRestore: (id: string) => void
  onDelete: (id: string) => void
  onNew: () => void
  onClose: () => void
}) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.45)', zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: '#fff', borderRadius: 18, padding: '1.5rem', width: 420, maxHeight: '80vh', overflow: 'auto', boxShadow: '0 12px 48px rgba(0,0,0,.22)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <span style={{ fontWeight: 700, fontSize: '.95rem', color: '#1e3a8a' }}>Historique des conversations</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', padding: 4 }}>
            <X style={{ width: 16, height: 16 }} />
          </button>
        </div>
        <button onClick={onNew} style={{ display: 'block', width: '100%', marginBottom: '.75rem', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 10, padding: '.55rem 1rem', color: '#2563eb', fontSize: '.83rem', fontWeight: 600, cursor: 'pointer' }}>
          + Nouvelle conversation
        </button>
        {!conversations?.length ? (
          <p style={{ color: '#94a3b8', fontSize: '.83rem', textAlign: 'center', padding: '1.5rem 0' }}>Aucun historique disponible.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '.45rem' }}>
            {conversations.map(conv => (
              <div key={conv.id} style={{ display: 'flex', alignItems: 'center', gap: '.5rem', padding: '.65rem .9rem', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10 }}>
                <span style={{ flex: 1, fontSize: '.82rem', color: '#374151', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {conv.title || `Session ${conv.id.slice(0, 8)}`}
                </span>
                <button onClick={() => onRestore(conv.id)} style={{ fontSize: '.73rem', color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}>Restaurer</button>
                <button onClick={() => onDelete(conv.id)} style={{ fontSize: '.73rem', color: '#dc2626', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}>Suppr.</button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Benchmark tiles ───────────────────────────────────────────────────────────

function BenchTiles({ bench, extra }: { bench?: Benchmark; extra?: BenchmarkExtra }) {
  if (!bench) return null
  return (
    <div style={{ display: 'flex', gap: '.55rem', flexWrap: 'wrap', marginBottom: '.9rem' }}>
      {bench.gross_margin_median != null && (
        <div className="situation-card neutral" style={{ minWidth: 90, textAlign: 'center' }}>
          <span className="situation-card-label">Marge brute médiane</span>
          <span className="situation-card-value" style={{ fontSize: '1.1rem' }}>{(bench.gross_margin_median * 100).toFixed(0)}%</span>
          <span className="situation-card-sub">secteur</span>
        </div>
      )}
      {bench.churn_median != null && (
        <div className="situation-card neutral" style={{ minWidth: 90, textAlign: 'center' }}>
          <span className="situation-card-label">Churn médian</span>
          <span className="situation-card-value" style={{ fontSize: '1.1rem' }}>{(bench.churn_median * 100).toFixed(1)}%</span>
          <span className="situation-card-sub">mensuel</span>
        </div>
      )}
      {bench.valorisation_multiple != null && (
        <div className="situation-card neutral" style={{ minWidth: 90, textAlign: 'center' }}>
          <span className="situation-card-label">Multiple EV/ARR</span>
          <span className="situation-card-value" style={{ fontSize: '1.1rem' }}>{bench.valorisation_multiple.toFixed(1)}x</span>
          <span className="situation-card-sub">valorisation</span>
        </div>
      )}
      {extra?.ltv_cac_ratio != null && (
        <div className="situation-card neutral" style={{ minWidth: 90, textAlign: 'center' }}>
          <span className="situation-card-label">LTV/CAC médian</span>
          <span className="situation-card-value" style={{ fontSize: '1.1rem' }}>{(extra.ltv_cac_ratio as number).toFixed(1)}x</span>
          <span className="situation-card-sub">unit economics</span>
        </div>
      )}
      {extra?.nrr != null && (
        <div className="situation-card neutral" style={{ minWidth: 90, textAlign: 'center' }}>
          <span className="situation-card-label">NRR médian</span>
          <span className="situation-card-value" style={{ fontSize: '1.1rem' }}>{(extra.nrr as number).toFixed(0)}%</span>
          <span className="situation-card-sub">rétention nette</span>
        </div>
      )}
      {extra?.cac_payback_months != null && (
        <div className="situation-card neutral" style={{ minWidth: 90, textAlign: 'center' }}>
          <span className="situation-card-label">CAC payback</span>
          <span className="situation-card-value" style={{ fontSize: '1.1rem' }}>{(extra.cac_payback_months as number).toFixed(0)}m</span>
          <span className="situation-card-sub">récupération CAC</span>
        </div>
      )}
      {extra?.growth_yoy != null && (
        <div className="situation-card neutral" style={{ minWidth: 90, textAlign: 'center' }}>
          <span className="situation-card-label">Croissance YoY</span>
          <span className="situation-card-value" style={{ fontSize: '1.1rem' }}>{(extra.growth_yoy as number).toFixed(0)}%</span>
          <span className="situation-card-sub">médiane secteur</span>
        </div>
      )}
      {bench.cac_median != null && (
        <div className="situation-card neutral" style={{ minWidth: 90, textAlign: 'center' }}>
          <span className="situation-card-label">CAC médian</span>
          <span className="situation-card-value" style={{ fontSize: '1.1rem' }}>{bench.cac_median.toFixed(0)}</span>
          <span className="situation-card-sub">acquisition client</span>
        </div>
      )}
      {bench.ltv_median != null && (
        <div className="situation-card neutral" style={{ minWidth: 90, textAlign: 'center' }}>
          <span className="situation-card-label">LTV médiane</span>
          <span className="situation-card-value" style={{ fontSize: '1.1rem' }}>{bench.ltv_median.toFixed(0)}</span>
          <span className="situation-card-sub">valeur client</span>
        </div>
      )}
    </div>
  )
}

// ── Beginner-mode analysis summary — human-readable, no jargon ───────────────

function BeginnerAnalysisSummary({ text, analysis }: { text: string; analysis?: Analysis }) {
  const kpis = analysis?.kpis
  const mc = analysis?.monte_carlo
  const phase = analysis?.phase

  const runway = kpis?.runway_months
  const survie = mc?.proba_survie_12m
  const cashAlert = kpis?.cash_out_alert

  // If we have structured data from kpis, show friendly tiles; fallback to markdown
  if (kpis) {
    const items: { emoji: string; label: string; value: string; hint: string }[] = []

    if (runway != null)
      items.push({
        emoji: runway < 3 ? '🔴' : runway < 6 ? '🟡' : '🟢',
        label: 'Votre autonomie financière',
        value: `${runway.toFixed(1)} mois`,
        hint: runway < 3 ? 'Urgent — il faut agir maintenant' : runway < 6 ? 'Vigilance — surveillez les dépenses' : 'Situation correcte pour votre stade',
      })

    if (survie != null)
      items.push({
        emoji: survie < 0.4 ? '🔴' : survie < 0.7 ? '🟡' : '🟢',
        label: 'Chance de survie à 1 an',
        value: `${(survie * 100).toFixed(0)}%`,
        hint: 'Calculé sur 1 000 simulations de votre situation',
      })

    if (cashAlert && cashAlert !== 'OK')
      items.push({
        emoji: cashAlert === 'CRITIQUE' ? '🚨' : '⚠️',
        label: 'Alerte trésorerie',
        value: cashAlert === 'CRITIQUE' ? 'Critique' : 'Attention requise',
        hint: cashAlert === 'CRITIQUE' ? 'Risque immédiat de manque de liquidités' : 'Surveillez de près vos dépenses',
      })

    if (phase)
      items.push({
        emoji: '📍',
        label: 'Où en êtes-vous',
        value: phase === 'SEED' ? 'Démarrage' : phase === 'TRACTION' ? 'Croissance' : 'Levée de fonds',
        hint: phase === 'SEED' ? 'Validez votre modèle avant de dépenser' : phase === 'TRACTION' ? 'Accélérez — le modèle fonctionne' : 'Préparez vos chiffres pour les investisseurs',
      })

    if (items.length > 0) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '.6rem' }}>
          {items.map((it, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '.6rem', padding: '.5rem .7rem', background: '#f8fafc', borderRadius: 8, border: '1px solid #e2e8f0' }}>
              <span style={{ fontSize: '1.1rem', flexShrink: 0 }}>{it.emoji}</span>
              <div>
                <div style={{ fontSize: '.78rem', color: '#64748b', fontWeight: 600 }}>{it.label}</div>
                <div style={{ fontSize: '.97rem', color: '#1e293b', fontWeight: 700, margin: '.1rem 0' }}>{it.value}</div>
                <div style={{ fontSize: '.74rem', color: '#94a3b8', lineHeight: 1.4 }}>{it.hint}</div>
              </div>
            </div>
          ))}
        </div>
      )
    }
  }

  // Fallback: strip technical headers, show readable paragraphs
  const simplified = text
    .replace(/### Données extraites\n?/g, '')
    .replace(/### KPIs\n?/g, '')
    .replace(/\*\*(Burn rate|Trésorerie|Revenu mensuel|Clients|Prix\/client|Secteur|Pays)\*\* : /g, '$1 : ')
    .trim()
  return <ReactMarkdown remarkPlugins={[remarkGfm]}>{simplified}</ReactMarkdown>
}

// ── Field-level dedup helpers (module-level — avoids TDZ inside markAnswered) ──

const FIELD_DEDUP_KW: Record<string, string[]> = {
  burn:    ['burn', 'dépens', 'depens', 'charges mensuel', 'coûts mensuel', 'couts mensuel', 'dépenses totales', 'depenses totales'],
  cash:    ['cash', 'trésorerie', 'tresorerie', 'solde', 'liquidit'],
  revenue: ['revenu mensuel', "chiffre d'affaires", 'chiffre d affaires', 'revenus mensuel'],
  clients: ['combien de clients', 'nombre de clients', 'abonnés', 'abonnes', 'clients actifs', 'clients payants'],
  prix:    ['prix ', 'tarif', 'ticket moyen', 'abonnement mensuel', 'prix moyen'],
  churn:   ['churn', 'attrition', 'perdez des clients', 'résiliation', 'resiliation', 'rétention', 'retention'],
  secteur: ['secteur', "secteur d'activit", 'secteur d activit', "domaine d'activit", "type d'activit", 'opère', 'dans quel domaine'],
  pays:    ['pays cibl', 'pays cible', 'marché géograph', 'marche geograph', 'dans quel pays', 'géograph'],
}

const fieldGroupOf = (q: string): string | null => {
  const ql = q.toLowerCase()
  for (const [field, kws] of Object.entries(FIELD_DEDUP_KW)) {
    if (kws.some(kw => ql.includes(kw))) return field
  }
  return null
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Home() {
  // Chat messages — only for free user-initiated conversation
  const [messages, setMessages] = useState<Message[]>([])
  // CFO Synthèse — single source of truth for the analysis zone narrative.
  // Always updated by the latest backend response; never overridden by stale state.
  const [analysisNarrative, setAnalysisNarrative] = useState('')
  const [input, setInput] = useState('')
  const [businessIdea, setBusinessIdea] = useState('')
  const [ideaSummary, setIdeaSummary] = useState('')
  const [entryPath, setEntryPath] = useState<EntryPath>('none')
  const [loading, setLoading] = useState(false)      // free chat only
  const [blockLoading, setBlockLoading] = useState(false) // block inline Q&A only
  // Per-block feedback shown inside each block after an answer
  const [blockFeedback, setBlockFeedback] = useState<Record<string, { text: string; type: 'success'|'warn'|'error'|'info' }>>({})
  // Stacked CFO analysis entries — initial narrative pinned, each new pipeline run appends
  const [analysisUpdates, setAnalysisUpdates] = useState<Array<{ text: string; label: string }>>([])
  // Global set of questions already shown to user — agent doesn't repeat, but frontend also tracks
  const [answeredQuestions, setAnsweredQuestions] = useState<Set<string>>(new Set())
  const markAnswered = (q: string) => {
    // Immediately update the ref — synchronous, visible in ALL closures right away.
    // This fixes the stale-closure bug where async callbacks ran before useState settled.
    const field = fieldGroupOf(q)
    if (field) answeredFieldsRef.current.add(field)
    answeredFieldsRef.current.add(q) // also track by exact text for non-field questions

    setAnsweredQuestions(prev => new Set([...prev, q]))
    // Evict ALL same-field questions from the accumulated list so a rephrased
    // duplicate of the answered question never resurfaces in the block on the next turn.
    setValidation(prev => {
      if (!prev) return prev
      if (!field) return prev
      const matchedKws = FIELD_DEDUP_KW[field]
      return {
        ...prev,
        questions_to_ask: (prev.questions_to_ask || []).filter(
          existing => existing === q ? false : !matchedKws.some(kw => existing.toLowerCase().includes(kw))
        ),
      }
    })
  }
  const [whatifMode, setWhatifMode] = useState(false)
  const [expertMode, setExpertMode] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [analysis, setAnalysis] = useState<Analysis | undefined>()
  const [ctx, setCtx] = useState<FinancialContext | undefined>()
  const [validation, setValidation] = useState<Validation | undefined>()
  const [bench, setBench] = useState<Benchmark | undefined>()
  const [extra, setExtra] = useState<BenchmarkExtra | undefined>()
  const [benchText, setBenchText] = useState('')
  const [conversations, setConversations] = useState<AppState['conversations']>([])
  const [a2a, setA2a] = useState<A2AState | undefined>()
  const [a2aHistory, setA2aHistory] = useState<Array<{ snapshot: A2AState; time: number }>>([])
  const [expandedA2A, setExpandedA2A] = useState<Set<number>>(new Set())
  const [a2aPublishTime, setA2aPublishTime] = useState<number | undefined>()
  const [a2aElapsed, setA2aElapsed] = useState(0)
  const [inputFlash, setInputFlash] = useState(false)
  // debug
  const [debugSource, setDebugSource] = useState('')
  const [debugLastResponse, setDebugLastResponse] = useState('')

  // Which archived (non-last) analysis cards are expanded
  const [expandedUpdates, setExpandedUpdates] = useState<Set<number>>(new Set())
  const toggleUpdateExpand = (idx: number) =>
    setExpandedUpdates(prev => { const s = new Set(prev); s.has(idx) ? s.delete(idx) : s.add(idx); return s })

  // Chat panel resize state (percent of total width)
  const [chatWidth, setChatWidth] = useState(35)
  const isDragging = useRef(false)
  const bodyRef = useRef<HTMLDivElement>(null)

  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const csvInputRef = useRef<HTMLInputElement>(null)
  const autoMsgRef = useRef<string | null>(null)
  const autoTriggeredRef = useRef(false)
  // Timing-safe answered-field tracker — useRef so mutations are immediately visible
  // in all async closures (no stale closure issue like useState has).
  const answeredFieldsRef = useRef<Set<string>>(new Set())
  const [stateLoaded, setStateLoaded] = useState(false)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  // Persist analysisUpdates to localStorage whenever they change
  useEffect(() => {
    if (analysisUpdates.length > 0) {
      try { localStorage.setItem('cfo_analysis_updates', JSON.stringify(analysisUpdates)) } catch { /* quota */ }
    }
  }, [analysisUpdates])

  // Persist answeredQuestions so blocks don't repeat after refresh
  useEffect(() => {
    if (answeredQuestions.size > 0) {
      try { localStorage.setItem('cfo_answered_questions', JSON.stringify([...answeredQuestions])) } catch { /* quota */ }
    }
  }, [answeredQuestions])

  // Chat resize — drag handle between analysis-zone and live-zone
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isDragging.current || !bodyRef.current) return
      const rect = bodyRef.current.getBoundingClientRect()
      const rightPct = Math.round((1 - (e.clientX - rect.left) / rect.width) * 100)
      setChatWidth(Math.max(20, Math.min(58, rightPct)))
    }
    const onUp = () => { isDragging.current = false; document.body.style.cursor = '' }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  }, [])

  useEffect(() => {
    const { idea, summary, track } = getIdeationContextFromStorage()
    const sourceParts: string[] = []
    if (typeof window !== 'undefined') {
      if (localStorage.getItem('startwise_summary')) sourceParts.push('startwise_summary')
      if (localStorage.getItem('sw_ideation_summary')) sourceParts.push('sw_ideation_summary')
      if (localStorage.getItem('sw_ideation_data')) sourceParts.push('sw_ideation_data')
      if (track === 'startup') sourceParts.push('startup_track')
    }
    setDebugSource(sourceParts.join(' | ') || 'none')
    setBusinessIdea(idea)
    setIdeaSummary(summary)
    // Seed the synthesis card with the ideation fallback ONLY when there is no
    // real backend narrative yet. Once the backend responds this will be overwritten.
    if (!analysisNarrative) {
      const fallback = composeIdeaNarrative(idea, summary, expertMode)
      if (fallback) setAnalysisNarrative(fallback)
    }
    if (summary && track !== 'startup') setEntryPath('ideation')
    else if (idea || track === 'startup') setEntryPath('audit')
    updateWorkflowStatus({ viability_assessment: 'available' })
  }, [expertMode]) // intentionally omit analysisNarrative — we only seed once on mount

  useEffect(() => {
    getState().then(data => {
      const hasExistingSession = !!(data.messages?.length || data.analysis?.kpis)
      // Restore chat messages — filter out raw ideation context messages
      if (data.messages?.length) {
        const chatMsgs = data.messages.filter((m: Message) =>
          m.role !== 'user' ||
          (!m.content.includes('## Business Idea') &&
           !m.content.includes("Contexte issu de l'idéation") &&
           !m.content.includes('Mon projet de startup :') &&
           !m.content.includes('## Key Insights') &&
           !m.content.includes('(contexte bloc:'))  // filter out block-answer messages
        )
        const sanitized = chatMsgs.filter((m: Message) => {
          if (m.role !== 'assistant') return true
          const c = (m.content || '').toLowerCase()
          return !(
            c.includes('## idée reçue') ||
            c.includes('## idee recue') ||
            c.includes('## pré-analyse cfo') ||
            c.includes('## pre-analyse cfo')
          )
        })
        setMessages(sanitized)
        // Recover narrative from saved messages only if we have nothing yet
        const recovered = extractNarrativeFromMessages(sanitized)
        if (recovered) setAnalysisNarrative(recovered)
      }
      // preanalysis_text is the most reliable saved narrative — always prefer it
      if ((data.preanalysis_text as string | undefined)?.trim()) {
        setAnalysisNarrative((data.preanalysis_text as string).trim())
      }
      // ── Step 1: Restore answered questions FIRST (synchronous ref mutation) ──
      // answeredFieldsRef must be populated before we filter validation below,
      // so filterDataQuestions immediately has the correct answered-field set.
      try {
        const savedAQ = localStorage.getItem('cfo_answered_questions')
        if (savedAQ) {
          const arr = JSON.parse(savedAQ) as string[]
          if (Array.isArray(arr) && arr.length) {
            setAnsweredQuestions(new Set(arr))
            arr.forEach(q => {
              answeredFieldsRef.current.add(q)
              const f = fieldGroupOf(q)
              if (f) answeredFieldsRef.current.add(f)
            })
          }
        }
      } catch { /* ignore */ }

      // ── Step 2: Restore ctx / validation / analysis (with filtering) ──────
      // Restore financial context — fall back to localStorage cache if backend lost state
      if (data.financial_context) {
        setCtx(data.financial_context as FinancialContext)
      } else {
        try {
          const c = localStorage.getItem('cfo_ctx_cache')
          if (c) setCtx(JSON.parse(c) as FinancialContext)
        } catch { /* ignore */ }
      }
      // Restore validation — filter questions through answeredFieldsRef (now populated)
      // so questions that were already answered don't show on reload.
      {
        const rawV = data.validation
          ? (data.validation as Validation)
          : (() => { try { const s = localStorage.getItem('cfo_validation_cache'); return s ? JSON.parse(s) as Validation : null } catch { return null } })()
        if (rawV) {
          const filteredQs = filterDataQuestions(rawV.questions_to_ask || [])
          setValidation({ ...rawV, questions_to_ask: filteredQs })
        }
      }
      // Restore analysis — fall back to localStorage cache if backend lost state
      // (pickle schema change after deploy = silent _default_state() with no kpis)
      if (data.analysis && (data.analysis as Analysis).kpis) {
        setAnalysis(data.analysis as Analysis)
      } else {
        try {
          const cached = localStorage.getItem('startwise_financial_data')
          if (cached) {
            const parsed = JSON.parse(cached) as Analysis
            if (parsed?.kpis) setAnalysis(parsed)
          }
        } catch { /* ignore */ }
      }
      // Restore stacked analysis update cards from localStorage
      try {
        const saved = localStorage.getItem('cfo_analysis_updates')
        if (saved) {
          const updates = JSON.parse(saved) as Array<{ text: string; label: string }>
          if (Array.isArray(updates) && updates.length) setAnalysisUpdates(updates)
        }
      } catch { /* ignore */ }

      if (data.bench) setBench(data.bench)
      if (data.bench_extra) setExtra(data.bench_extra)
      if (data.bench_text) setBenchText(data.bench_text)
      if (data.conversations) setConversations(data.conversations)
      // Restore a2aPublishTime if recent enough to still be polling
      if (data.a2a_publish_time) {
        const age = Date.now() / 1000 - (data.a2a_publish_time as number)
        if (age < 300) setA2aPublishTime(data.a2a_publish_time as number)
      }
      if (data.whatif_mode) setWhatifMode(data.whatif_mode)

      // Prefetch benchmarks early when we have sector context but no bench data yet
      if (!data.bench) {
        const { idea, summary } = getIdeationContextFromStorage()
        const sectorHint = (data.financial_context?.secteur) ||
          (idea + ' ' + summary).match(/\b(SaaS|FinTech|EdTech|HealthTech|E-commerce|Retail|Logistique|AgriTech|IoT|Marketplace)\b/i)?.[0] || ''
        if (sectorHint) {
          prefetchBenchmarks(sectorHint, data.financial_context?.pays || 'TN').then(res => {
            if (res?.bench) {
              setBench(res.bench)
              if (res.bench_extra) setExtra(res.bench_extra)
              if (res.bench_text) setBenchText(res.bench_text)
            }
          }).catch(() => {/* silent */})
        }
      }

      // Auto-trigger initial agent pass when any startup context exists but analysis is still empty.
      // Covers both: ideation track (summary filled) and existing-startup track (product_audit_draft).
      const { idea, summary } = getIdeationContextFromStorage()
      const hasAnalysisAlready = !!(data.analysis?.kpis ||
        (() => { try { const c = localStorage.getItem('startwise_financial_data'); return c && JSON.parse(c)?.kpis } catch { return false } })())
      const hasContext = !!summary || !!idea
      if (hasContext && !hasAnalysisAlready && !autoTriggeredRef.current) {
        const msg = idea
          ? `Mon projet de startup : ${idea}.\n\nContexte issu de l'idéation : ${summary.slice(0, 700)}`
          : summary.slice(0, 700)
        autoMsgRef.current = msg
      }

      // Immediately fetch A2A state if a completed analysis exists — the investment
      // agent response persists in the CommAgent even after the 5-min polling window.
      // Without this, users who reload the page lose their investment insights.
      if (hasAnalysisAlready) {
        getA2AState().then(a2aData => {
          if (a2aData?.available && (a2aData as A2AState).investment_rating) {
            setA2a(a2aData as A2AState)
          }
        }).catch(() => { /* silent — A2A bus may not be running */ })
      }

      setStateLoaded(true)
    }).catch(() => setStateLoaded(true))
  }, [])

  // Fire auto-analysis once state is loaded (uses block answer path — no chat pollution)
  useEffect(() => {
    if (stateLoaded && autoMsgRef.current) {
      const msg = autoMsgRef.current
      autoMsgRef.current = null
      autoTriggeredRef.current = true
      handleBlockAnswer(msg)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateLoaded])

  const pollA2A = useCallback(async () => {
    try { setA2a(await getA2AState()) } catch { /* */ }
  }, [])

  useEffect(() => {
    if (!a2aPublishTime) return
    const interval = setInterval(() => {
      const elapsed = Math.floor(Date.now() / 1000 - a2aPublishTime)
      setA2aElapsed(elapsed)
      if (elapsed < 300) pollA2A()
      else { clearInterval(interval); setA2aPublishTime(undefined) }
    }, 2000)
    return () => clearInterval(interval)
  }, [a2aPublishTime, pollA2A])

  // ── Shared state updater after any analysis response ──────────────────────

  // Merge new questions into existing list, deduplicating by FIELD (not just exact text).
  // If the existing list already has a question about "burn", don't add another burn question
  // — even if it's phrased differently. This prevents same-field duplicates within a block.
  const mergeQuestions = (existing: string[], incoming: string[]): string[] => {
    const result = [...existing]
    const existingFields = new Set(existing.map(fieldGroupOf).filter(Boolean) as string[])
    for (const q of incoming) {
      if (result.includes(q)) continue               // exact duplicate
      const field = fieldGroupOf(q)
      if (field && existingFields.has(field)) continue  // same-field duplicate (different phrasing)
      result.push(q)
      if (field) existingFields.add(field)
    }
    return result
  }

  // Filter backend questions before surfacing them in blocks:
  // - skip questions about fields already known from ideation context (sector)
  // - skip questions already answered this session
  // Uses answeredFieldsRef (not answeredQuestions state) so async callbacks always
  // see the latest value — no stale closure issue.
  const filterDataQuestions = (qs: string[]): string[] => {
    return qs.filter(q => {
      if (!q) return false
      // Exact-text match (catches non-field questions too)
      if (answeredFieldsRef.current.has(q)) return false
      const field = fieldGroupOf(q)
      // Field-level match — catches same concept rephrased differently
      if (field && answeredFieldsRef.current.has(field)) return false
      const ql = q.toLowerCase()
      // Sector already embedded in ideation summary — don't ask again
      if (ideaSummary && FIELD_DEDUP_KW.secteur.some(kw => ql.includes(kw))) return false
      // Country already known from context
      if (ctx?.pays && FIELD_DEDUP_KW.pays.some(kw => ql.includes(kw))) return false
      return true
    })
  }

  const applyAnalysisData = (data: Record<string, unknown>) => {
    if (data.analysis) setAnalysis(data.analysis as Analysis)
    if (data.financial_context) setCtx(data.financial_context as FinancialContext)
    if (data.validation) {
      const v = data.validation as Validation
      // Filter BOTH sources through filterDataQuestions:
      // - data.questions    = agent's clarification questions (LLM generated)
      // - v.questions_to_ask = validator's questions (regenerated every turn for missing fields)
      // Without filtering v.questions_to_ask, the validator re-injects already-answered
      // questions (sector, burn, etc.) on every response — they never disappear.
      const agentQs = filterDataQuestions((data.questions as string[] | undefined) || [])
      const validatorQs = filterDataQuestions(v.questions_to_ask || [])
      setValidation({ ...v, questions_to_ask: mergeQuestions(validatorQs, agentQs) })
    }
    if (data.bench) setBench(data.bench as Benchmark)
    if (data.bench_extra) setExtra(data.bench_extra as BenchmarkExtra)
    if (data.bench_text) setBenchText(data.bench_text as string)
    if (data.a2a_publish_time) {
      // Archive previous investment recommendation before the new analysis clears it
      if (a2a?.investment_rating) {
        setA2aHistory(prev => [...prev, { snapshot: a2a, time: Date.now() }])
        setA2a(undefined)
      }
      setA2aPublishTime(data.a2a_publish_time as number); setA2aElapsed(0)
    }
    // Build the narrative: analysis text + benchmark commentary.
    // NEVER overwrite the initial narrative — push as a new stacked entry below.
    const narrative = (data.data_text as string || '') +
      (data.bench_text ? '\n\n' + data.bench_text : '')
    if (narrative.trim()) {
      const label = (data as Record<string, unknown>).analysis && (data as Record<string, unknown>).analysis && ((data as {analysis?: {kpis?: unknown}}).analysis?.kpis)
        ? 'Analyse CFO complète'
        : 'Mise à jour CFO'
      setAnalysisUpdates(prev => [...prev, { text: narrative, label }])
    }
    localStorage.setItem('startwise_financial_data', JSON.stringify(data.analysis))
    if (data.bench) localStorage.setItem('startwise_market_data', JSON.stringify(data.bench))
    // Also cache context + validation so blocks restore correctly when backend
    // session is lost (pickle schema change or Redis TTL expiry).
    try {
      if (data.financial_context) localStorage.setItem('cfo_ctx_cache', JSON.stringify(data.financial_context))
      if (data.validation) localStorage.setItem('cfo_validation_cache', JSON.stringify(data.validation))
    } catch { /* quota */ }
    markStepAsCompleted('viability_assessment')
  }

  // ── Block answer — user responds to an agent question inside a block ───────
  // Uses blockLoading (not loading) so the free chat spinner never fires.
  // blockId: which block triggered the answer — result shown inline inside that block.

  const handleBlockAnswer = async (msg: string, blockId?: string) => {
    if (!msg || blockLoading) return
    setBlockLoading(true)
    if (blockId) setBlockFeedback(prev => ({ ...prev, [blockId]: { text: '...', type: 'info' as const } }))
    try {
      // silent=true → backend won't store this in session chat history.
      const data = await sendMessage(msg, true)
      setDebugLastResponse(`type=${data.type} | hasKpis=${!!(data.analysis?.kpis)} | replyLen=${String(data.reply || data.data_text || '').length}`)

      if (data.type === 'analysis' && data.analysis?.kpis) {
        // Full pipeline with KPIs — update everything including narrative
        applyAnalysisData(data)
        if (blockId) setBlockFeedback(prev => ({ ...prev, [blockId]: { text: '✓ Analyse complète générée — consultez les blocs ci-dessus.', type: 'success' as const } }))
      } else if (data.type === 'analysis') {
        // Partial data — backend ran but produced no KPIs (agent asked for clarification).
        // Only update context/validation; do NOT push to analysisUpdates (no real analysis yet).
        // Keep existing analysis state intact to preserve block data from prior full runs.
        if ((data.analysis as Analysis)?.kpis) setAnalysis(data.analysis as Analysis)
        if (data.financial_context) setCtx(data.financial_context as FinancialContext)
        if (data.validation) {
          const v = data.validation as Validation
          const extraQs = filterDataQuestions((data.questions as string[] | undefined) || [])
          setValidation(extraQs.length
            ? { ...v, questions_to_ask: mergeQuestions(v.questions_to_ask || [], extraQs) }
            : v)
        }
        if (data.bench) setBench(data.bench as Benchmark)
        if (data.bench_extra) setExtra(data.bench_extra as BenchmarkExtra)
        if (data.bench_text) setBenchText(data.bench_text as string)
        const fctx = data.financial_context as FinancialContext | undefined
        const fields: string[] = []
        if (fctx?.burn_rate) fields.push(`burn rate: ${fctx.burn_rate}`)
        if (fctx?.cash_balance) fields.push(`trésorerie: ${fctx.cash_balance}`)
        if (fctx?.monthly_revenue) fields.push(`revenus: ${fctx.monthly_revenue}`)
        if (fctx?.n_clients) fields.push(`clients: ${fctx.n_clients}`)
        const ackText = fields.length ? `✓ Données reçues — ${fields.join(', ')}.` : '✓ Données reçues.'
        if (blockId) setBlockFeedback(prev => ({ ...prev, [blockId]: { text: ackText, type: 'success' as const } }))
      } else if (data.type === 'ideation_preanalysis') {
        // Initial CFO pre-analysis — fills the synthesis card.
        const reply = (data.reply || '') as string
        if (reply.trim()) setAnalysisNarrative(reply)
        if (blockId) setBlockFeedback(prev => ({ ...prev, [blockId]: { text: '✓ Contexte analysé.', type: 'success' as const } }))
      } else {
        // type=general — parser couldn't extract financial data.
        // NEVER overwrite analysisNarrative.
        if (data.financial_context) setCtx(data.financial_context as FinancialContext)
        if (data.validation) setValidation(data.validation as Validation)
        const reply = (data.reply || data.data_text || '') as string
        const isErrorFallback = !reply.trim() || reply.includes("n'ai pas pu traiter") || reply.length < 80
        const hint = isErrorFallback
          ? 'Reformulez avec un chiffre et une unité — ex: "Mon burn rate mensuel est 5 000 TND".'
          : reply.slice(0, 200)
        if (blockId) setBlockFeedback(prev => ({ ...prev, [blockId]: { text: hint, type: 'warn' as const } }))
      }
    } catch (err) {
      const errStr = String(err)
      console.error('[handleBlockAnswer]', err)
      setDebugLastResponse(`ERROR: ${errStr}`)
      if (blockId) setBlockFeedback(prev => ({ ...prev, [blockId]: { text: `Erreur réseau — Django :8000 ? (${errStr.slice(0,60)})`, type: 'error' as const } }))
    } finally {
      setBlockLoading(false)
    }
  }

  const handleBlockFileAnswer = async (file: File, contextLabel: string) => {
    if (!file || loading) return
    setLoading(true)
    try {
      if (file.name.toLowerCase().endsWith('.csv') || file.name.toLowerCase().endsWith('.txt')) {
        const text = await file.text()
        const values: string[] = []
        text.split('\n').forEach(line => {
          const parts = line.split(/[,;]/)
          const last = parts[parts.length - 1].trim().replace(/[^0-9.-]/g, '')
          if (last && !isNaN(Number(last))) values.push(last)
        })
        const payload = values.length > 0
          ? `Fichier (${file.name}) pour ${contextLabel}. Valeurs detectees: ${values.join(', ')}. Mets a jour mon analyse.`
          : `Fichier (${file.name}) pour ${contextLabel}. Contenu: ${text.slice(0, 3000)}. Mets a jour mon analyse.`
        const data = await sendMessage(payload)
        if (data.type === 'analysis' && data.analysis?.kpis) applyAnalysisData(data)
        else if (data.reply || data.data_text) setAnalysisNarrative((data.reply || data.data_text) as string)
        return
      }

      const data = await uploadFile(file)
      if (data.type === 'analysis' && data.analysis?.kpis) {
        applyAnalysisData(data)
      } else if (data.message) {
        setAnalysisNarrative(`${modeText(expertMode, 'Retour agent', 'Retour du CFO')}:\n\n${data.message as string}`)
      }
    } catch {
      // noop
    } finally {
      setLoading(false)
    }
  }

  // ── Chat send — user-initiated free conversation ───────────────────────────
  // Adds messages to the chat. If analysis is triggered, updates blocks silently
  // and shows a brief notification in the chat.

  const handleChatSend = async (text?: string) => {
    const msg = (text ?? input).trim()
    if (!msg || loading) return
    setInput('')
    setLoading(true)
    setMessages(prev => [...prev, { role: 'user', content: msg }])
    try {
      const data = await sendMessage(msg)
      const reply = (data.reply || data.data_text || '') as string
      const replyMsgType: Message['msgType'] =
        data.type === 'analysis' || data.type === 'ideation_onboarding' || data.type === 'general' || data.type === 'whatif'
          ? data.type
          : 'general'
      setMessages(prev => [...prev, { role: 'assistant', content: reply, msgType: replyMsgType }])
      // Silently sync analysis state so the left zone stays up to date
      if (data.type === 'analysis') {
        if (data.analysis?.kpis) applyAnalysisData(data)
        else {
          if (data.financial_context) setCtx(data.financial_context as FinancialContext)
          if (data.validation) setValidation(data.validation as Validation)
          if (data.bench) setBench(data.bench as Benchmark)
        }
      } else if (data.type === 'whatif' && data.analysis) {
        setAnalysis(data.analysis as Analysis)
      }
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Erreur lors de la requête.', msgType: 'general' }])
    } finally { setLoading(false) }
  }

  // Prefill the chat textarea (for what-if chips, suggestions, strategic prompts)
  const handlePrefillChat = (text: string) => {
    setInput(text)
    setInputFlash(true)
    setTimeout(() => setInputFlash(false), 800)
    textareaRef.current?.focus()
    textareaRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleChatSend() }
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
      a.style.display = 'none'; a.href = url
      a.download = `startwise_${new Date().toISOString().slice(0, 10)}.pdf`
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      setTimeout(() => URL.revokeObjectURL(url), 10000)
    } catch { alert("Erreur génération PDF — soumettez d'abord vos données financières.") }
  }

  const handleCsvUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ''
    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    // Binary formats: send to backend upload endpoint for proper extraction
    if (['pdf', 'docx', 'xlsx'].includes(ext)) {
      await handleBlockFileAnswer(file, 'historique des revenus mensuels pour saisonnalité')
      return
    }
    // Text formats (CSV, TXT, JSON): read locally and extract numbers
    const reader = new FileReader()
    reader.onload = ev => {
      const text = ev.target?.result as string
      const values: string[] = []
      text.split('\n').forEach(line => {
        const parts = line.split(/[,;:\t]/)
        const last = parts[parts.length - 1].trim().replace(/[^0-9.-]/g, '')
        if (last && !isNaN(Number(last))) values.push(last)
      })
      if (values.length > 0) {
        handleBlockAnswer(`Voici mes données mensuelles de revenus (fichier ${file.name}) : ${values.join(', ')} TND. Analyse la saisonnalité et mets à jour mes projections.`)
      } else {
        // No numbers extracted — send raw text for parser
        handleBlockAnswer(`Historique de revenus (${file.name}) : ${text.slice(0, 3000)}. Extrais les valeurs mensuelles et analyse la saisonnalité.`)
      }
    }
    reader.readAsText(file)
  }

  const handleNewConv = async () => {
    await newConversation()
    setMessages([]); setCtx(undefined); setValidation(undefined)
    setAnalysis(undefined); setBench(undefined); setExtra(undefined)
    setBenchText(''); setAnalysisNarrative('')
    setA2a(undefined); setA2aHistory([]); setA2aPublishTime(undefined); setWhatifMode(false)
    setAnalysisUpdates([])
    localStorage.removeItem('cfo_analysis_updates')
    setAnsweredQuestions(new Set())
    answeredFieldsRef.current.clear()
    localStorage.removeItem('cfo_answered_questions')
    localStorage.removeItem('startwise_financial_data')
    localStorage.removeItem('startwise_market_data')
    localStorage.removeItem('cfo_ctx_cache')
    localStorage.removeItem('cfo_validation_cache')
    const updated = await getState()
    setConversations(updated.conversations || [])
    setShowHistory(false)
  }

  const handleRestoreConv = async (id: string) => {
    await restoreConversation(id)
    const updated = await getState()
    if (updated.messages?.length) setMessages(updated.messages)
    if (updated.analysis && (updated.analysis as Analysis).kpis) {
      setAnalysis(updated.analysis as Analysis)
      // Fetch A2A state — investment insights persist in CommAgent after analysis
      getA2AState().then(a2aData => {
        if (a2aData?.available && (a2aData as A2AState).investment_rating) setA2a(a2aData as A2AState)
      }).catch(() => { /* silent */ })
    }
    if (updated.financial_context) setCtx(updated.financial_context)
    if (updated.validation) {
      const v = updated.validation as Validation
      const filteredQs = filterDataQuestions(v.questions_to_ask || [])
      setValidation({ ...v, questions_to_ask: filteredQs })
    }
    if (updated.bench) setBench(updated.bench)
    if (updated.bench_extra) setExtra(updated.bench_extra)
    if (updated.bench_text) setBenchText(updated.bench_text)
    setConversations(updated.conversations || [])
    setShowHistory(false)
  }

  const handleDeleteConv = async (id: string) => {
    await deleteConversation(id)
    const updated = await getState()
    setConversations(updated.conversations || [])
  }

  const hasAnalysis = !!(analysis?.kpis)

  // Build the raw missing-fields list, then filter out fields that are EITHER:
  // a) already in ctx (parser extracted them — validator just hasn't seen the fresh ctx)
  // b) already answered by the user this session (answeredFieldsRef tracks by field group)
  // Without this, the hardcoded block field inputs re-appear every time the validator
  // regenerates missing_critical, even after the user already answered those fields.
  const _rawMissing: string[] = validation?.missing_critical?.length
    ? validation.missing_critical
    : !hasAnalysis && entryPath === 'ideation'
      ? Object.values(BLOCK_FIELD_MAP).flat()
      : []
  const missing = _rawMissing.filter(m => {
    // Field name → [ctx getter, answeredFieldsRef group key]
    const checks: Array<[string, (() => boolean) | null, string]> = [
      ['burn_rate',       () => ctx?.burn_rate != null,        'burn'],
      ['cash_balance',    () => ctx?.cash_balance != null,     'cash'],
      ['monthly_revenue', () => ctx?.monthly_revenue != null,  'revenue'],
      ['n_clients',       () => ctx?.n_clients != null,        'clients'],
      ['prix_client',     () => ctx?.prix_client != null,      'prix'],
      ['churn_rate',      () => ctx?.churn_rate != null,       'churn'],
    ]
    for (const [prefix, ctxCheck, group] of checks) {
      if (m === prefix || m.startsWith(prefix)) {
        if (ctxCheck?.()) return false                      // ctx has the value
        if (answeredFieldsRef.current.has(group)) return false  // user answered it
      }
    }
    return true
  })
  // Filter out already-answered questions — shared across all blocks (one CFO context)
  const allQuestions = (validation?.questions_to_ask || []).filter(q => !answeredQuestions.has(q))
  const routedQuestions = routeQuestions(allQuestions)
  const phrase = confidencePhrase(analysis, validation)
  const showAgentZone = !!(a2a || a2aPublishTime)
  const hasIdeaContext = !!(businessIdea.trim() || ideaSummary.trim())

  return (
    <div className="cfo-page">

      {/* ── Top bar ────────────────────────────────────────────────────────── */}
      <div className="cfo-top-bar">
        <div className="cfo-top-left">
          <span className="cfo-title">StartWise CFO</span>
          <span className="cfo-phrase">
            {modeText(
              expertMode,
              `Mode expert - ${phrase}`,
              `Mode debutant - ${phrase}`,
            )}
          </span>
        </div>

        <div className="expert-toggle">
          <button className={`expert-btn ${!expertMode ? 'active' : ''}`} onClick={() => setExpertMode(false)}>Débutant</button>
          <button className={`expert-btn ${expertMode ? 'active' : ''}`} onClick={() => setExpertMode(true)}>Expert</button>
        </div>

        <div className="cfo-top-right">
          <button className={`act-btn ${whatifMode ? 'active' : ''}`} onClick={handleToggleWhatif}>
            <FlaskConical style={{ width: 12, height: 12 }} />
            {whatifMode ? 'What-If actif' : 'What-If'}
          </button>
          {hasAnalysis && (
            <button className="act-btn" onClick={handlePdf}>
              <Download style={{ width: 12, height: 12 }} />PDF
            </button>
          )}
          <button className="act-btn" onClick={() => setShowHistory(true)}>
            <History style={{ width: 12, height: 12 }} />Historique
          </button>
        </div>
      </div>

      {/* ── Two-column body ─────────────────────────────────────────────────── */}
      <div className="cfo-body" ref={bodyRef}>

        {/* ═══ ANALYSIS ZONE (left side, flex grows) ══════════════════════════ */}
        <div className="analysis-zone" style={{ flex: 100 - chatWidth }}>

          {hasIdeaContext && (
            <div className="cfo-synthese-card">
              <div className="cfo-synthese-header">
                <FileText style={{ width: 14, height: 14, flexShrink: 0 }} />
                <span className="cfo-synthese-title">
                  {modeText(expertMode, 'Analyse initiale depuis Business Idea', 'Point de depart de votre idee')}
                </span>
                <span className="cfo-synthese-badge">
                  {modeText(expertMode, 'Contexte initial', 'Avant les questions')}
                </span>
              </div>
              <div className="cfo-synthese-body md">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {composeIdeaNarrative(businessIdea, ideaSummary, expertMode)}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {/* CFO Synthèse initiale — pinned, never replaced */}
          <div className="cfo-synthese-card">
            <div className="cfo-synthese-header">
              <FileText style={{ width: 14, height: 14, flexShrink: 0 }} />
              <span className="cfo-synthese-title">
                {modeText(expertMode, 'Pré-analyse CFO', 'Première lecture de votre CFO')}
              </span>
              <span className="cfo-synthese-badge">
                {analysisNarrative ? modeText(expertMode, 'Pré-analyse', 'En cours') : modeText(expertMode, 'Attente données', 'En attente')}
              </span>
            </div>
            <div className="cfo-synthese-body md">
              {blockLoading && !analysisNarrative ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '.6rem', color: '#3b82f6', fontSize: '.84rem' }}>
                  <span className="spinner" style={{ width: 14, height: 14 }} />
                  <span>Votre CFO analyse le contexte…</span>
                </div>
              ) : (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {analysisNarrative || "Soumettez vos données financières pour démarrer l'analyse."}
                </ReactMarkdown>
              )}
            </div>
          </div>

          {/* CFO analyses — latest always visible, previous archived/foldable */}
          {analysisUpdates.length > 0 && (() => {
            const latest = analysisUpdates[analysisUpdates.length - 1]
            const archived = analysisUpdates.slice(0, -1)
            return (
              <>
                {/* Archive section — all but the latest, collapsed by default */}
                {archived.length > 0 && (
                  <div className="cfo-synthese-card" style={{ borderLeft: '3px solid #cbd5e1' }}>
                    <button
                      onClick={() => toggleUpdateExpand(-1)}
                      style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '.6rem', padding: '.65rem 1rem', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left' }}
                    >
                      <History style={{ width: 13, height: 13, color: '#94a3b8', flexShrink: 0 }} />
                      <span style={{ flex: 1, fontSize: '.8rem', fontWeight: 600, color: '#64748b' }}>
                        {modeText(expertMode, `${archived.length} analyse${archived.length > 1 ? 's' : ''} précédente${archived.length > 1 ? 's' : ''}`, `${archived.length} mise${archived.length > 1 ? 's' : ''} à jour précédente${archived.length > 1 ? 's' : ''}`)}
                      </span>
                      <span style={{ fontSize: '.7rem', color: '#94a3b8' }}>
                        {expandedUpdates.has(-1) ? '▲ Réduire' : '▼ Voir l\'historique'}
                      </span>
                    </button>
                    {expandedUpdates.has(-1) && (
                      <div style={{ borderTop: '1px solid #f1f5f9', display: 'flex', flexDirection: 'column', gap: '.5rem', padding: '.7rem 1rem' }}>
                        {archived.map((entry, idx) => (
                          <div key={idx} style={{ borderRadius: 8, border: '1px solid #e2e8f0', overflow: 'hidden' }}>
                            <button
                              onClick={() => toggleUpdateExpand(idx)}
                              style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '.5rem', padding: '.5rem .75rem', background: '#f8fafc', border: 'none', cursor: 'pointer', textAlign: 'left' }}
                            >
                              <CheckCircle2 style={{ width: 12, height: 12, color: '#94a3b8', flexShrink: 0 }} />
                              <span style={{ flex: 1, fontSize: '.76rem', fontWeight: 600, color: '#64748b' }}>
                                {expertMode ? entry.label : `Analyse ${idx + 1}`}
                              </span>
                              <span style={{ fontSize: '.65rem', color: '#94a3b8' }}>{expandedUpdates.has(idx) ? '▲' : '▼'}</span>
                            </button>
                            {expandedUpdates.has(idx) && (
                              <div className="cfo-synthese-body md" style={{ borderTop: '1px solid #e2e8f0', fontSize: '.8rem' }}>
                                {expertMode
                                  ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{entry.text}</ReactMarkdown>
                                  : <BeginnerAnalysisSummary text={entry.text} analysis={analysis} />}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Latest analysis — always expanded */}
                <div className="cfo-synthese-card" style={{ borderLeft: '3px solid #6366f1' }}>
                  <div className="cfo-synthese-header">
                    <CheckCircle2 style={{ width: 14, height: 14, flexShrink: 0, color: '#6366f1' }} />
                    <span className="cfo-synthese-title">
                      {expertMode ? latest.label : 'Dernière analyse CFO'}
                    </span>
                    <span className="cfo-synthese-badge" style={{ background: '#ede9fe', color: '#7c3aed' }}>
                      {modeText(expertMode, 'Dernière', 'À jour')}
                    </span>
                  </div>
                  <div className="cfo-synthese-body md">
                    {expertMode
                      ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{latest.text}</ReactMarkdown>
                      : <BeginnerAnalysisSummary text={latest.text} analysis={analysis} />}
                  </div>
                </div>
              </>
            )
          })()}

          {blockLoading && analysisNarrative && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '.55rem', color: '#6366f1', fontSize: '.8rem', padding: '.4rem .6rem' }}>
              <span className="spinner" style={{ width: 12, height: 12 }} />
              <span>CFO met à jour l'analyse…</span>
            </div>
          )}

          {/* Block 1 — Situation globale */}
          <div className="cfo-block">
            <div className="block-header">
              <span className="block-number">1</span>
              <span className="block-title">{expertMode ? 'Situation Globale' : 'Où en est votre startup ?'}</span>
              <span className={`block-status ${hasAnalysis ? 'block-status-ok' : 'block-status-locked'}`}>
                {hasAnalysis
                  ? modeText(expertMode, 'Actif', 'Disponible')
                  : modeText(expertMode, 'En attente', 'A remplir')}
              </span>
            </div>
            <div className="block-body">
              <Block1
                analysis={analysis} expertMode={expertMode}
                routedQuestions={routedQuestions} missing={missing}
                onAnswer={(msg) => handleBlockAnswer(msg, 'block1')}
                onFileAnswer={handleBlockFileAnswer}
                onAnswered={markAnswered}
                feedback={blockFeedback['block1']}
                isLoading={blockLoading}
              />
            </div>
          </div>

          {/* Block 2 — KPIs */}
          <div className={`cfo-block ${!hasAnalysis ? 'locked' : ''}`}>
            <div className={`block-header ${!hasAnalysis ? 'locked' : ''}`}>
              <span className={`block-number ${!hasAnalysis ? 'locked' : ''}`}>2</span>
              <span className={`block-title ${!hasAnalysis ? 'locked' : ''}`}>
                {expertMode ? 'KPIs & Métriques Business' : 'Vos chiffres clés'}
              </span>
              <span className={`block-status ${hasAnalysis ? (missing.length ? 'block-status-partial' : 'block-status-ok') : 'block-status-locked'}`}>
                {hasAnalysis
                  ? (missing.length
                    ? modeText(expertMode, 'Partiel', 'A completer')
                    : modeText(expertMode, 'Complet', 'Complet'))
                  : modeText(expertMode, 'En attente', 'A remplir')}
              </span>
            </div>
            <div className="block-body">
              {hasAnalysis ? (
                <>
                  {!expertMode && (
                    <p style={{ fontSize: '.81rem', color: '#64748b', marginBottom: '.9rem', lineHeight: 1.55 }}>
                      Calculés automatiquement à partir de vos données. Plus vous en ajoutez, plus ils sont précis.
                    </p>
                  )}
                  <KPICards kpis={analysis?.kpis} mc={analysis?.monte_carlo} bench={bench} extra={extra} phase={analysis?.phase} expertMode={expertMode} />
                  <BlockInlineQA
                    blockId="block2" routedQuestions={routedQuestions}
                    missing={missing} expertMode={expertMode}
                    onAnswer={(msg) => handleBlockAnswer(msg, 'block2')}
                    onFileAnswer={handleBlockFileAnswer}
                    onAnswered={markAnswered}
                    feedback={blockFeedback['block2']} isLoading={blockLoading}
                  />
                </>
              ) : (
                <p className="locked-hint">
                  <Lock style={{ width: 14, height: 14, flexShrink: 0 }} />
                  {expertMode
                    ? 'Requis : burn_rate + cash_balance + monthly_revenue minimum.'
                    : "Actif après votre première analyse. Renseignez vos données dans le bloc 1."}
                </p>
              )}
            </div>
          </div>

          {/* Block 3 — Scénarios */}
          <div className={`cfo-block ${!hasAnalysis ? 'locked' : ''}`}>
            <div className={`block-header ${!hasAnalysis ? 'locked' : ''}`}>
              <span className={`block-number ${!hasAnalysis ? 'locked' : ''}`}>3</span>
              <span className={`block-title ${!hasAnalysis ? 'locked' : ''}`}>
                {expertMode ? 'Projections — 3 Scénarios' : 'Et si les choses changent ?'}
              </span>
              <span className={`block-status ${hasAnalysis ? 'block-status-ok' : 'block-status-locked'}`}>
                {hasAnalysis
                  ? modeText(expertMode, 'Actif', 'Disponible')
                  : modeText(expertMode, 'En attente', 'A remplir')}
              </span>
            </div>
            <div className="block-body">
              {hasAnalysis ? (
                <>
                  {!expertMode && (
                    <p style={{ fontSize: '.81rem', color: '#64748b', marginBottom: '.9rem', lineHeight: 1.55 }}>
                      Votre CFO a simulé 3 trajectoires : si tout va bien, dans la normale, et si ça se complique.
                    </p>
                  )}
                  <ScenariosChart scenarios={analysis?.scenarios} />
                  <BlockInlineQA
                    blockId="block3" routedQuestions={routedQuestions}
                    missing={missing} expertMode={expertMode}
                    onAnswer={(msg) => handleBlockAnswer(msg, 'block3')}
                    onFileAnswer={handleBlockFileAnswer}
                    onAnswered={markAnswered}
                    feedback={blockFeedback['block3']} isLoading={blockLoading}
                  />
                </>
              ) : (
                <p className="locked-hint">
                  <Lock style={{ width: 14, height: 14, flexShrink: 0 }} />
                  {expertMode ? 'Requiert : scenario_projection().' : 'Disponible après la première analyse.'}
                </p>
              )}
            </div>
          </div>

          {/* Block 4 — Monte Carlo */}
          <div className={`cfo-block ${!hasAnalysis ? 'locked' : ''}`}>
            <div className={`block-header ${!hasAnalysis ? 'locked' : ''}`}>
              <span className={`block-number ${!hasAnalysis ? 'locked' : ''}`}>4</span>
              <span className={`block-title ${!hasAnalysis ? 'locked' : ''}`}>
                {expertMode ? 'Monte Carlo — Distribution Runway' : 'Simulation de survie ×1 000'}
              </span>
              <span className={`block-status ${hasAnalysis ? 'block-status-ok' : 'block-status-locked'}`}>
                {hasAnalysis
                  ? modeText(expertMode, 'Actif', 'Disponible')
                  : modeText(expertMode, 'En attente', 'A remplir')}
              </span>
            </div>
            <div className="block-body">
              {hasAnalysis ? (
                <>
                  <MonteCarloChart mc={analysis?.monte_carlo} />
                  <MonteCarloSummary mc={analysis?.monte_carlo} expertMode={expertMode} onPrefillChat={handlePrefillChat} />
                  <BlockInlineQA
                    blockId="block4" routedQuestions={routedQuestions}
                    missing={missing} expertMode={expertMode}
                    onAnswer={(msg) => handleBlockAnswer(msg, 'block4')}
                    onFileAnswer={handleBlockFileAnswer}
                    onAnswered={markAnswered}
                    feedback={blockFeedback['block4']} isLoading={blockLoading}
                  />
                </>
              ) : (
                <p className="locked-hint">
                  <Lock style={{ width: 14, height: 14, flexShrink: 0 }} />
                  {expertMode ? 'Requiert : monte_carlo() — 1 000 simulations.' : 'Simulera 1 000 scénarios pour évaluer vos chances de survie.'}
                </p>
              )}
            </div>
          </div>

          {/* Block 5 — Saisonnalité */}
          <div className={`cfo-block ${!hasAnalysis ? 'locked' : ''}`}>
            <div className={`block-header ${!hasAnalysis ? 'locked' : ''}`}>
              <span className={`block-number ${!hasAnalysis ? 'locked' : ''}`}>5</span>
              <span className={`block-title ${!hasAnalysis ? 'locked' : ''}`}>
                {expertMode ? 'Prévision Saisonnalité — 12 mois' : 'Vos revenus mois par mois'}
              </span>
              <span className={`block-status ${hasAnalysis ? 'block-status-ok' : 'block-status-locked'}`}>
                {hasAnalysis
                  ? modeText(expertMode, 'Actif', 'Disponible')
                  : modeText(expertMode, 'En attente', 'A remplir')}
              </span>
            </div>
            <div className="block-body">
              {hasAnalysis ? (
                <>
                  <div style={{ fontSize: '.78rem', color: '#6b7280', marginBottom: '.75rem', display: 'flex', flexWrap: 'wrap', gap: '.4rem .9rem', lineHeight: 1.5 }}>
                    <span>
                      <span style={{ fontWeight: 600 }}>
                        {modeText(expertMode, 'Secteur :', 'Votre secteur :')}
                      </span>{' '}
                      {ctx?.secteur || (ideaSummary ? 'détecté depuis l\'idéation' : 'non détecté — projection générique')}
                    </span>
                    <span style={{ color: '#94a3b8' }}>·</span>
                    <span>
                      <span style={{ fontWeight: 600 }}>
                        {modeText(expertMode, 'Source :', 'Données :')}
                      </span>{' '}
                      {modeText(expertMode,
                        'modèle saisonnier interne (cache secteur + historique revenus)',
                        'calcul automatique basé sur votre secteur et historique')}
                    </span>
                    {!ctx?.secteur && !ideaSummary && (
                      <span style={{ color: '#f59e0b', fontWeight: 500 }}>
                        ⚠ {modeText(expertMode, 'Précisez votre secteur pour affiner la saisonnalité', 'Indiquez votre secteur pour améliorer la prévision')}
                      </span>
                    )}
                  </div>
                  <SeasonalityChart seasonality={analysis?.seasonality} />
                  <BlockInlineQA
                    blockId="block5" routedQuestions={routedQuestions}
                    missing={missing} expertMode={expertMode}
                    onAnswer={(msg) => handleBlockAnswer(msg, 'block5')}
                    onFileAnswer={handleBlockFileAnswer}
                    onAnswered={markAnswered}
                    feedback={blockFeedback['block5']} isLoading={blockLoading}
                  />
                  {/* Text input for revenue history — type directly or import a file */}
                  <SeasonalityTextInput
                    expertMode={expertMode}
                    onSubmit={(msg) => handleBlockAnswer(msg, 'block5')}
                    disabled={blockLoading}
                  />
                  <label className="csv-upload-area" style={{ display: 'flex', cursor: 'pointer', marginTop: '.5rem' }}>
                    <input ref={csvInputRef} type="file" accept=".csv,.txt,.json,.xlsx,.pdf,.docx" onChange={handleCsvUpload} style={{ display: 'none' }} />
                    <Upload style={{ width: 15, height: 15, color: '#6366f1', flexShrink: 0 }} />
                    <div>
                      <div className="csv-upload-label">Importer votre historique de revenus</div>
                      <div className="csv-upload-sub">CSV, TXT, JSON, XLSX, PDF, DOCX — valeurs mensuelles</div>
                    </div>
                  </label>
                </>
              ) : (
                <p className="locked-hint">
                  <Lock style={{ width: 14, height: 14, flexShrink: 0 }} />
                  {expertMode ? 'Requiert : seasonality_trend().' : 'Disponible après analyse. Import CSV également possible.'}
                </p>
              )}
            </div>
          </div>

          {/* Block 6 — Benchmarks — unlocked as soon as we have any sector context */}
          {(() => {
            const hasSectorCtx = !!(ctx?.secteur || hasIdeaContext)
            return (
              <div className={`cfo-block ${!hasSectorCtx ? 'locked' : ''}`}>
                <div className={`block-header ${!hasSectorCtx ? 'locked' : ''}`}>
                  <span className={`block-number ${!hasSectorCtx ? 'locked' : ''}`}>6</span>
                  <span className={`block-title ${!hasSectorCtx ? 'locked' : ''}`}>
                    {expertMode ? 'Benchmarks Sectoriels' : 'Comment vous situez-vous dans votre secteur ?'}
                  </span>
                  <span className={`block-status ${bench ? (bench.source?.includes('tavily') ? 'block-status-ok' : 'block-status-partial') : hasSectorCtx ? 'block-status-partial' : 'block-status-locked'}`}>
                    {bench
                      ? (bench.source?.includes('tavily')
                        ? modeText(expertMode, 'Live Tavily', 'Données live')
                        : modeText(expertMode, 'Cache ChromaDB', 'Données cachées'))
                      : hasSectorCtx
                      ? modeText(expertMode, 'Chargement...', 'Chargement...')
                      : modeText(expertMode, 'En attente', 'A remplir')}
                  </span>
                </div>
                <div className="block-body">
                  {bench ? (
                    <>
                      <div style={{ fontSize: '.78rem', color: '#6b7280', marginBottom: '.75rem', display: 'flex', flexWrap: 'wrap', gap: '.4rem .9rem', lineHeight: 1.5 }}>
                        <span>
                          <span style={{ fontWeight: 600 }}>
                            {modeText(expertMode, 'Secteur comparé :', 'Votre secteur :')}
                          </span>{' '}
                          <span style={{ color: '#1e293b', fontWeight: 500 }}>{ctx?.secteur || 'SaaS (défaut)'}</span>
                        </span>
                        <span style={{ color: '#94a3b8' }}>·</span>
                        <span>
                          <span style={{ fontWeight: 600 }}>
                            {modeText(expertMode, 'Source :', 'Données :')}
                          </span>{' '}
                          {bench.source?.includes('tavily')
                            ? modeText(expertMode, 'Tavily (web temps réel)', 'données live du web')
                            : modeText(expertMode, 'ChromaDB (base vectorielle interne)', 'base de données sectorielle')}
                        </span>
                        {bench.similarity_score != null && expertMode && (
                          <>
                            <span style={{ color: '#94a3b8' }}>·</span>
                            <span>Similarité {(bench.similarity_score * 100).toFixed(0)}%</span>
                          </>
                        )}
                      </div>
                      <BenchTiles bench={bench} extra={extra} />
                      <BenchmarkChart bench={bench} extra={extra} kpis={analysis?.kpis} ctx={ctx} />
                      {benchText && (
                        <div className="md" style={{ fontSize: '.82rem', marginTop: '.9rem' }}>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{benchText}</ReactMarkdown>
                        </div>
                      )}
                      <BlockInlineQA
                        blockId="block6" routedQuestions={routedQuestions}
                        missing={missing} expertMode={expertMode}
                        onAnswer={(msg) => handleBlockAnswer(msg, 'block6')}
                        onAnswered={markAnswered}
                        onFileAnswer={handleBlockFileAnswer}
                        feedback={blockFeedback['block6']} isLoading={blockLoading}
                      />
                    </>
                  ) : hasSectorCtx ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '.55rem', color: '#6366f1', fontSize: '.82rem', padding: '.3rem 0' }}>
                      <span className="spinner" style={{ width: 13, height: 13 }} />
                      <span>
                        {modeText(expertMode,
                          'Récupération des benchmarks sectoriels via ChromaDB + Tavily…',
                          'Chargement des données de votre secteur…')}
                      </span>
                    </div>
                  ) : (
                    <p className="locked-hint">
                      <Lock style={{ width: 14, height: 14, flexShrink: 0 }} />
                      {expertMode ? 'ChromaDB + Tavily — déclenché dès que le secteur est détecté.' : 'Se charge automatiquement dès que votre secteur est identifié.'}
                    </p>
                  )}
                </div>
              </div>
            )
          })()}



        </div>

        {/* ── Resize handle ── */}
        <div
          className="chat-resize-handle"
          onMouseDown={e => { isDragging.current = true; document.body.style.cursor = 'col-resize'; e.preventDefault() }}
          title="Glisser pour redimensionner"
        >
          <div className="chat-resize-grip" />
        </div>

        {/* ═══ LIVE ZONE — free conversation only (right side, resizable) ═════ */}
        <div className="live-zone" style={{ flex: chatWidth, maxWidth: `${chatWidth + 5}%`, minWidth: `${Math.max(chatWidth - 5, 18)}%` }}>
          <div className="live-zone-scroll">

            {/* Welcome state — shown when no messages yet */}
            {messages.length === 0 && !loading && (
              <div className="live-welcome">
                <BrainCircuit style={{ width: 30, height: 30, color: '#c7d2fe' }} />
                <div className="live-welcome-title">
                  {modeText(expertMode, 'Chat libre - niveau expert', 'Chat libre avec votre CFO')}
                </div>
                <div className="live-welcome-sub">
                  {modeText(
                    expertMode,
                    'Definitions, strategie, hypotheses avancees et questions hors blocs - ici.',
                    "Termes a expliquer, strategie, questions hors blocs - c'est ici.",
                  )}
                  {entryPath === 'ideation' && businessIdea && (
                    <> Projet : <strong>{businessIdea.slice(0, 60)}</strong></>
                  )}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '.4rem', width: '100%' }}>
                  {[
                    "C'est quoi le burn rate exactement ?",
                    'Comment savoir si mon LTV/CAC est bon ?',
                    'Que veut dire Monte Carlo dans ce contexte ?',
                  ].map((e, i) => (
                    <button key={i} className="suggestion-chip" style={{ textAlign: 'left', fontSize: '.74rem' }} onClick={() => handleChatSend(e)}>
                      {e}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Loading state while auto-trigger runs */}
            {messages.length === 0 && loading && (
              <div className="live-welcome">
                <span className="spinner" style={{ width: 22, height: 22 }} />
                <div className="live-welcome-title">
                  {modeText(expertMode, 'Analyse CFO en cours...', 'Analyse en cours...')}
                </div>
                <div className="live-welcome-sub">
                  {entryPath === 'ideation'
                    ? "Votre CFO analyse votre projet d'idéation"
                    : 'Traitement en cours…'}
                </div>
              </div>
            )}

            {/* Chat messages */}
            {messages.map((m, i) => (
              <div key={i} className={m.role === 'user' ? 'live-msg-user' : 'live-msg-assistant'}>
                {m.role === 'user' ? (
                  <div className="live-bubble-user">{m.content}</div>
                ) : m.msgType === 'analysis' ? (
                  <div className="analysis-notif-badge">
                    <CheckCircle2 style={{ width: 13, height: 13, flexShrink: 0 }} />
                    <span>{m.content}</span>
                  </div>
                ) : (
                  <div className="live-bubble-assistant md">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                  </div>
                )}
              </div>
            ))}

            {loading && messages.length > 0 && (
              <div className="live-msg-assistant">
                <div style={{ display: 'flex', alignItems: 'center', gap: '.55rem', color: '#3b82f6', fontSize: '.8rem', padding: '.4rem 0' }}>
                  <span className="spinner" style={{ width: 13, height: 13 }} />
                  <span>Votre CFO réfléchit…</span>
                </div>
              </div>
            )}

            <div ref={bottomRef} />

          </div>

          {/* Suggestions for the free chat */}
          <SmartSuggestions
            analysis={analysis} hasAnalysis={hasAnalysis}
            onPrefillChat={handlePrefillChat} loading={loading}
          />

          {/* Free chat input */}
          <div className="live-input-bar">
            {whatifMode && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: '.45rem .7rem', marginBottom: '.45rem', fontSize: '.74rem', color: '#92400e' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '.35rem' }}>
                  <FlaskConical style={{ width: 12, height: 12 }} />Mode What-If actif
                </span>
                <button onClick={handleToggleWhatif} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#d97706', fontWeight: 700 }}>✕</button>
              </div>
            )}
            <div className="live-input-row">
              <textarea
                ref={textareaRef}
                className={`live-input-box${inputFlash ? ' input-flash' : ''}`}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKey}
                placeholder={
                  whatifMode ? 'Simulez un scénario hypothétique…'
                  : hasAnalysis ? 'Posez une question libre à votre CFO…'
                  : 'Que voulez-vous savoir ou comprendre ?'
                }
                rows={1}
              />
              <button className="send-btn" onClick={() => handleChatSend()} disabled={loading || !input.trim()}>
                {loading ? <span className="spinner" style={{ width: 14, height: 14 }} /> : '→'}
              </button>
            </div>
          </div>
        </div>

      </div>

      {/* History modal */}
      {showHistory && (
        <HistoryModal
          conversations={conversations}
          onRestore={handleRestoreConv}
          onDelete={handleDeleteConv}
          onNew={handleNewConv}
          onClose={() => setShowHistory(false)}
        />
      )}



    </div>
  )
}
