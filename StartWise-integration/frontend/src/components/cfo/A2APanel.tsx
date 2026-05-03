'use client'
import type { A2AState } from '@/lib/types'
import { sendClarification } from '@/services/cfo'
import { useState } from 'react'

interface Props {
  a2a: A2AState
  elapsedSeconds: number
  onClarificationSent: () => void
  expertMode?: boolean
}

const ratingClass = (r?: string) =>
  r ? `rating-card rating-${r}` : 'rating-card'

const badgeClass = (r?: string) =>
  r ? `rating-badge badge-${r}` : 'rating-badge'

const fmt = (v?: string | number) => {
  if (v == null || v === '') return '—'
  const n = Number(v)
  if (!isNaN(n)) return n.toLocaleString('fr-FR')
  return String(v)
}

export default function A2APanel({ a2a, elapsedSeconds, onClarificationSent, expertMode }: Props) {
  const [answer, setAnswer] = useState('')
  const [sending, setSending] = useState(false)

  const rating = a2a.investment_rating
  const clarStatus = a2a.clarification_status
  const isReady = !!rating
  const isPending = clarStatus === 'pending'
  const isAutoAnswered = clarStatus === 'auto_answered'

  let pendingQuestions: string[] = []
  let autoAnswers: Record<string, string> = {}
  try { pendingQuestions = JSON.parse(a2a.clarification_questions || '[]') } catch { /* */ }
  try { autoAnswers = JSON.parse(a2a.clarification_auto_answers || '{}') } catch { /* */ }

  const handleSendAnswer = async () => {
    if (!answer.trim()) return
    setSending(true)
    try {
      await sendClarification(answer.trim())
      setAnswer('')
      onClarificationSent()
    } finally {
      setSending(false)
    }
  }

  if (!a2a.available) {
    return (
      <div style={{ color: '#9ca3af', fontSize: '.8rem' }}>
        InvestmentAgent non disponible (A2A_BUS_URL non configuré).
      </div>
    )
  }

  // ── Ready: show recommendation ───────────────────────────────────────────
  if (isReady) {
    const score = a2a.investment_score ? `${a2a.investment_score}%` : '—'
    const confidence = a2a.investment_confidence
      ? `${(Number(a2a.investment_confidence) * 100).toFixed(0)}%` : '—'

    // Beginner-friendly rating labels
    const ratingLabel = expertMode ? rating : (
      rating === 'STRONG_BUY' ? 'Très favorable' :
      rating === 'BUY' ? 'Favorable' :
      rating === 'HOLD' ? 'Neutre — à améliorer' :
      rating === 'PASS' ? 'Non recommandé' : rating
    )

    return (
      <div>
        <div className={ratingClass(rating)}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '.5rem' }}>
            <span className={badgeClass(rating)}>{ratingLabel}</span>
            {expertMode && (
              <span style={{ fontSize: '.78rem', color: '#6b7280' }}>
                Score {score} · Confiance {confidence}
              </span>
            )}
          </div>
          {a2a.investment_recommendation && (
            <p style={{ fontSize: '.83rem', color: '#374151', marginBottom: '.5rem' }}>
              {a2a.investment_recommendation}
            </p>
          )}
        </div>

        {/* Valuation */}
        {(a2a.valuation || a2a.valuation_method) && (
          <div style={{ marginBottom: '.6rem' }}>
            <div style={{ fontSize: '.75rem', fontWeight: 600, color: '#6b7280', marginBottom: '.3rem' }}>
              {expertMode ? 'VALORISATION' : 'VALEUR ESTIMÉE DE VOTRE STARTUP'}
            </div>
            <table className="w-full text-sm">
              <tbody>
                {a2a.valuation && <tr>
                  <td style={{ color: '#6b7280', padding: '2px 0' }}>{expertMode ? 'Valorisation' : 'Valeur estimée'}</td>
                  <td style={{ fontWeight: 600, textAlign: 'right' }}>{fmt(a2a.valuation)} TND</td>
                </tr>}
                {expertMode && a2a.valuation_method && <tr>
                  <td style={{ color: '#6b7280', padding: '2px 0' }}>Méthode</td>
                  <td style={{ fontWeight: 600, textAlign: 'right' }}>{a2a.valuation_method}</td>
                </tr>}
              </tbody>
            </table>
          </div>
        )}

        {/* Best scenario */}
        {a2a.best_scenario && (
          <div style={{ marginBottom: '.6rem' }}>
            <div style={{ fontSize: '.75rem', fontWeight: 600, color: '#6b7280', marginBottom: '.3rem' }}>
              {expertMode ? 'SCÉNARIO OPTIMAL' : 'MEILLEURE STRATÉGIE DE FINANCEMENT'}
            </div>
            <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '.6rem' }}>
              <div style={{ fontWeight: 600, marginBottom: '.3rem', fontSize: '.85rem' }}>{a2a.best_scenario}</div>
              <table className="w-full">
                <tbody>
                  {a2a.best_scenario_raise && <tr>
                    <td style={{ color: '#6b7280', fontSize: '.78rem' }}>{expertMode ? 'Levée' : 'Montant à lever'}</td>
                    <td style={{ fontWeight: 600, fontSize: '.78rem', textAlign: 'right' }}>{fmt(a2a.best_scenario_raise)} TND</td>
                  </tr>}
                  {a2a.best_scenario_dilution && <tr>
                    <td style={{ color: '#6b7280', fontSize: '.78rem' }}>{expertMode ? 'Dilution' : 'Part cédée aux investisseurs'}</td>
                    <td style={{ fontWeight: 600, fontSize: '.78rem', textAlign: 'right' }}>{a2a.best_scenario_dilution}%</td>
                  </tr>}
                  {a2a.founder_after_pct && <tr>
                    <td style={{ color: '#6b7280', fontSize: '.78rem' }}>{expertMode ? 'Part fondateur' : 'Vous gardez'}</td>
                    <td style={{ fontWeight: 600, fontSize: '.78rem', textAlign: 'right' }}>{a2a.founder_after_pct}%</td>
                  </tr>}
                  {expertMode && a2a.best_scenario_post_money && <tr>
                    <td style={{ color: '#6b7280', fontSize: '.78rem' }}>Post-money</td>
                    <td style={{ fontWeight: 600, fontSize: '.78rem', textAlign: 'right' }}>{fmt(a2a.best_scenario_post_money)} TND</td>
                  </tr>}
                </tbody>
              </table>
              {a2a.best_scenario_rationale && (
                <p style={{ fontSize: '.75rem', color: '#6b7280', marginTop: '.4rem', fontStyle: 'italic' }}>
                  {a2a.best_scenario_rationale}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Conflict */}
        {a2a.conflict_type && (
          <div style={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 8, padding: '.6rem', fontSize: '.8rem' }}>
            ⚠️ <strong>{expertMode ? a2a.conflict_type : 'Point d\'attention'}</strong> — {a2a.conflict_message}
          </div>
        )}
      </div>
    )
  }

  // ── Clarification asked ──────────────────────────────────────────────────
  if (isPending || isAutoAnswered) {
    return (
      <div>
        {isAutoAnswered && (
          <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 8, padding: '.75rem', marginBottom: '.75rem', fontSize: '.83rem' }}>
            <div style={{ fontWeight: 600, marginBottom: '.4rem' }}>✅ Questions répondues automatiquement</div>
            {Object.entries(autoAnswers).map(([q, a]) => (
              <div key={q} style={{ marginBottom: '.25rem' }}>
                <span style={{ color: '#6b7280' }}>{q}</span><br />
                <span style={{ fontWeight: 500 }}>→ {a}</span>
              </div>
            ))}
            <div style={{ marginTop: '.5rem', color: '#6b7280', display: 'flex', alignItems: 'center', gap: 6 }}>
              <span className="spinner" /> En attente de la recommandation… ({elapsedSeconds}s)
            </div>
          </div>
        )}

        {isPending && pendingQuestions.length > 0 && (
          <div>
            <div style={{ fontWeight: 600, fontSize: '.85rem', marginBottom: '.5rem' }}>
              L&apos;investment_agent a besoin de précisions :
            </div>
            {a2a.clarification_phrased && (
              <p style={{ fontSize: '.83rem', color: '#374151', marginBottom: '.75rem' }}>
                {a2a.clarification_phrased}
              </p>
            )}
            <ul style={{ fontSize: '.82rem', color: '#374151', paddingLeft: '1.2rem', marginBottom: '.75rem' }}>
              {pendingQuestions.map((q, i) => <li key={i}>{q}</li>)}
            </ul>
            <div style={{ display: 'flex', gap: '.5rem' }}>
              <input
                value={answer}
                onChange={e => setAnswer(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSendAnswer()}
                placeholder="Votre réponse…"
                style={{ flex: 1, border: '1px solid #e0e0e0', borderRadius: 8, padding: '.5rem .75rem', fontSize: '.85rem', outline: 'none' }}
              />
              <button
                onClick={handleSendAnswer}
                disabled={sending || !answer.trim()}
                className="send-btn"
                style={{ padding: '.5rem 1rem', fontSize: '.85rem' }}
              >
                {sending ? '…' : 'Envoyer'}
              </button>
            </div>
          </div>
        )}
      </div>
    )
  }

  // ── Waiting ──────────────────────────────────────────────────────────────
  return (
    <div style={{ color: '#6b7280', fontSize: '.83rem', display: 'flex', alignItems: 'center', gap: 8 }}>
      <span className="spinner" />
      {expertMode
        ? `InvestmentAgent analyse… (${elapsedSeconds}s)`
        : `L'agent prépare ses recommandations d'investissement… (${elapsedSeconds}s)`}
    </div>
  )
}
