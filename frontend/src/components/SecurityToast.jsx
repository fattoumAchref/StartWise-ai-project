// src/components/SecurityToast.jsx
import { useEffect, useRef } from 'react'
import { useApp } from '../context/AppContext'

export default function SecurityToast() {
  const { securityToast, setSecurityToast } = useApp()
  const timerRef = useRef(null)

  // Progress bar animation
  useEffect(() => {
    if (!securityToast) return
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setSecurityToast(null), 5000)
    return () => clearTimeout(timerRef.current)
  }, [securityToast, setSecurityToast])

  if (!securityToast) return null

  // Strip the "🛡️ Analyse refusée : " prefix added by the backend
  const rawMessage = securityToast.message || ''
  const displayMessage = rawMessage
    .replace(/^🛡️\s*Analyse refusée\s*:\s*/i, '')
    .replace(/^Analyse refusée\s*:\s*/i, '')

  return (
    <div
      role="alert"
      aria-live="assertive"
      style={{ zIndex: 9999 }}
      className="fixed bottom-6 right-6 max-w-sm w-full pointer-events-auto animate-toast-in"
    >
      {/* Card */}
      <div className="relative overflow-hidden rounded-xl border border-red-500/30 bg-black/70 backdrop-blur-xl shadow-2xl shadow-red-900/20">

        {/* Progress bar — drains over 5s */}
        <div className="absolute bottom-0 left-0 h-[2px] bg-red-500/60 animate-shrink" />

        <div className="flex gap-3 p-4">
          {/* Icon */}
          <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-red-500/10 border border-red-500/30 flex items-center justify-center">
            <svg className="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M12 2L3.5 6v6c0 5 3.8 9.7 8.5 11 4.7-1.3 8.5-6 8.5-11V6L12 2z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4M12 16h.01" />
            </svg>
          </div>

          {/* Text */}
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-red-400 uppercase tracking-widest mb-1">
              Accès refusé — Prompt Guard
            </p>
            <p className="text-sm text-white/80 leading-relaxed">
              {displayMessage}
            </p>
          </div>

          {/* Close */}
          <button
            onClick={() => setSecurityToast(null)}
            className="flex-shrink-0 text-white/30 hover:text-white/70 transition-colors mt-0.5"
            aria-label="Fermer"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
