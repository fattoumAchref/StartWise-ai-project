'use client'
import { useState, useEffect, useRef } from 'react'
import { Building2, RefreshCw, Clock } from 'lucide-react'
import { getA2AState } from '@/services/cfo'
import A2APanel from '@/components/cfo/A2APanel'
import type { A2AState } from '@/lib/types'

export default function InvestmentPage() {
  const [a2a, setA2a]             = useState<A2AState | undefined>()
  const [elapsed, setElapsed]     = useState(0)
  const [polling, setPolling]     = useState(true)
  const intervalRef               = useRef<ReturnType<typeof setInterval> | null>(null)
  const elapsedRef                = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    const fetchState = async () => {
      try {
        const data = await getA2AState()
        if (data?.available && (data as A2AState).investment_rating) {
          setA2a(data as A2AState)
          setPolling(false)
          if (intervalRef.current) clearInterval(intervalRef.current)
          if (elapsedRef.current) clearInterval(elapsedRef.current)
        }
      } catch { /* silent */ }
    }

    fetchState()
    intervalRef.current = setInterval(fetchState, 5000)
    elapsedRef.current  = setInterval(() => setElapsed(e => e + 1), 1000)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      if (elapsedRef.current)  clearInterval(elapsedRef.current)
    }
  }, [])

  return (
    <div style={{ padding: '2rem', maxWidth: 860, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '.75rem', marginBottom: '1.75rem' }}>
        <Building2 style={{ width: 22, height: 22, color: '#6366f1', flexShrink: 0 }} />
        <div>
          <h1 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--foreground)', margin: 0 }}>
            Investment Agent
          </h1>
          <p style={{ fontSize: '.78rem', color: '#6b7280', margin: 0, marginTop: 2 }}>
            Recommandations stratégiques d'investissement basées sur votre analyse financière
          </p>
        </div>
        {polling && (
          <span style={{
            marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '.35rem',
            fontSize: '.72rem', color: '#6366f1', background: '#eef2ff',
            padding: '.25rem .6rem', borderRadius: 20,
          }}>
            <RefreshCw style={{ width: 11, height: 11 }} className="animate-spin" />
            polling…
          </span>
        )}
      </div>

      {/* Result or waiting state */}
      {a2a ? (
        <A2APanel
          a2a={a2a}
          elapsedSeconds={elapsed}
          onClarificationSent={() => setElapsed(0)}
          showCrossAgentConflicts={false}
        />
      ) : (
        <div style={{
          border: '1.5px dashed #c7d2fe', borderRadius: 12,
          padding: '2.5rem 2rem', textAlign: 'center',
        }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1rem' }}>
            <div style={{
              width: 48, height: 48, borderRadius: '50%',
              background: '#eef2ff', display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Building2 style={{ width: 22, height: 22, color: '#6366f1' }} />
            </div>
          </div>

          <p style={{ fontSize: '.9rem', fontWeight: 600, color: '#4338ca', marginBottom: '.5rem' }}>
            En attente des recommandations
          </p>

          <p style={{ fontSize: '.82rem', color: '#6b7280', lineHeight: 1.65, maxWidth: 480, margin: '0 auto .75rem' }}>
            L'Investment Agent analyse vos données financières automatiquement
            après chaque analyse complète sur la page <strong>Finance</strong>.
            Les recommandations apparaîtront ici dès qu'elles sont prêtes.
          </p>

          {elapsed > 0 && (
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: '.35rem',
              fontSize: '.72rem', color: '#9ca3af',
            }}>
              <Clock style={{ width: 12, height: 12 }} />
              {elapsed}s — vérification toutes les 5s
            </span>
          )}
        </div>
      )}
    </div>
  )
}
