'use client'
import { useRef } from 'react'
import type { FinancialContext, Validation, Conversation } from '@/lib/types'
import { newConversation, restoreConversation, deleteConversation, uploadFile, resetSession } from '@/lib/api'

interface Props {
  ctx?: FinancialContext
  validation?: Validation
  conversations: Conversation[]
  onNewConv: () => void
  onRestore: (msgs: unknown[]) => void
  onReset: () => void
  onUpload: (data: unknown) => void
}

const fmt = (v: unknown) => {
  if (v == null) return '—'
  try { return Number(v).toLocaleString('fr-FR') } catch { return String(v) }
}

const qualityClass = (score: number) =>
  score >= 0.8 ? 'q-complete' : score >= 0.5 ? 'q-partial' : 'q-missing'

const qualityLabel = (score: number) =>
  score >= 0.8 ? '✓ Complètes' : score >= 0.5 ? '⚠ Partielles' : '✗ Incomplètes'

export default function Sidebar({ ctx, validation, conversations, onNewConv, onRestore, onReset, onUpload }: Props) {
  const fileRef = useRef<HTMLInputElement>(null)

  const handleNew = async () => {
    await newConversation()
    onNewConv()
  }

  const handleRestore = async (id: string) => {
    const data = await restoreConversation(id)
    onRestore(data.messages || [])
  }

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    await deleteConversation(id)
    onNewConv()
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const data = await uploadFile(file)
    onUpload(data)
    e.target.value = ''
  }

  const handleReset = async () => {
    if (!confirm('Réinitialiser la session ?')) return
    await resetSession()
    onReset()
  }

  const dqs = validation?.data_quality_score ?? 0

  return (
    <aside className="sidebar">
      {/* Header */}
      <div className="sb-header">
        <div className="sb-logo">🎯 StartWise</div>
        <div className="sb-tagline">Assistant CFO · Multi-Agent</div>
      </div>

      {/* Actions */}
      <div className="sb-section">
        <div className="sb-section-title">Actions</div>
        <button className="sb-btn" onClick={handleNew}>＋ Nouvelle conversation</button>
        <button className="sb-btn" onClick={() => fileRef.current?.click()}>📎 Importer PDF / CSV</button>
        <button className="sb-btn" onClick={handleReset}>🗑 Réinitialiser</button>
        <input ref={fileRef} type="file" accept=".pdf,.csv,.txt,.xlsx" hidden onChange={handleUpload} />
      </div>

      {/* Context summary */}
      {ctx && (
        <div className="sb-section">
          <div className="sb-section-title">Contexte financier</div>
          {validation && (
            <div style={{ marginBottom: '0.5rem', textAlign: 'center' }}>
              <span className={`quality-badge ${qualityClass(dqs)}`}>
                {qualityLabel(dqs)} ({(dqs * 100).toFixed(0)}%)
              </span>
            </div>
          )}
          <div className="ctx-card">
            {ctx.burn_rate != null && (
              <div className="ctx-row"><span className="ctx-label">Burn</span><span className="ctx-value">{fmt(ctx.burn_rate)} TND/m</span></div>
            )}
            {ctx.cash_balance != null && (
              <div className="ctx-row"><span className="ctx-label">Cash</span><span className="ctx-value">{fmt(ctx.cash_balance)} TND</span></div>
            )}
            {ctx.monthly_revenue != null && (
              <div className="ctx-row"><span className="ctx-label">Revenu</span><span className="ctx-value">{fmt(ctx.monthly_revenue)} TND/m</span></div>
            )}
            {ctx.n_clients != null && (
              <div className="ctx-row"><span className="ctx-label">Clients</span><span className="ctx-value">{fmt(ctx.n_clients)}</span></div>
            )}
            {ctx.secteur && (
              <div className="ctx-row"><span className="ctx-label">Secteur</span><span className="ctx-value">{ctx.secteur}</span></div>
            )}
            {ctx.pays && (
              <div className="ctx-row"><span className="ctx-label">Pays</span><span className="ctx-value">{ctx.pays}</span></div>
            )}
          </div>
        </div>
      )}

      {/* Conversations */}
      {conversations.length > 0 && (
        <div className="sb-section" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div className="sb-section-title">Historique</div>
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {conversations.map(c => (
              <div key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <button className="sb-btn" style={{ flex: 1 }} onClick={() => handleRestore(c.id)}>
                  💬 {c.title}
                </button>
                <button
                  onClick={e => handleDelete(e, c.id)}
                  style={{ background: 'transparent', border: 'none', color: '#666', cursor: 'pointer', fontSize: '0.75rem', padding: '4px' }}
                >✕</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </aside>
  )
}
