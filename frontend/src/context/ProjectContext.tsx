'use client'
/**
 * ProjectContext.tsx
 * ─────────────────
 * Pont de données entre le module Idéation (ft-ideation-phase) et
 * le pipeline d'analyse stratégique StartWise.
 *
 * Flux :
 *   Onboarding Q&A  ──► ideationSummary (state)
 *                           │
 *                           ▼
 *                   document_text injecté dans AppContext
 *                           │
 *                           ▼
 *              4 agents parallèles (Trend, Vision, Emotion, Creative)
 */

import { createContext, useContext, useState, useCallback, ReactNode } from 'react'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface IdeationData {
  /** Résumé complet généré par le module Idéation */
  summary: string
  /** Idée business brute saisie pendant l'onboarding */
  businessIdea: string
  /** ID de session Idéation (pour récupérer la session si besoin) */
  sessionId: string | null
  /** Titre court extrait du résumé */
  shortTitle: string
}

interface ProjectContextValue {
  /** Données d'idéation (null si l'onboarding n'a pas encore été complété) */
  ideation: IdeationData | null
  /** Enregistre le résumé d'idéation et déclenche l'injection dans StartWise */
  setIdeationResult: (data: IdeationData) => void
  /** Efface l'idéation (nouveau projet) */
  clearIdeation: () => void
  /** true si un résumé d'idéation est disponible */
  hasIdeation: boolean
}

// ── Context ───────────────────────────────────────────────────────────────────

const ProjectContext = createContext<ProjectContextValue | null>(null)

// ── Provider ──────────────────────────────────────────────────────────────────

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [ideation, setIdeation] = useState<IdeationData | null>(() => {
    // Restaurer depuis localStorage au démarrage
    if (typeof window === 'undefined') return null
    try {
      const saved = localStorage.getItem('sw_ideation_data')
      return saved ? JSON.parse(saved) : null
    } catch {
      return null
    }
  })

  const setIdeationResult = useCallback((data: IdeationData) => {
    setIdeation(data)
    // Persister pour survivre aux rechargements
    try {
      localStorage.setItem('sw_ideation_data', JSON.stringify(data))
      // Clé utilisée par AppContext pour pré-remplir document_text + projectDesc
      localStorage.setItem('sw_ideation_summary', data.summary)
      localStorage.setItem('sw_ideation_business_idea', data.businessIdea)
    } catch { /* quota */ }
  }, [])

  const clearIdeation = useCallback(() => {
    setIdeation(null)
    localStorage.removeItem('sw_ideation_data')
    localStorage.removeItem('sw_ideation_summary')
    localStorage.removeItem('sw_ideation_business_idea')
  }, [])

  return (
    <ProjectContext.Provider
      value={{
        ideation,
        setIdeationResult,
        clearIdeation,
        hasIdeation: !!ideation?.summary,
      }}
    >
      {children}
    </ProjectContext.Provider>
  )
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useProject(): ProjectContextValue {
  const ctx = useContext(ProjectContext)
  if (!ctx) throw new Error('useProject must be used inside <ProjectProvider>')
  return ctx
}
