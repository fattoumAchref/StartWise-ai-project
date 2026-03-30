// src/pages/AgentPage.jsx - Version avec onglets spécifiques par agent
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useState, useEffect } from 'react'
import {
  ArrowLeft, TrendingUp, AlertTriangle, Lightbulb, Target, Zap,
  Shield, Rocket, BarChart3, ChevronDown, ChevronUp, Link2, ExternalLink,
  Brain, Sparkles, Palette, Type, Layout, Eye, Clock, Code, Palette as PaletteIcon,
  Droplet, Square, Activity, Hash, MessageSquare, ShieldAlert, Search, Gift, Mic2, Camera, Map as MapIcon,
} from 'lucide-react'

// Composant pour afficher une source avec lien
function SourceBadge({ source }) {
  if (!source || !source.url) {
    return (
      <div className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-[10px] text-gray-500">
        <Brain className="w-2 h-2" />
        <span>IA StartWise</span>
      </div>
    )
  }

  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 dark:bg-blue-950/30 rounded text-[10px] text-blue-600 dark:text-blue-400 hover:underline transition-all"
    >
      <Link2 className="w-2 h-2" />
      <span className="max-w-[150px] truncate">{source.title || source.type || 'Source'}</span>
      <ExternalLink className="w-2 h-2" />
    </a>
  )
}

// ==================== COMPOSANTS POUR TREND HUNTER ====================

function RiskCard({ risk, index }) {
  const [isExpanded, setIsExpanded] = useState(false)

  const getRiskText = (field) => {
    if (!field) return ''
    if (typeof field === 'string') return field
    if (typeof field === 'object') {
      return field.risk || field.name || field.description || JSON.stringify(field)
    }
    return String(field)
  }

  const riskName = getRiskText(risk.risk || risk.name)
  const riskDesc = getRiskText(risk.description)
  const riskMitigation = getRiskText(risk.mitigation)
  const riskSource = risk.source

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
      className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden"
    >
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-5 text-left flex items-start justify-between hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
      >
        <div className="flex items-start gap-4 flex-1">
          <div className="w-8 h-8 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="w-4 h-4 text-red-500" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h4 className="font-semibold text-gray-900 dark:text-white">{riskName}</h4>
              {riskSource && <SourceBadge source={riskSource} />}
            </div>
            <p className="text-sm text-gray-500 mt-1 line-clamp-2">{riskDesc}</p>
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-gray-400 flex-shrink-0" />
        ) : (
          <ChevronDown className="w-5 h-5 text-gray-400 flex-shrink-0" />
        )}
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-gray-100 dark:border-gray-800 px-5 py-4 bg-gray-50 dark:bg-gray-800/50"
          >
            <div className="space-y-3">
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Mitigation</p>
                <p className="text-sm text-gray-700 dark:text-gray-300">{riskMitigation}</p>
              </div>
              {riskSource?.url && (
                <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                  <p className="text-xs text-gray-400">Source originale</p>
                  <a href={riskSource.url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 hover:underline break-all">
                    {riskSource.url}
                  </a>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function WeakSignalCard({ signal, index }) {
  const [isExpanded, setIsExpanded] = useState(false)

  const signalName = signal.signal || signal.name
  const signalDesc = signal.description || signal.summary
  const signalOpportunity = signal.opportunity
  const signalSource = signal.source

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05 }}
      className="group relative"
    >
      <div className="relative p-5 rounded-xl border border-gray-200 dark:border-gray-800 hover:border-blue-500/50 transition-all bg-white dark:bg-gray-900">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center flex-shrink-0">
            <Zap className="w-5 h-5 text-blue-500" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap mb-2">
              <span className="text-xs font-mono text-blue-500 bg-blue-50 dark:bg-blue-950/30 px-2 py-0.5 rounded">
                SIGNAL #{index + 1}
              </span>
              {signalSource && <SourceBadge source={signalSource} />}
            </div>
            <h4 className="font-semibold text-gray-900 dark:text-white mb-2">{signalName}</h4>
            <p className="text-sm text-gray-600 dark:text-gray-400">{signalDesc}</p>
          </div>
          <button onClick={() => setIsExpanded(!isExpanded)} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors">
            <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
          </button>
        </div>

        <AnimatePresence>
          {isExpanded && signalOpportunity && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-800"
            >
              <div className="bg-gradient-to-r from-blue-500/5 to-cyan-500/5 rounded-lg p-4">
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Opportunité stratégique</p>
                <p className="text-sm text-gray-600 dark:text-gray-400">{signalOpportunity}</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}

function RecommendationCard({ recommendation, index }) {
  const recText = typeof recommendation === 'string' ? recommendation : recommendation.recommendation
  const recSource = recommendation.source

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 + index * 0.05 }}
      className="group cursor-pointer"
    >
      <div className="relative p-5 rounded-xl bg-gradient-to-r from-blue-500/5 to-cyan-500/5 border border-blue-500/20 hover:border-blue-500/40 transition-all">
        <div className="flex items-start gap-4">
          <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform">
            <Rocket className="w-4 h-4 text-blue-500" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap mb-2">
              <span className="text-xs font-mono text-blue-500">RECOMMANDATION #{index + 1}</span>
              {recSource && <SourceBadge source={recSource} />}
            </div>
            <p className="text-sm text-gray-900 dark:text-white">{recText}</p>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

// ==================== COMPOSANTS POUR VISION SEMIOTICS ====================

function ColorPaletteCard({ palette }) {
  const [hoveredColor, setHoveredColor] = useState(null)

  const colors = [
    { name: palette.primary?.name || "Primary", hex: palette.primary?.hex || "#0D9488", role: "Primaire" },
    ...(palette.secondary || []).map((c, i) => ({ ...c, role: `Secondaire ${i + 1}` })),
    { name: palette.accent?.name || "Accent", hex: palette.accent?.hex || "#F4D03F", role: "Accent" },
    { name: palette.neutral?.name || "Neutral", hex: palette.neutral?.hex || "#2C2C2C", role: "Neutre" }
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6"
    >
      <div className="flex items-center gap-2 mb-4">
        <PaletteIcon className="w-5 h-5 text-purple-500" />
        <h3 className="font-semibold">Palette de couleurs</h3>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {colors.map((color, idx) => (
          <motion.div
            key={idx}
            whileHover={{ scale: 1.05, y: -5 }}
            onHoverStart={() => setHoveredColor(color)}
            onHoverEnd={() => setHoveredColor(null)}
            className="relative cursor-pointer"
          >
            <div
              className="w-full h-24 rounded-xl shadow-lg transition-all"
              style={{ backgroundColor: color.hex }}
            />
            <p className="text-xs font-mono text-center mt-2">{color.name}</p>
            <p className="text-[10px] text-gray-400 text-center">{color.hex}</p>
            <AnimatePresence>
              {hoveredColor === color && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="absolute -top-8 left-1/2 -translate-x-1/2 bg-gray-900 text-white text-xs px-2 py-1 rounded whitespace-nowrap"
                >
                  {color.psychology || color.role}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        ))}
      </div>
    </motion.div>
  )
}

function TypographyCard({ typography }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6"
    >
      <div className="flex items-center gap-2 mb-4">
        <Type className="w-5 h-5 text-purple-500" />
        <h3 className="font-semibold">Typographie</h3>
      </div>
      <div className="space-y-4">
        <div>
          <p className="text-xs text-gray-500 mb-1">Titres</p>
          <p className="text-2xl font-bold" style={{ fontFamily: typography.heading?.name }}>
            {typography.heading?.name || "Playfair Display"}
          </p>
          <p className="text-xs text-gray-400 mt-1">{typography.heading?.justification}</p>
        </div>
        <div className="pt-3 border-t border-gray-100 dark:border-gray-800">
          <p className="text-xs text-gray-500 mb-1">Corps de texte</p>
          <p className="text-base" style={{ fontFamily: typography.body?.name }}>
            {typography.body?.name || "Inter"} — La typographie est l'art de rendre le texte agréable à lire.
          </p>
          <p className="text-xs text-gray-400 mt-1">{typography.body?.justification}</p>
        </div>
      </div>
    </motion.div>
  )
}

function CompositionCard({ composition }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
      className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6"
    >
      <div className="flex items-center gap-2 mb-4">
        <Layout className="w-5 h-5 text-purple-500" />
        <h3 className="font-semibold">Composition & Grille</h3>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-gray-500 mb-1">Type de grille</p>
          <p className="text-sm">{composition.grid_type || "Asymmetrical"}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Ratio images</p>
          <p className="text-sm">{composition.image_ratio || "16:9"}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Pattern d'attention</p>
          <p className="text-sm">{composition.attention_pattern || "Z-Pattern"}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Espacement</p>
          <p className="text-sm">{composition.spacing || "Généreux"}</p>
        </div>
      </div>
    </motion.div>
  )
}

function StyleCard({ style }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
      className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6"
    >
      <div className="flex items-center gap-2 mb-4">
        <Eye className="w-5 h-5 text-purple-500" />
        <h3 className="font-semibold">Style visuel</h3>
      </div>
      <div className="space-y-3">
        <div>
          <p className="text-xs text-gray-500 mb-1">Style recommandé</p>
          <p className="text-lg font-medium">{style.style || "Glassmorphism subtil"}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Justification</p>
          <p className="text-sm text-gray-600 dark:text-gray-400">{style.justification}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Application</p>
          <p className="text-sm text-gray-600 dark:text-gray-400">{style.application}</p>
        </div>
      </div>
    </motion.div>
  )
}

function VibeCheckCard({ vibe }) {
  const scores = [
    { name: "Esthétique", value: vibe.aesthetic_score || 92, icon: Eye },
    { name: "Premium", value: vibe.premium_perception || 88, icon: Target },
    { name: "Tech", value: vibe.tech_perception || 75, icon: Zap },
    { name: "Confiance", value: vibe.trust_perception || 85, icon: Shield }
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4 }}
      className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6"
    >
      <div className="flex items-center gap-2 mb-4">
        <Activity className="w-5 h-5 text-purple-500" />
        <h3 className="font-semibold">Vibe Check - Perception émotionnelle</h3>
      </div>
      <div className="grid grid-cols-2 gap-4 mb-4">
        {scores.map((score, idx) => {
          const IconComp = score.icon
          return (
            <div key={idx} className="text-center">
              <IconComp className="w-4 h-4 mx-auto mb-1 text-gray-400" />
              <p className="text-2xl font-bold">{score.value}%</p>
              <p className="text-xs text-gray-500">{score.name}</p>
            </div>
          )
        })}
      </div>
      <p className="text-sm text-gray-600 dark:text-gray-400">{vibe.feedback_analysis}</p>
    </motion.div>
  )
}

function SemioticSquareCard({ semiotic }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.5 }}
      className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6"
    >
      <div className="flex items-center gap-2 mb-4">
        <Square className="w-5 h-5 text-purple-500" />
        <h3 className="font-semibold">Carré sémiotique (Greimas)</h3>
      </div>
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="bg-purple-50 dark:bg-purple-950/20 rounded-lg p-3 text-center">
          <p className="text-xs text-gray-500">Position primaire</p>
          <p className="text-sm font-medium mt-1">{semiotic.primary_position || "Nature + Individu"}</p>
        </div>
        <div className="bg-blue-50 dark:bg-blue-950/20 rounded-lg p-3 text-center">
          <p className="text-xs text-gray-500">Position secondaire</p>
          <p className="text-sm font-medium mt-1">{semiotic.secondary_position || "Culture"}</p>
        </div>
      </div>
      <div className="mb-4">
        <p className="text-xs text-gray-500 mb-1">Zones à éviter</p>
        <div className="flex flex-wrap gap-2">
          {(semiotic.avoidance_zones || []).map((zone, idx) => (
            <span key={idx} className="px-2 py-1 bg-red-100 dark:bg-red-950/30 text-red-600 text-xs rounded">
              {zone}
            </span>
          ))}
        </div>
      </div>
      <p className="text-sm text-gray-600 dark:text-gray-400">{semiotic.visual_posture}</p>
    </motion.div>
  )
}

function TemporalAgingCard({ aging }) {
  // Valeurs par défaut pour éviter les erreurs
  const safeAging = {
    aging_score: aging?.aging_score ?? 7.5,
    timeless_elements: Array.isArray(aging?.timeless_elements) ? aging.timeless_elements : [],
    trends_to_avoid: Array.isArray(aging?.trends_to_avoid) ? aging.trends_to_avoid : [],
    refresh_schedule: aging?.refresh_schedule || "Refresh recommandé tous les 2-3 ans"
  }

  // Si refresh_schedule est un objet, le convertir en string
  let refreshText = safeAging.refresh_schedule
  if (typeof refreshText === 'object' && refreshText !== null) {
    // Convertir l'objet en texte lisible
    const parts = []
    if (refreshText.court_term) parts.push(`Court terme: ${refreshText.court_term}`)
    if (refreshText.moyen_term) parts.push(`Moyen terme: ${refreshText.moyen_term}`)
    if (refreshText.long_term) parts.push(`Long terme: ${refreshText.long_term}`)
    refreshText = parts.join(' • ') || "Plan de refresh défini"
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.6 }}
      className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6"
    >
      <div className="flex items-center gap-2 mb-4">
        <Clock className="w-5 h-5 text-purple-500" />
        <h3 className="font-semibold">Durabilité esthétique</h3>
      </div>
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm text-gray-500">Score de longévité</span>
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold">{safeAging.aging_score}</span>
          <span className="text-sm text-gray-400">/10</span>
        </div>
      </div>
      <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full mb-4">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${safeAging.aging_score * 10}%` }}
          transition={{ duration: 1 }}
          className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full"
        />
      </div>
      <div className="space-y-2">
        <div>
          <p className="text-xs text-gray-500 mb-1">Éléments intemporels</p>
          <div className="flex flex-wrap gap-1">
            {safeAging.timeless_elements.map((el, idx) => (
              <span key={idx} className="px-2 py-0.5 bg-green-100 dark:bg-green-950/30 text-green-600 text-xs rounded">
                {typeof el === 'string' ? el : JSON.stringify(el)}
              </span>
            ))}
          </div>
          {safeAging.timeless_elements.length === 0 && (
            <p className="text-xs text-gray-400 italic">Aucun élément identifié</p>
          )}
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Tendances à éviter</p>
          <div className="flex flex-wrap gap-1">
            {safeAging.trends_to_avoid.map((trend, idx) => (
              <span key={idx} className="px-2 py-0.5 bg-red-100 dark:bg-red-950/30 text-red-600 text-xs rounded">
                {typeof trend === 'string' ? trend : JSON.stringify(trend)}
              </span>
            ))}
          </div>
          {safeAging.trends_to_avoid.length === 0 && (
            <p className="text-xs text-gray-400 italic">Aucune tendance critique</p>
          )}
        </div>
        <p className="text-xs text-gray-400 mt-2">{refreshText}</p>
      </div>
    </motion.div>
  )
}

function DesignTokensCard({ tokens }) {
  const [copied, setCopied] = useState(false)

  const copyToClipboard = () => {
    navigator.clipboard.writeText(JSON.stringify(tokens, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.7 }}
      className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6"
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Code className="w-5 h-5 text-purple-500" />
          <h3 className="font-semibold">Design Tokens (Tailwind ready)</h3>
        </div>
        <button
          onClick={copyToClipboard}
          className="px-3 py-1 text-xs bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
        >
          {copied ? "Copié !" : "Copier JSON"}
        </button>
      </div>
      <pre className="text-xs font-mono bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg overflow-auto max-h-48">
        {JSON.stringify(tokens, null, 2)}
      </pre>
    </motion.div>
  )
}

function CompetitorAnalysisCard({ competitors }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.8 }}
      className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6"
    >
      <div className="flex items-center gap-2 mb-4">
        <Hash className="w-5 h-5 text-purple-500" />
        <h3 className="font-semibold">Concurrents analysés</h3>
      </div>
      <div className="space-y-2">
        {competitors?.slice(0, 5).map((comp, idx) => (
          <div key={idx} className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-800 last:border-0">
            <span className="text-sm">{comp.title || comp.name}</span>
            {comp.url && (
              <a href={comp.url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 hover:underline">
                Voir
              </a>
            )}
          </div>
        ))}
      </div>
    </motion.div>
  )
}



function ConfidenceCurve({ value }) {
  const [displayValue, setDisplayValue] = useState(0)

  useEffect(() => {
    let start = 0
    const duration = 2000
    const stepTime = 20
    const steps = duration / stepTime
    const increment = value / steps

    const timer = setInterval(() => {
      start += increment
      if (start >= value) {
        setDisplayValue(value)
        clearInterval(timer)
      } else {
        setDisplayValue(Math.round(start))
      }
    }, stepTime)

    return () => clearInterval(timer)
  }, [value])

  return (
    <div className="relative flex flex-col items-center">
      <div className="relative w-32 h-32">
        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="52" fill="none" stroke="#e5e7eb" strokeWidth="8" className="dark:stroke-gray-700" />
          <motion.circle
            cx="60"
            cy="60"
            r="52"
            fill="none"
            stroke="url(#gradient)"
            strokeWidth="8"
            strokeLinecap="round"
            initial={{ strokeDasharray: 326.8, strokeDashoffset: 326.8 }}
            animate={{ strokeDashoffset: 326.8 * (1 - displayValue / 100) }}
            transition={{ duration: 2, ease: "easeOut" }}
          />
          <defs>
            <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#3b82f6" />
              <stop offset="100%" stopColor="#06b6d4" />
            </linearGradient>
          </defs>
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold text-gray-900 dark:text-white">{displayValue}%</span>
          <span className="text-[8px] text-gray-500">CONFIANCE</span>
        </div>
      </div>
    </div>
  )
}



// ==================== COMPOSANTS POUR EMOTION AGENT ====================

//Sentiment Velocity
function SentimentVelocityTable({ data }) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
      <h3 className="font-semibold mb-4 flex items-center gap-2">
        <TrendingUp className="w-5 h-5 text-emerald-500" /> Sentiment Velocity (12 mois)
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-500 border-b border-gray-100 dark:border-gray-800">
              <th className="text-left pb-3">Concurrent</th>
              <th className="pb-3 text-center">Score Initial</th>
              <th className="pb-3 text-center">Actuel</th>
              <th className="pb-3 text-center">Tendance</th>
            </tr>
          </thead>
          <tbody>
            {data.map((item, idx) => (
              <tr key={idx} className="border-b border-gray-50 dark:border-gray-800/50">
                <td className="py-4 font-medium">{item.competitor}</td>
                <td className="text-center">{item.prev_score}/5</td>
                <td className="text-center font-bold text-emerald-500">{item.current_score}/5</td>
                <td className="text-center">
                  {item.trend === 'down' ?
                    <span className="text-red-500 flex items-center justify-center">↘ Chute</span> :
                    <span className="text-green-500 flex items-center justify-center">↗ Montée</span>
                  }
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

//Hall of Shame (Captures HTML)
function HallOfShame({ reviews }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {reviews.map((rev, idx) => (
        <div key={idx} className="p-4 bg-gray-50 dark:bg-gray-800 rounded-xl border border-red-500/20">
          <div className="flex justify-between items-center mb-2">
            <span className="text-xs font-bold text-red-500 uppercase">⚠️ {rev.competitor}</span>
            <span className="text-[10px] text-gray-400">{rev.source}</span>
          </div>
          {/* L'IA injecte ici le faux HTML qui ressemble à un tweet/avis */}
          <div
            className="text-sm italic text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-900 p-3 rounded shadow-sm border border-gray-100 dark:border-gray-800"
            dangerouslySetInnerHTML={{ __html: rev.comment }}
          />
          <p className="text-[11px] mt-2 text-emerald-500">💡 Opportunité : Ne pas reproduire cette erreur.</p>
        </div>
      ))}
    </div>
  );
}

//Social Sentiment Mining (Le Mur des Lamentations)
function SentimentMining({ mining }) {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold flex items-center gap-2 mb-4">
        <Search className="w-5 h-5 text-red-500" /> Le Mur des Lamentations (Extraction IA)
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {mining.map((item, idx) => (
          <motion.div
            key={idx}
            whileHover={{ y: -5 }}
            className="p-4 bg-white dark:bg-gray-900 border-l-4 border-red-500 rounded-r-xl shadow-sm"
          >
            <div className="flex justify-between items-start mb-2">
              <span className="text-xs font-bold text-red-500 uppercase">{item.topic}</span>
              <span className="text-[10px] bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded italic">
                Source: {item.source}
              </span>
            </div>
            <p className="text-sm italic text-gray-600 dark:text-gray-400 mb-3">"{item.verbatim}"</p>
            <div className="pt-2 border-t border-gray-100 dark:border-gray-800">
              <p className="text-[11px] font-bold text-emerald-500 uppercase">Opportunité StartWise :</p>
              <p className="text-xs text-gray-700 dark:text-gray-300">{item.opportunity}</p>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

//Loyalty Audit (Le Showroom des Récompenses)
function LoyaltyAudit({ audit }) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
      <h3 className="font-semibold mb-6 flex items-center gap-2">
        <Gift className="w-5 h-5 text-emerald-500" /> Showroom des Récompenses
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 relative">
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 hidden md:block">
          <div className="w-8 h-8 rounded-full bg-emerald-500 text-white flex items-center justify-center font-bold text-xs shadow-lg">VS</div>
        </div>

        {/* Système Concurrent */}
        <div className="p-5 bg-gray-50 dark:bg-gray-800/50 rounded-2xl border border-dashed border-gray-300 dark:border-gray-700 opacity-70">
          <p className="text-xs font-bold text-gray-400 mb-2 uppercase">Système Concurrent (Froid)</p>
          <h4 className="font-bold text-lg mb-2">{audit.cold_system?.name}</h4>
          <p className="text-sm text-gray-500 mb-4">{audit.cold_system?.desc}</p>
          <div className="p-3 bg-white dark:bg-gray-900 rounded border border-gray-200 text-xs font-mono text-red-400">
            Visual: {audit.cold_system?.visual}
          </div>
        </div>

        {/* Système StartWise */}
        <div className="p-5 bg-gradient-to-br from-emerald-500/10 to-teal-500/10 rounded-2xl border-2 border-emerald-500 shadow-xl shadow-emerald-500/5">
          <p className="text-xs font-bold text-emerald-500 mb-2 uppercase">Approche StartWise (Valorisante)</p>
          <h4 className="font-bold text-lg mb-2">{audit.warm_system?.name}</h4>
          <p className="text-sm text-gray-700 dark:text-gray-300 mb-4">{audit.warm_system?.desc}</p>
          <div className="p-3 bg-emerald-500 text-white rounded shadow-lg text-xs font-bold animate-pulse">
            ✨ {audit.warm_system?.visual}
          </div>
        </div>
      </div>
    </div>
  );
}
//Voice-Matching (Le Battle des Tonalités)
function VoiceMatching({ matching }) {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold flex items-center gap-2 mb-4">
        <Mic2 className="w-5 h-5 text-purple-500" /> Battle des Tonalités (Voice-Matching)
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-red-50 dark:bg-red-950/20 p-4 rounded-xl border border-red-200 dark:border-red-900">
          <p className="text-[10px] font-bold text-red-500 uppercase mb-2 italic">Réponse Robotique (Concurrent)</p>
          <p className="text-sm text-gray-800 dark:text-gray-200 italic leading-relaxed">"{matching.bad_reply}"</p>
        </div>
        <div className="bg-emerald-50 dark:bg-emerald-950/20 p-4 rounded-xl border border-emerald-200 dark:border-emerald-900">
          <p className="text-[10px] font-bold text-emerald-500 uppercase mb-2 italic">Réponse Empathique (StartWise)</p>
          <p className="text-sm text-gray-800 dark:text-gray-200 italic leading-relaxed font-medium">"{matching.good_reply}"</p>
        </div>
      </div>
      <div className="mt-2 p-3 bg-purple-500/10 border border-purple-500/20 rounded-lg">
        <p className="text-xs text-purple-600 dark:text-purple-400 font-medium">
          🎯 <strong>Personality Gap :</strong> {matching.personality_gap}
        </p>
      </div>
    </div>
  );
}

//composant expert
function CustomerJourneyMap({ journey }) {
  return (
    <div className="py-8">
      <h3 className="font-semibold mb-8 flex items-center gap-2">
        <MapIcon className="w-5 h-5 text-emerald-500" /> Parcours Client Idéal : L'Expérience "Haute Couture"
      </h3>
      <div className="relative flex justify-between">
        {/* Ligne de fond */}
        <div className="absolute top-1/2 left-0 w-full h-0.5 bg-gray-200 dark:bg-gray-800 -translate-y-1/2" />

        {journey.map((item, idx) => (
          <motion.div
            key={idx}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.2 }}
            className="relative z-10 flex flex-col items-center group w-1/4"
          >
            {/* L'icône de l'étape */}
            <div className={`w-12 h-12 rounded-full flex items-center justify-center text-xl mb-4 shadow-xl transition-all group-hover:scale-110 
              ${item.type === 'delight' ? 'bg-emerald-500 text-white' : 'bg-red-500 text-white'}`}>
              {item.icon}
            </div>

            {/* Le texte */}
            <div className="text-center px-2">
              <p className="font-bold text-sm mb-1 uppercase tracking-tighter">{item.step}</p>
              <p className="text-[11px] text-gray-500 leading-tight bg-white dark:bg-gray-900 p-2 rounded-lg border border-gray-100 dark:border-gray-800 shadow-sm">
                {item.desc}
              </p>
            </div>

            {/* Indicateur de type */}
            <div className={`mt-2 px-2 py-0.5 rounded-full text-[9px] font-bold uppercase ${item.type === 'delight' ? 'text-emerald-500 bg-emerald-50' : 'text-red-500 bg-red-50'}`}>
              {item.type === 'delight' ? '✨ Moment Plaisir' : '⚠️ Point de Friction'}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

// Carte OCEAN Profile avec animation de barre
function OceanProfileCard({ profile }) {
  const dimensions = [
    { key: 'openness', label: 'Openness', icon: '🎨', color: 'from-purple-500 to-pink-500' },
    { key: 'conscientiousness', label: 'Conscientiousness', icon: '📋', color: 'from-blue-500 to-cyan-500' },
    { key: 'extraversion', label: 'Extraversion', icon: '🗣️', color: 'from-green-500 to-emerald-500' },
    { key: 'agreeableness', label: 'Agreeableness', icon: '🤝', color: 'from-orange-500 to-amber-500' },
    { key: 'neuroticism', label: 'Neuroticism', icon: '🌊', color: 'from-red-500 to-rose-500' }
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6"
    >
      <div className="flex items-center gap-2 mb-4">
        <Brain className="w-5 h-5 text-emerald-500" />
        <h3 className="font-semibold">Profil OCEAN (Big Five)</h3>
        <span className="text-xs text-gray-400 ml-2">Référence Netflix/Spotify</span>
      </div>
      <div className="space-y-4">
        {dimensions.map((dim, idx) => {
          const data = profile[dim.key] || { score: 50, rationale: '', ux_recommendation: '' }
          return (
            <motion.div
              key={dim.key}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.1 }}
              className="group cursor-pointer"
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm">{dim.icon}</span>
                  <span className="text-sm font-medium">{dim.label}</span>
                </div>
                <span className="text-sm font-bold text-emerald-500">{data.score}%</span>
              </div>
              <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${data.score}%` }}
                  transition={{ duration: 1, delay: idx * 0.1 }}
                  className={`h-full bg-gradient-to-r ${dim.color} rounded-full`}
                />
              </div>
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                whileHover={{ opacity: 1, height: 'auto' }}
                className="overflow-hidden"
              >
                <p className="text-xs text-gray-500 mt-1">{data.rationale}</p>
                <p className="text-xs text-emerald-500 mt-0.5">💡 {data.ux_recommendation}</p>
              </motion.div>
            </motion.div>
          )
        })}
      </div>
    </motion.div>
  )
}

// Carte Tone of Voice avec animation au survol
function ToneOfVoiceCard({ tone }) {
  const pillars = [
    { key: 'direct', label: 'Direct', icon: '⚡', color: 'border-blue-500', bg: 'bg-blue-50 dark:bg-blue-950/20' },
    { key: 'empathic', label: 'Empathique', icon: '❤️', color: 'border-rose-500', bg: 'bg-rose-50 dark:bg-rose-950/20' },
    { key: 'inspiring', label: 'Inspirant', icon: '✨', color: 'border-amber-500', bg: 'bg-amber-50 dark:bg-amber-950/20' },
    { key: 'non_judgmental', label: 'Non-jugemental', icon: '🕊️', color: 'border-emerald-500', bg: 'bg-emerald-50 dark:bg-emerald-950/20' }
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6"
    >
      <div className="flex items-center gap-2 mb-4">
        <MessageSquare className="w-5 h-5 text-emerald-500" />
        <h3 className="font-semibold">Tone of Voice Matrix</h3>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {pillars.map((pillar, idx) => {
          const data = tone[pillar.key] || { example: '', when: '', micro_copy: '' }
          return (
            <motion.div
              key={pillar.key}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: idx * 0.1 }}
              whileHover={{ scale: 1.02, y: -2 }}
              className={`p-4 rounded-xl border-l-4 ${pillar.color} ${pillar.bg} transition-all`}
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-lg">{pillar.icon}</span>
                <span className="font-semibold">{pillar.label}</span>
              </div>
              <p className="text-sm text-gray-700 dark:text-gray-300 italic">"{data.example}"</p>
              <p className="text-xs text-gray-500 mt-2">📌 {data.when}</p>
              <p className="text-xs text-emerald-500 mt-1">✍️ {data.micro_copy}</p>
            </motion.div>
          )
        })}
      </div>
    </motion.div>
  )
}

// Carte Circadian Emotion avec timeline animée
function CircadianCard({ circadian }) {
  const periods = [
    { key: 'morning', label: '🌅 Matin', time: '6h-11h', emoji: '⚡' },
    { key: 'midday', label: '🍽️ Midi', time: '11h-14h', emoji: '😌' },
    { key: 'afternoon', label: '📊 Après-midi', time: '14h-18h', emoji: '🎯' },
    { key: 'evening', label: '🌙 Soir', time: '18h-22h', emoji: '🏆' },
    { key: 'night', label: '💤 Nuit', time: '22h-6h', emoji: '😴' }
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6"
    >
      <div className="flex items-center gap-2 mb-4">
        <Clock className="w-5 h-5 text-emerald-500" />
        <h3 className="font-semibold">Cartographie Émotionnelle Circadienne</h3>
      </div>
      <div className="relative">
        {/* Timeline ligne horizontale */}
        <div className="absolute top-8 left-0 right-0 h-0.5 bg-gray-200 dark:bg-gray-700" />
        <div className="relative flex justify-between gap-2 overflow-x-auto pb-4">
          {periods.map((period, idx) => {
            const data = circadian[period.key] || { emotion: '', tone: '', push: '' }
            return (
              <motion.div
                key={period.key}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.1 }}
                whileHover={{ y: -5 }}
                className="flex flex-col items-center min-w-[80px] text-center cursor-pointer group"
              >
                <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-950/30 flex items-center justify-center text-xl mb-2 group-hover:scale-110 transition-transform">
                  {period.emoji}
                </div>
                <p className="text-xs font-semibold">{period.label}</p>
                <p className="text-[10px] text-gray-400">{period.time}</p>
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  whileHover={{ opacity: 1, scale: 1 }}
                  className="absolute bottom-full mb-2 bg-gray-900 text-white text-xs px-2 py-1 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-all pointer-events-none"
                >
                  {data.emotion}
                </motion.div>
              </motion.div>
            )
          })}
        </div>
      </div>
      <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-3">
        {periods.slice(0, 3).map((period, idx) => {
          const data = circadian[period.key] || {}
          return (
            <motion.div
              key={period.key}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.5 + idx * 0.1 }}
              className="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg"
            >
              <p className="text-xs text-gray-500">{period.label}</p>
              <p className="text-sm font-medium mt-1">📱 {data.push || 'Notification'}</p>
              <p className="text-xs text-emerald-500 mt-0.5">🎵 {data.tone || 'Tonalité'}</p>
            </motion.div>
          )
        })}
      </div>
    </motion.div>
  )
}

// Carte Behavioral Nudges
function NudgesCard({ nudges }) {
  const icons = ['🏆', '⚡', '🎯']
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6"
    >
      <div className="flex items-center gap-2 mb-4">
        <Target className="w-5 h-5 text-emerald-500" />
        <h3 className="font-semibold">Behavioral Nudges (Nudge Theory)</h3>
        <span className="text-xs text-gray-400">Prix Nobel 2017</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {(nudges || []).map((nudge, idx) => (
          <motion.div
            key={idx}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: idx * 0.1 }}
            whileHover={{ scale: 1.02, y: -3 }}
            className="p-4 rounded-xl bg-gradient-to-br from-emerald-500/5 to-teal-500/5 border border-emerald-500/20 text-center cursor-pointer"
          >
            <div className="text-3xl mb-2">{icons[idx]}</div>
            <p className="font-semibold text-sm">{nudge.name}</p>
            <p className="text-xs text-gray-500 mt-1">{nudge.mechanism}</p>
            <p className="text-xs text-emerald-500 mt-2">✨ {nudge.application}</p>
          </motion.div>
        ))}
      </div>
    </motion.div>
  )
}

// Carte Hook Model
function HookModelCard({ hook }) {
  const steps = [
    { key: 'trigger', label: '🎣 Déclencheur', color: 'border-amber-500' },
    { key: 'action', label: '⚡ Action', color: 'border-blue-500' },
    { key: 'variable_reward', label: '🎁 Récompense', color: 'border-emerald-500' },
    { key: 'investment', label: '💎 Investissement', color: 'border-purple-500' }
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6"
    >
      <div className="flex items-center gap-2 mb-4">
        <Zap className="w-5 h-5 text-emerald-500" />
        <h3 className="font-semibold">Ethical Hook Model (Habitudes saines)</h3>
      </div>
      <div className="flex flex-wrap gap-4 justify-between">
        {steps.map((step, idx) => (
          <motion.div
            key={step.key}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.1 }}
            whileHover={{ y: -5 }}
            className={`flex-1 min-w-[120px] p-3 rounded-xl border-l-4 ${step.color} bg-gray-50 dark:bg-gray-800/30 text-center`}
          >
            <p className="text-sm font-semibold">{step.label}</p>
            <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
              {hook[step.key] || 'À définir'}
            </p>
          </motion.div>
        ))}
      </div>
    </motion.div>
  )
}

// Carte Cognitive Load
function CognitiveLoadCard({ load }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6"
    >
      <div className="flex items-center gap-2 mb-4">
        <Activity className="w-5 h-5 text-emerald-500" />
        <h3 className="font-semibold">Cognitive Load Optimizer</h3>
        <span className="text-xs text-gray-400">John Sweller - Théorie de la charge cognitive</span>
      </div>
      <div className="flex items-center gap-4 flex-wrap">
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.5 }}
          className="w-24 h-24 rounded-full bg-gradient-to-br from-emerald-500 to-teal-500 flex flex-col items-center justify-center text-white"
        >
          <span className="text-2xl font-bold">{load.max_steps || 3}</span>
          <span className="text-[10px]">étapes max</span>
        </motion.div>
        <div className="flex-1">
          <p className="font-medium">{load.recommendation || 'Processus simplifié'}</p>
          <p className="text-sm text-gray-500 mt-1">Niveau de complexité: {load.complexity_level || 'bas'}</p>
          <div className="flex flex-wrap gap-2 mt-2">
            {(load.ux_principles || []).map((principle, idx) => (
              <span key={idx} className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-xs">
                {principle}
              </span>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  )
}

// ==================== COMPOSANT PRINCIPAL ====================

export default function AgentPage() {
  const { agentId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()

  const { result, projectDesc, thoughts } = location.state || {}
  const agentThoughts = thoughts || result?.agent_thoughts || []

  const [activeTab, setActiveTab] = useState('overview')

  const isVisionAgent = agentId === 'visual_semiotics'

  // Configuration des onglets selon l'agent
  const getTabs = () => {
    if (isVisionAgent) {
      return [
        { id: 'overview', label: 'Vue d\'ensemble', icon: BarChart3 },
        { id: 'visual_identity', label: '🎨 Identité Visuelle', icon: Palette },
        { id: 'strategy_analysis', label: '📊 Analyse Stratégique', icon: Target },
        { id: 'design_system', label: '⚙️ Design System', icon: Code }
      ]
    }

    if (agentId === 'emotional_intelligence') {
      return [
        { id: 'overview', label: 'Vue d\'ensemble', icon: BarChart3 },
        { id: 'market_emotions', label: '🛡️ Analyse Concurrentielle', icon: ShieldAlert }, // Nouvelles fonctions
        { id: 'psychology', label: '🧠 Stratégie Cognitive', icon: Brain }, // Tes anciennes cartes
      ]
    }
    return [
      { id: 'overview', label: 'Vue d\'ensemble', icon: BarChart3 },
      { id: 'risks', label: 'Risques', icon: AlertTriangle },
      { id: 'signals', label: 'Signaux faibles', icon: Zap },
      { id: 'strategy', label: 'Stratégie', icon: Lightbulb },
      { id: 'opportunities', label: 'Opportunités', icon: Target },
      { id: 'premortem', label: 'Pre-Mortem', icon: Shield }
    ]
  }

  const tabs = getTabs()

  // Données spécifiques Vision
  const colorPalette = result?.color_palette || {}
  const typography = result?.typography || {}
  const composition = result?.composition || {}
  const visualStyle = result?.visual_style || {}
  const vibeCheck = result?.vibe_check || { aesthetic_score: 85, premium_perception: 80, tech_perception: 70, trust_perception: 75, feedback_analysis: "" }
  const semioticSquare = result?.semiotic_square || { primary_position: "", secondary_position: "", avoidance_zones: [], visual_posture: "" }
  const temporalAging = result?.temporal_aging || { aging_score: 7.5, timeless_elements: [], trends_to_avoid: [], refresh_schedule: "" }
  const designTokens = result?.design_tokens || {}
  const competitors = result?.web_sources || []
  const semioticsAnalysis = result?.semiotics_analysis || { dominant_signifiers: [], competitor_archetypes: [], counter_signifiers: [], recommended_archetype: "", strategic_rationale: "" }

  // Données Trend (fallback)
  const analysis = result?.analysis || {}
  const weakSignals = result?.weak_signals || []
  const risks = analysis?.main_risks || []
  const recommendations = analysis?.recommendations || []
  const gapAnalysis = result?.gap_analysis || {}
  const preMortem = result?.pre_mortem || {}

  // Après les déclarations de variables existantes, ajoute pour l'agent Emotion :
  const oceanProfile = result?.ocean_profile || {}
  const circadianEmotions = result?.circadian_emotions || {}
  const toneOfVoice = result?.tone_of_voice || {}
  const ethicalHook = result?.ethical_hook || {}
  const behavioralNudges = result?.behavioral_nudges || []
  const cognitiveLoad = result?.cognitive_load || {}

  // Fonction utilitaire pour extraire le texte d'un objet
  const getText = (obj) => {
    if (!obj) return ''
    if (typeof obj === 'string') return obj
    if (typeof obj === 'object') {
      return obj.description || obj.name || obj.lesson || obj.details || JSON.stringify(obj)
    }
    return String(obj)
  }

  const config = {
    trend_hunter: { name: 'TREND HUNTER', icon: TrendingUp, iconColor: 'text-blue-500', bgGradient: 'from-blue-500/20 to-cyan-500/20' },
    visual_semiotics: { name: 'VISUAL SEMIOTICS', icon: Eye, iconColor: 'text-purple-500', bgGradient: 'from-purple-500/20 to-pink-500/20' },
    emotional_intelligence: { name: 'EMOTIONAL AI', icon: Brain, iconColor: 'text-emerald-500', bgGradient: 'from-emerald-500/20 to-teal-500/20' },
    creative_director: { name: 'CREATIVE UNIT', icon: Sparkles, iconColor: 'text-orange-500', bgGradient: 'from-orange-500/20 to-red-500/20' }
  }[agentId] || { name: 'AGENT', icon: Target, iconColor: 'text-gray-500', bgGradient: '' }

  const Icon = config.icon

  if (!result) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-500">Chargement des données...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      {/* Header (identique) */}
      <div className="sticky top-0 z-10 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="text-sm">Retour</span>
          </button>
        </div>
      </div>

      {/* Hero (identique) */}
      <div className={`bg-gradient-to-r ${config.bgGradient} border-b border-gray-200 dark:border-gray-800`}>
        <div className="max-w-6xl mx-auto px-6 py-8">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <div className="flex items-center gap-3 mb-3">
                {Icon && <Icon className={`w-8 h-8 ${config.iconColor}`} />}
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{config.name}</h1>
              </div>
              <p className="text-gray-600 dark:text-gray-400 max-w-xl">
                {isVisionAgent
                  ? "Analyse sémiotique avancée : identité visuelle, stratégie et design system"
                  : "Analyse stratégique avancée du marché, des risques et des opportunités"}
              </p>
              <div className="flex items-center gap-2 mt-4">
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                <span className="text-xs text-gray-500">
                  Modèle: {result.model_used || "Groq/Llama-4-Scout-17B"}
                </span>
              </div>
            </div>
            <ConfidenceCurve value={result?.score * 10 || 75} />
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 sticky top-[73px] z-10">
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex gap-6 overflow-x-auto">
            {tabs.map((tab) => {
              const TabIcon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`
                    flex items-center gap-2 py-3 border-b-2 transition-all whitespace-nowrap
                    ${activeTab === tab.id
                      ? 'border-purple-500 text-purple-500'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                    }
                  `}
                >
                  <TabIcon className="w-4 h-4" />
                  <span className="text-sm font-medium">{tab.label}</span>
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-6xl mx-auto px-6 py-8">
        <AnimatePresence mode="wait">

          {/* ==================== VUE D'ENSEMBLE (COMMUNE) ==================== */}
          {activeTab === 'overview' && (
            <motion.div
              key="overview"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-6"
            >
              {/* Stats */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-white dark:bg-gray-900 rounded-xl p-5 border border-gray-200 dark:border-gray-800">
                  <div className="flex items-center gap-2 mb-2">
                    {isVisionAgent ? <Palette className="w-4 h-4 text-purple-500" /> : <AlertTriangle className="w-4 h-4 text-red-500" />}
                    <span className="text-sm text-gray-500">
                      {isVisionAgent ? "Score de cohérence" : "Score de risque"}
                    </span>
                  </div>
                  <div className="text-2xl font-bold">
                    {isVisionAgent ? `${vibeCheck.aesthetic_score || 92}%` : `${analysis.risk_score || 7}/10`}
                  </div>
                </div>
                <div className="bg-white dark:bg-gray-900 rounded-xl p-5 border border-gray-200 dark:border-gray-800">
                  <div className="flex items-center gap-2 mb-2">
                    {isVisionAgent ? <Type className="w-4 h-4 text-purple-500" /> : <Zap className="w-4 h-4 text-yellow-500" />}
                    <span className="text-sm text-gray-500">
                      {isVisionAgent ? "Polices recommandées" : "Signaux détectés"}
                    </span>
                  </div>
                  <div className="text-2xl font-bold">
                    {isVisionAgent ? "2" : weakSignals.length}
                  </div>
                </div>
                <div className="bg-white dark:bg-gray-900 rounded-xl p-5 border border-gray-200 dark:border-gray-800">
                  <div className="flex items-center gap-2 mb-2">
                    {isVisionAgent ? <Code className="w-4 h-4 text-purple-500" /> : <Lightbulb className="w-4 h-4 text-green-500" />}
                    <span className="text-sm text-gray-500">
                      {isVisionAgent ? "Design Tokens" : "Recommandations"}
                    </span>
                  </div>
                  <div className="text-2xl font-bold">
                    {isVisionAgent ? "Prêts à l'emploi" : recommendations.length}
                  </div>
                </div>
              </div>

              {/* Chaîne de raisonnement */}
              {agentThoughts && agentThoughts.length > 0 && (
                <div className="bg-gray-50 dark:bg-gray-900/50 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
                  <div className="p-4 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
                    <div className="flex items-center gap-2">
                      <Brain className="w-4 h-4 text-purple-500" />
                      <h3 className="font-semibold">Chaîne de raisonnement</h3>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">Réflexions internes de l'agent pendant l'analyse</p>
                  </div>
                  <div className="p-4 space-y-3 max-h-80 overflow-y-auto">
                    {agentThoughts.map((thought, idx) => (
                      <div key={idx} className="flex gap-3">
                        <div className="w-6 h-6 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center flex-shrink-0">
                          <span className="text-xs text-purple-500">🧠</span>
                        </div>
                        <div className="flex-1">
                          <p className="text-sm text-gray-700 dark:text-gray-300 font-mono leading-relaxed">{thought}</p>
                          <p className="text-xs text-gray-400 mt-1">Étape {idx + 1}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Contexte du projet */}
              <div className="bg-white dark:bg-gray-900 rounded-xl p-5 border border-gray-200 dark:border-gray-800">
                <h3 className="font-semibold mb-3">Contexte du projet</h3>
                <p className="text-gray-600 dark:text-gray-400">{projectDesc}</p>
              </div>

              {/* Modèle utilisé */}
              {result.model_used && (
                <div className="bg-gradient-to-r from-purple-500/5 to-pink-500/5 rounded-xl p-4 border border-purple-500/20">
                  <p className="text-xs text-gray-500">Modèle d'IA utilisé</p>
                  <p className="text-sm font-mono text-purple-600 dark:text-purple-400">{result.model_used}</p>
                </div>
              )}
            </motion.div>
          )}

          {/* ==================== VISION - IDENTITÉ VISUELLE ==================== */}
          {isVisionAgent && activeTab === 'visual_identity' && (
            <motion.div
              key="visual_identity"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-6"
            >
              {/* Palette de couleurs */}
              <ColorPaletteCard palette={colorPalette} />

              {/* Typographie */}
              <TypographyCard typography={typography} />

              {/* Style visuel */}
              <StyleCard style={visualStyle} />
            </motion.div>
          )}

          {/* ==================== VISION - ANALYSE STRATÉGIQUE ==================== */}
          {isVisionAgent && activeTab === 'strategy_analysis' && (
            <motion.div
              key="strategy_analysis"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-6"
            >
              {/* Vibe Check */}
              <VibeCheckCard vibe={vibeCheck} />

              {/* Temporal Aging */}
              <TemporalAgingCard aging={temporalAging} />

              {/* Carré sémiotique de Greimas */}
              <SemioticSquareCard semiotic={semioticSquare} />

              {/* Analyse sémiotique des concurrents */}
              {semioticsAnalysis.dominant_signifiers && semioticsAnalysis.dominant_signifiers.length > 0 && (
                <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <Hash className="w-5 h-5 text-purple-500" />
                    <h3 className="font-semibold">Analyse sémiotique des concurrents</h3>
                  </div>
                  <div className="space-y-4">
                    <div>
                      <p className="text-xs text-gray-500 mb-2">Signifiants dominants</p>
                      <div className="flex flex-wrap gap-2">
                        {(semioticsAnalysis.dominant_signifiers || []).map((s, idx) => (
                          <span key={idx} className="px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded text-sm">
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 mb-2">Contre-signifiants (opportunités)</p>
                      <div className="flex flex-wrap gap-2">
                        {(semioticsAnalysis.counter_signifiers || []).map((s, idx) => (
                          <span key={idx} className="px-2 py-1 bg-green-100 dark:bg-green-950/30 text-green-700 dark:text-green-400 rounded text-sm">
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 mb-2">Archétype recommandé</p>
                      <p className="text-sm font-medium text-purple-600 dark:text-purple-400">
                        {semioticsAnalysis.recommended_archetype || "Non défini"}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </motion.div>
          )}

          {/* ==================== VISION - DESIGN SYSTEM ==================== */}
          {isVisionAgent && activeTab === 'design_system' && (
            <motion.div
              key="design_system"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-6"
            >
              {/* Design Tokens */}
              <DesignTokensCard tokens={designTokens} />

              {/* Composition */}
              <CompositionCard composition={composition} />

              {/* Concurrents analysés */}
              <CompetitorAnalysisCard competitors={competitors} />
            </motion.div>
          )}

          {/* ==================== TREND - RISQUES ==================== */}
          {!isVisionAgent && activeTab === 'risks' && (
            <motion.div
              key="risks"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-3"
            >
              {risks.map((risk, idx) => (
                <RiskCard key={idx} risk={risk} index={idx} />
              ))}
            </motion.div>
          )}

          {/* ==================== TREND - SIGNAUX ==================== */}
          {!isVisionAgent && activeTab === 'signals' && (
            <motion.div
              key="signals"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-3"
            >
              {weakSignals.map((signal, idx) => (
                <WeakSignalCard key={idx} signal={signal} index={idx} />
              ))}
            </motion.div>
          )}

          {/* ==================== TREND - STRATÉGIE ==================== */}
          {!isVisionAgent && activeTab === 'strategy' && (
            <motion.div
              key="strategy"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-3"
            >
              {recommendations.map((rec, idx) => (
                <RecommendationCard key={idx} recommendation={rec} index={idx} />
              ))}
            </motion.div>
          )}

          {/* ==================== TREND - OPPORTUNITÉS ==================== */}
          {!isVisionAgent && activeTab === 'opportunities' && (
            <motion.div
              key="opportunities"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-6"
            >
              <div className="bg-gradient-to-r from-blue-500/10 to-cyan-500/10 rounded-xl border border-blue-500/20 p-6">
                <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
                  <Target className="w-5 h-5 text-blue-500" />
                  Zone Blue Ocean
                </h3>
                <p className="text-gray-700 dark:text-gray-300">
                  {getText(gapAnalysis.blue_ocean_opportunity)}
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-3">Zones d'opportunité</h3>
                <div className="grid grid-cols-1 gap-3">
                  {(gapAnalysis.opportunity_zones || []).map((zone, idx) => (
                    <div key={idx} className="bg-green-50 dark:bg-green-950/20 rounded-xl p-4 border border-green-200 dark:border-green-800">
                      <p className="text-gray-700 dark:text-gray-300">{getText(zone)}</p>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <h3 className="font-semibold mb-3">Zones saturées (à éviter)</h3>
                <div className="flex flex-wrap gap-2">
                  {(gapAnalysis.crowded_zones || []).map((zone, idx) => (
                    <span key={idx} className="px-3 py-1 bg-red-100 dark:bg-red-950/30 text-red-600 dark:text-red-400 rounded-full text-sm">
                      {getText(zone)}
                    </span>
                  ))}
                </div>
              </div>
            </motion.div>
          )}

          {/* ==================== TREND - PRE-MORTEM ==================== */}
          {!isVisionAgent && activeTab === 'premortem' && (
            <motion.div
              key="premortem"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-6"
            >
              <div className="bg-gradient-to-r from-red-500/10 to-orange-500/10 rounded-xl border border-red-500/20 p-6">
                <div className="flex items-center gap-3 mb-4">
                  <Shield className="w-6 h-6 text-red-500" />
                  <h2 className="text-xl font-bold text-gray-900 dark:text-white">Pre-Mortem 2028</h2>
                </div>
                <p className="text-gray-700 dark:text-gray-300 text-lg font-medium mb-2">
                  {getText(preMortem.primary_cause)}
                </p>
                <p className="text-gray-600 dark:text-gray-400">
                  {getText(preMortem.lessons_learned)}
                </p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
                  <h3 className="font-semibold mb-3 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-red-500" />
                    Causes secondaires
                  </h3>
                  <ul className="space-y-2">
                    {(preMortem.secondary_causes || []).map((cause, idx) => (
                      <li key={idx} className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2">
                        <span className="text-red-500 mt-1">•</span>
                        {getText(cause)}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
                  <h3 className="font-semibold mb-3 flex items-center gap-2">
                    <Rocket className="w-4 h-4 text-green-500" />
                    Comment l'éviter
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {getText(preMortem.could_it_have_been_saved)}
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {/* ==================== EMOTION - ANALYSE CONCURRENTIELLE (LES 5 FONCTIONS) ==================== */}

          {agentId === 'emotional_intelligence' && activeTab === 'market_emotions' && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-8">

              {/* 1. Sentiment Velocity (Tableau des scores) */}
              <SentimentVelocityTable data={result?.sentiment_velocity || []} />

              {/* 2. & 5. Social Sentiment Mining + Hall of Shame (Capture) */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                  <SentimentMining mining={result?.sentiment_mining || []} />
                </div>
                <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-red-500/20 shadow-sm">
                  <h4 className="text-xs font-bold text-red-500 mb-3 uppercase flex items-center gap-2">
                    <Camera className="w-4 h-4" /> Capture Hall of Shame
                  </h4>
                  <div dangerouslySetInnerHTML={{ __html: result?.hall_of_shame_html }} className="scale-90 origin-top" />
                </div>
              </div>

              {/* 3. Competitor Voice-Matching */}
              <VoiceMatching matching={result?.voice_matching || {}} />

              {/* 4. Customer Journey Map */}
              <CustomerJourneyMap journey={result?.customer_journey || []} />

              {/* 5. Loyalty Mechanism Audit */}
              <LoyaltyAudit audit={result?.loyalty_audit || {}} />

            </motion.div>
          )}

          {/* ==================== EMOTION - STRATÉGIE COGNITIVE ==================== */}

          {agentId === 'emotional_intelligence' && activeTab === 'psychology' && (
            <motion.div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <OceanProfileCard profile={oceanProfile} />
                <ToneOfVoiceCard tone={toneOfVoice} /> {/* Tes anciennes cartes */}
              </div>
              <NudgesCard nudges={behavioralNudges} />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <HookModelCard hook={ethicalHook} />
                <CognitiveLoadCard load={cognitiveLoad} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}