'use client'
// src/pages/AgentPage.jsx - Version avec onglets spécifiques par agent (Next.js compatible)
import { useParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { useState, useEffect } from 'react'
import { useApp } from '../context/AppContext'
import {
  ArrowLeft, TrendingUp, AlertTriangle, Lightbulb, Target, Zap,
  Shield, Rocket, BarChart3, ChevronDown, ChevronUp, Link2, ExternalLink,
  Brain, Sparkles, Palette, Type, Layout, Eye, Clock, Code, Palette as PaletteIcon,
  Droplet, Square, Activity, Hash, MessageSquare, ShieldAlert, Search, Gift, Mic2, Camera, Map as MapIcon,
  Users, FlaskConical, ChevronRight, Star, TrendingDown, ArrowUpRight, CheckCircle2, XCircle, Link,  Database,
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
        <h3 className="font-semibold">Benchmark Concurrents</h3>
        <span className="ml-auto text-xs text-gray-400">{competitors?.length || 0} sources analysées</span>
      </div>
      <div className="space-y-2">
        {competitors?.slice(0, 5).map((comp, idx) => (
          <div key={idx} className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-800 last:border-0">
            <span className="text-sm">{comp.title || comp.name}</span>
            {comp.url && (
              <a href={comp.url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 hover:underline">
                Voir →
              </a>
            )}
          </div>
        ))}
      </div>
    </motion.div>
  )
}

// Variantes de mise en page pour chaque piste logo
const LOGO_VARIANTS = {
  light: {
    bg: 'bg-white',
    border: 'border border-gray-200',
    layout: 'flex-row',        // icône à gauche, texte à droite
    iconSize: 'w-16 h-16',
    nameCss: (primary) => ({ color: '#1a1a2e', fontWeight: 800 }),
    taglineCss: () => ({ color: '#64748b' }),
  },
  dark: {
    bg: 'bg-gray-950',
    border: 'border border-gray-800',
    layout: 'flex-row',
    iconSize: 'w-16 h-16',
    nameCss: () => ({ color: '#ffffff', fontWeight: 800, letterSpacing: '0.05em' }),
    taglineCss: () => ({ color: '#94a3b8' }),
  },
  badge: {
    bg: 'bg-gray-50',
    border: 'border border-gray-200',
    layout: 'flex-col',        // icône en haut, texte en dessous centré
    iconSize: 'w-20 h-20',
    nameCss: (primary) => ({ color: primary, fontWeight: 700 }),
    taglineCss: () => ({ color: '#94a3b8', letterSpacing: '0.15em', textTransform: 'uppercase' }),
  },
}

function LogoHybride({ iconSrc, companyName, label, variant = 'light', primaryColor = '#0D9488', fontFamily = 'Inter' }) {
  const [svgCopied, setSvgCopied] = useState(false)
  const v = LOGO_VARIANTS[variant]
  const isRow = v.layout === 'flex-row'
  const tagline = companyName ? companyName.split(' ').slice(1).join(' ') || 'Brand' : 'Brand'

  const exportLogo = () => {
    // Crée un SVG exportable combinant icône + texte
    const textColor = variant === 'dark' ? '#ffffff' : (variant === 'badge' ? primaryColor : '#1a1a2e')
    const bgColor = variant === 'dark' ? '#0a0a0a' : (variant === 'badge' ? '#f8f9fa' : '#ffffff')
    const svgExport = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 160"><rect width="400" height="160" fill="${bgColor}"/><text x="200" y="90" text-anchor="middle" font-family="system-ui,-apple-system,sans-serif" font-size="48" font-weight="800" fill="${textColor}">${companyName || 'Brand'}</text></svg>`
    navigator.clipboard.writeText(svgExport)
    setSvgCopied(true)
    setTimeout(() => setSvgCopied(false), 2000)
  }

  return (
    <div className={`rounded-2xl overflow-hidden ${v.bg} ${v.border} flex flex-col`}>
      {/* Zone logo */}
      <div
        className={`flex-1 flex items-center justify-center gap-4 p-8 ${isRow ? 'flex-row' : 'flex-col'}`}
        style={{ minHeight: 180 }}
      >
        {/* Icône générée par FLUX.1 */}
        {iconSrc ? (
          <img
            src={iconSrc}
            alt="Brand mark"
            className={`${v.iconSize} object-contain rounded-xl flex-shrink-0`}
            style={{ imageRendering: 'crisp-edges' }}
          />
        ) : (
          <div
            className={`${v.iconSize} rounded-xl flex-shrink-0 flex items-center justify-center border-2 border-dashed`}
            style={{ borderColor: primaryColor + '40' }}
          >
            <Sparkles className="w-6 h-6" style={{ color: primaryColor }} />
          </div>
        )}

        {/* Texte HTML net — jamais une image */}
        <div className={`flex flex-col ${isRow ? 'items-start' : 'items-center text-center'}`}>
          <span
            style={{
              fontFamily: `"${fontFamily}", system-ui, -apple-system, sans-serif`,
              fontSize: isRow ? '1.75rem' : '1.5rem',
              lineHeight: 1.1,
              ...v.nameCss(primaryColor),
            }}
          >
            {companyName || 'Votre Marque'}
          </span>
          {variant === 'badge' && (
            <span
              style={{
                fontFamily: 'system-ui, -apple-system, sans-serif',
                fontSize: '0.65rem',
                marginTop: '0.4rem',
                ...v.taglineCss(),
              }}
            >
              {tagline} · Est. 2025
            </span>
          )}
          {variant === 'light' && (
            <span
              style={{
                fontFamily: 'system-ui, -apple-system, sans-serif',
                fontSize: '0.75rem',
                marginTop: '0.25rem',
                ...v.taglineCss(),
              }}
            >
              {tagline}
            </span>
          )}
        </div>
      </div>

      {/* Footer avec label + export */}
      <div
        className={`px-4 py-2.5 flex items-center justify-between border-t ${
          variant === 'dark' ? 'border-gray-800 bg-gray-900' : 'border-gray-100 bg-gray-50'
        }`}
      >
        <p className={`text-xs font-medium truncate flex-1 ${variant === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
          {label}
        </p>
        <button
          onClick={exportLogo}
          className={`text-[10px] ml-2 shrink-0 transition-colors ${
            variant === 'dark'
              ? 'text-gray-500 hover:text-purple-400'
              : 'text-gray-400 hover:text-purple-600'
          }`}
        >
          {svgCopied ? '✓ Copié' : '↗ Exporter'}
        </button>
      </div>
    </div>
  )
}

function VisionImageCard({ src, label, tall = false }) {
  const [expanded, setExpanded] = useState(false)
  const [svgCopied, setSvgCopied] = useState(false)

  const isSvg = src && src.trimStart().startsWith('<svg')

  const copySvg = () => {
    navigator.clipboard.writeText(src).then(() => {
      setSvgCopied(true)
      setTimeout(() => setSvgCopied(false), 2000)
    })
  }

  if (!src) {
    return (
      <div className={`rounded-xl border border-dashed border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 flex flex-col items-center justify-center gap-2 ${tall ? 'min-h-[340px]' : 'min-h-[180px]'}`}>
        <div className="w-8 h-8 rounded-full border-2 border-dashed border-gray-300 dark:border-gray-700 flex items-center justify-center">
          <Sparkles className="w-4 h-4 text-gray-400" />
        </div>
        <p className="text-xs text-gray-400">Génération en cours...</p>
        {label && <p className="text-xs text-gray-500 font-medium px-3 text-center">{label}</p>}
      </div>
    )
  }

  if (isSvg) {
    // Rendu SVG inline — vectoriel, net à toutes les tailles
    return (
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden bg-white group flex flex-col">
        <div
          className={`bg-white flex items-center justify-center p-6 cursor-pointer transition-all duration-300 ${expanded ? 'py-10' : ''}`}
          onClick={() => setExpanded(!expanded)}
          dangerouslySetInnerHTML={{ __html: src.replace(/<svg/, '<svg style="width:100%;height:auto;max-height:200px"') }}
        />
        <div className="px-3 py-2 flex items-center justify-between border-t border-gray-100 bg-gray-50">
          <p className="text-xs font-medium text-gray-700 truncate flex-1">{label}</p>
          <div className="flex items-center gap-2 ml-2">
            <button
              onClick={copySvg}
              className="text-[10px] text-gray-400 hover:text-purple-600 transition-colors"
              title="Copier le code SVG"
            >
              {svgCopied ? '✓ Copié' : 'Copier SVG'}
            </button>
            <span className="text-gray-300">|</span>
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-[10px] text-gray-400 hover:text-gray-600"
            >
              {expanded ? 'Réduire ↑' : 'Agrandir ↓'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Rendu image WEBP (moodboard FLUX.1)
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden bg-white dark:bg-gray-900 group">
      <div
        className={`overflow-hidden cursor-pointer transition-all duration-500 ${tall ? (expanded ? '' : 'max-h-[340px]') : (expanded ? '' : 'max-h-[200px]')}`}
        onClick={() => setExpanded(!expanded)}
      >
        <img
          src={src}
          alt={label}
          className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
        />
      </div>
      <div className="px-3 py-2 flex items-center justify-between border-t border-gray-100 dark:border-gray-800">
        <p className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate flex-1">{label}</p>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[10px] text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 ml-2 shrink-0"
        >
          {expanded ? 'Réduire ↑' : 'Agrandir ↓'}
        </button>
      </div>
    </div>
  )
}



// Image générée par IA (FLUX.1)
function AIImagePanel({ src, title, description }) {
  const [expanded, setExpanded] = useState(false)
  if (!src) return null
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white border border-gray-200 rounded-2xl overflow-hidden"
    >
      <div className="bg-gray-50 border-b border-gray-200 px-5 py-3 flex items-center gap-3">
        <div className="w-7 h-7 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center flex-shrink-0">
          <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="font-semibold text-gray-900 text-sm truncate">{title}</h4>
          {description && <p className="text-gray-400 text-xs truncate">{description}</p>}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-[9px] text-indigo-500 bg-indigo-50 border border-indigo-100 px-2 py-0.5 rounded-full font-mono">
            FLUX.1 · IA
          </span>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-[10px] text-gray-400 hover:text-gray-600 transition-colors px-2 py-1 rounded-lg hover:bg-gray-100"
          >
            {expanded ? 'Réduire' : 'Agrandir'}
          </button>
        </div>
      </div>
      <div className={`overflow-hidden transition-all duration-300 ${expanded ? '' : 'max-h-52'}`}>
        <img
          src={src}
          alt={title}
          className="w-full object-cover"
          style={expanded ? {} : { maxHeight: 208 }}
        />
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



// ==================== CHARTS SVG TREND HUNTER ====================

// Matrice Risques (Probabilité × Impact)
function RiskMatrixChart({ risks }) {
  const [hovered, setHovered] = useState(null)
  const W = 460, H = 300
  const pad = { l: 52, r: 20, t: 20, b: 44 }
  const cW = W - pad.l - pad.r
  const cH = H - pad.t - pad.b

  const quadrants = [
    { x: 0,    y: 0,    w: cW / 2, h: cH / 2, label: 'Surveiller',  fill: '#f0fdf4' },
    { x: cW/2, y: 0,    w: cW / 2, h: cH / 2, label: 'Critique',    fill: '#fff7ed' },
    { x: 0,    y: cH/2, w: cW / 2, h: cH / 2, label: 'Accepter',    fill: '#f9fafb' },
    { x: cW/2, y: cH/2, w: cW / 2, h: cH / 2, label: 'Atténuer',    fill: '#fef2f2' },
  ]

  const riskColor = (prob, impact) => {
    const score = (prob / 100) * impact
    if (score >= 6) return '#dc2626'
    if (score >= 3.5) return '#d97706'
    return '#16a34a'
  }

  const xProb = (p) => (p / 100) * cW
  const yImp = (v) => cH - ((v - 1) / 9) * cH

  const yTicks = [1, 3, 5, 7, 9]
  const xTicks = [0, 25, 50, 75, 100]

  return (
    <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
      <div className="bg-gray-50 border-b border-gray-200 px-5 py-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-white border border-gray-200 flex items-center justify-center">
          <AlertTriangle className="w-4 h-4 text-red-500" />
        </div>
        <div>
          <h3 className="font-semibold text-gray-900 text-sm">Matrice des Risques</h3>
          <p className="text-gray-500 text-xs">Probabilité × Impact · positionnement des risques identifiés</p>
        </div>
      </div>
      <div className="p-4">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 300 }}>
          <g transform={`translate(${pad.l},${pad.t})`}>
            {/* Quadrants */}
            {quadrants.map((q, i) => (
              <rect key={i} x={q.x} y={q.y} width={q.w} height={q.h}
                fill={q.fill} stroke="#e5e7eb" strokeWidth={0.5} />
            ))}
            {/* Quadrant labels */}
            {quadrants.map((q, i) => (
              <text key={i} x={q.x + q.w / 2} y={q.y + q.h / 2}
                textAnchor="middle" dominantBaseline="middle"
                fontSize={9} fill="#9ca3af" fontWeight={500} letterSpacing={0.5}>
                {q.label.toUpperCase()}
              </text>
            ))}
            {/* Y axis ticks */}
            {yTicks.map(v => (
              <g key={v}>
                <line x1={-4} y1={yImp(v)} x2={cW} y2={yImp(v)}
                  stroke="#f3f4f6" strokeWidth={1} />
                <text x={-8} y={yImp(v)} textAnchor="end" dominantBaseline="middle"
                  fontSize={9} fill="#9ca3af">{v}</text>
              </g>
            ))}
            {/* X axis ticks */}
            {xTicks.map(v => (
              <g key={v}>
                <line x1={xProb(v)} y1={0} x2={xProb(v)} y2={cH + 4}
                  stroke="#f3f4f6" strokeWidth={1} />
                <text x={xProb(v)} y={cH + 14} textAnchor="middle"
                  fontSize={9} fill="#9ca3af">{v}%</text>
              </g>
            ))}
            {/* Axis labels */}
            <text x={cW / 2} y={cH + 34} textAnchor="middle" fontSize={10} fill="#6b7280" fontWeight={500}>
              Probabilité
            </text>
            <text x={-38} y={cH / 2} textAnchor="middle" fontSize={10} fill="#6b7280" fontWeight={500}
              transform={`rotate(-90, -38, ${cH / 2})`}>
              Impact
            </text>
            {/* Risk dots */}
            {risks.map((risk, idx) => {
              const prob = risk.probability ?? 50 + idx * 7
              const impact = risk.impact ?? 5 + (idx % 3)
              const cx = xProb(Math.min(prob, 99))
              const cy = yImp(Math.min(Math.max(impact, 1), 10))
              const col = riskColor(prob, impact)
              const isHov = hovered === idx
              return (
                <g key={idx}
                  onMouseEnter={() => setHovered(idx)}
                  onMouseLeave={() => setHovered(null)}
                  style={{ cursor: 'pointer' }}>
                  <circle cx={cx} cy={cy} r={isHov ? 10 : 7}
                    fill={col} fillOpacity={0.15} stroke={col} strokeWidth={1.5} />
                  <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle"
                    fontSize={8} fill={col} fontWeight={700}>{idx + 1}</text>
                  {isHov && (
                    <foreignObject x={cx - 90} y={cy - 58} width={180} height={52}>
                      <div xmlns="http://www.w3.org/1999/xhtml"
                        className="bg-white border border-gray-200 shadow-lg rounded-lg px-3 py-2 text-xs pointer-events-none">
                        <p className="font-semibold text-gray-900 truncate">
                          {typeof risk.risk === 'string' ? risk.risk : (risk.risk?.risk || `Risque ${idx + 1}`)}
                        </p>
                        <p className="text-gray-500 mt-0.5">Prob. {prob}% · Impact {impact}/10</p>
                      </div>
                    </foreignObject>
                  )}
                </g>
              )
            })}
          </g>
        </svg>
        {/* Legend */}
        <div className="flex flex-wrap gap-3 mt-1 px-2">
          {risks.map((risk, idx) => {
            const prob = risk.probability ?? 50
            const impact = risk.impact ?? 5
            return (
              <div key={idx} className="flex items-center gap-1.5 text-xs text-gray-600">
                <span className="font-bold text-gray-800">{idx + 1}.</span>
                <span className="truncate max-w-[160px]">
                  {typeof risk.risk === 'string' ? risk.risk : (risk.risk?.risk || `Risque ${idx + 1}`)}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// Roadmap Gantt (recommandations)
function StrategyRoadmap({ recommendations }) {
  const months = Array.from({ length: 12 }, (_, i) => i + 1)
  const phaseColors = {
    'Phase 1': { bar: '#3730a3', bg: '#eef2ff', text: '#3730a3' },
    'Phase 2': { bar: '#065f46', bg: '#ecfdf5', text: '#065f46' },
    'Phase 3': { bar: '#78350f', bg: '#fffbeb', text: '#78350f' }
  }
  const priorityLabel = { high: 'Élevée', medium: 'Moyenne', low: 'Faible' }
  const priorityDot = { high: 'bg-red-400', medium: 'bg-amber-400', low: 'bg-gray-300' }

  return (
    <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
      <div className="bg-gray-50 border-b border-gray-200 px-5 py-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-white border border-gray-200 flex items-center justify-center">
          <BarChart3 className="w-4 h-4 text-indigo-600" />
        </div>
        <div>
          <h3 className="font-semibold text-gray-900 text-sm">Roadmap Stratégique</h3>
          <p className="text-gray-500 text-xs">Plan d'exécution sur 12 mois · priorités et phases</p>
        </div>
      </div>
      <div className="p-5">
        {/* Month header */}
        <div className="flex mb-3">
          <div className="w-52 flex-shrink-0" />
          <div className="flex-1 grid grid-cols-12 gap-0">
            {months.map(m => (
              <div key={m} className="text-center text-[9px] text-gray-400 font-medium">M{m}</div>
            ))}
          </div>
        </div>
        {/* Rows */}
        <div className="space-y-2">
          {recommendations.map((rec, idx) => {
            const recText = typeof rec === 'string' ? rec : rec.recommendation
            const phase = rec.phase || 'Phase 1'
            const start = (rec.month_start || 1) - 1
            const end = rec.month_end || 4
            const colors = phaseColors[phase] || phaseColors['Phase 1']
            const prio = rec.priority || 'medium'
            return (
              <motion.div key={idx}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.07 }}
                className="flex items-center gap-0">
                <div className="w-52 flex-shrink-0 pr-3 flex items-start gap-1.5">
                  <span className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${priorityDot[prio] || 'bg-gray-300'}`} />
                  <p className="text-[11px] text-gray-700 leading-tight line-clamp-2">{recText}</p>
                </div>
                <div className="flex-1 grid grid-cols-12 gap-0 h-7 relative">
                  <div className="absolute inset-y-0" style={{
                    left: `${(start / 12) * 100}%`,
                    width: `${((end - start) / 12) * 100}%`,
                    background: colors.bar,
                    borderRadius: 4,
                    opacity: 0.85
                  }} />
                  <div className="absolute inset-y-0 flex items-center px-2" style={{
                    left: `${(start / 12) * 100}%`,
                    width: `${((end - start) / 12) * 100}%`,
                  }}>
                    <span className="text-[9px] font-bold text-white truncate">{phase}</span>
                  </div>
                </div>
              </motion.div>
            )
          })}
        </div>
        {/* Phase legend */}
        <div className="flex gap-4 mt-4 pt-3 border-t border-gray-100">
          {Object.entries(phaseColors).map(([phase, colors]) => (
            <div key={phase} className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-sm" style={{ background: colors.bar }} />
              <span className="text-[10px] text-gray-500">{phase}</span>
            </div>
          ))}
          <div className="ml-auto flex gap-3">
            {Object.entries(priorityLabel).map(([key, label]) => (
              <div key={key} className="flex items-center gap-1">
                <span className={`w-1.5 h-1.5 rounded-full ${priorityDot[key]}`} />
                <span className="text-[10px] text-gray-400">{label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// Blue Ocean Canvas (ligne concurrents vs startup)
function BlueOceanCanvas({ gapAnalysis }) {
  const factors = gapAnalysis.canvas_factors || []
  const [hovered, setHovered] = useState(null)

  if (factors.length === 0) return null

  const W = 520, H = 260
  const pad = { l: 48, r: 20, t: 20, b: 64 }
  const cW = W - pad.l - pad.r
  const cH = H - pad.t - pad.b
  const n = factors.length

  const xPos = (i) => (i / (n - 1)) * cW
  const yPos = (v) => cH - ((Math.min(Math.max(v, 0), 10)) / 10) * cH

  const compPoints = factors.map((f, i) => `${xPos(i)},${yPos(f.competitor_avg_score || 5)}`)
  const startPoints = factors.map((f, i) => `${xPos(i)},${yPos(f.startup_score || 5)}`)

  const compPath = `M ${compPoints.join(' L ')}`
  const startPath = `M ${startPoints.join(' L ')}`

  const compFill = `M ${compPoints.join(' L ')} L ${xPos(n - 1)},${cH} L 0,${cH} Z`
  const startFill = `M ${startPoints.join(' L ')} L ${xPos(n - 1)},${cH} L 0,${cH} Z`

  const yTicks = [0, 2, 4, 6, 8, 10]

  return (
    <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
      <div className="bg-gray-50 border-b border-gray-200 px-5 py-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-white border border-gray-200 flex items-center justify-center">
          <Target className="w-4 h-4 text-indigo-600" />
        </div>
        <div>
          <h3 className="font-semibold text-gray-900 text-sm">Blue Ocean Canvas</h3>
          <p className="text-gray-500 text-xs">Comparaison facteurs clés · concurrents vs votre projet</p>
        </div>
      </div>
      <div className="p-4">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 260 }}>
          <defs>
            <linearGradient id="compGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#dc2626" stopOpacity={0.08} />
              <stop offset="100%" stopColor="#dc2626" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="startGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1d4ed8" stopOpacity={0.12} />
              <stop offset="100%" stopColor="#1d4ed8" stopOpacity={0} />
            </linearGradient>
          </defs>
          <g transform={`translate(${pad.l},${pad.t})`}>
            {/* Grid */}
            {yTicks.map(v => (
              <g key={v}>
                <line x1={0} y1={yPos(v)} x2={cW} y2={yPos(v)} stroke="#f3f4f6" strokeWidth={1} />
                <text x={-6} y={yPos(v)} textAnchor="end" dominantBaseline="middle"
                  fontSize={8} fill="#9ca3af">{v}</text>
              </g>
            ))}
            {/* Area fills */}
            <path d={compFill} fill="url(#compGrad)" />
            <path d={startFill} fill="url(#startGrad)" />
            {/* Lines */}
            <path d={compPath} fill="none" stroke="#ef4444" strokeWidth={1.5} strokeDasharray="4 2" />
            <path d={startPath} fill="none" stroke="#2563eb" strokeWidth={2} />
            {/* Factor dots & labels */}
            {factors.map((f, i) => (
              <g key={i}>
                <line x1={xPos(i)} y1={0} x2={xPos(i)} y2={cH} stroke="#f3f4f6" strokeWidth={1} />
                {/* Competitor dot */}
                <circle cx={xPos(i)} cy={yPos(f.competitor_avg_score || 5)} r={hovered === i ? 5 : 3.5}
                  fill="#ef4444" stroke="white" strokeWidth={1}
                  onMouseEnter={() => setHovered(i)} onMouseLeave={() => setHovered(null)}
                  style={{ cursor: 'pointer' }} />
                {/* Startup dot */}
                <circle cx={xPos(i)} cy={yPos(f.startup_score || 5)} r={hovered === i ? 5 : 3.5}
                  fill="#2563eb" stroke="white" strokeWidth={1}
                  onMouseEnter={() => setHovered(i)} onMouseLeave={() => setHovered(null)}
                  style={{ cursor: 'pointer' }} />
                {/* Factor label */}
                <text x={xPos(i)} y={cH + 12} textAnchor="middle" fontSize={8} fill="#6b7280"
                  transform={n > 5 ? `rotate(-35, ${xPos(i)}, ${cH + 12})` : ''}>
                  {f.factor?.length > 14 ? f.factor.slice(0, 13) + '…' : f.factor}
                </text>
                {hovered === i && (
                  <foreignObject x={xPos(i) - 70} y={-50} width={140} height={48}>
                    <div xmlns="http://www.w3.org/1999/xhtml"
                      className="bg-white border border-gray-200 shadow-lg rounded-lg px-2 py-1.5 text-xs pointer-events-none">
                      <p className="font-semibold text-gray-900 truncate">{f.factor}</p>
                      <p className="text-red-500">Concurrents : {f.competitor_avg_score}/10</p>
                      <p className="text-blue-600">Votre projet : {f.startup_score}/10</p>
                    </div>
                  </foreignObject>
                )}
              </g>
            ))}
          </g>
        </svg>
        <div className="flex gap-6 justify-center mt-1">
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <div className="w-4 h-0.5 bg-red-400" style={{ borderTop: '2px dashed #ef4444' }} />
            <span>Concurrents (moy.)</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <div className="w-4 h-0.5 bg-blue-600" />
            <span>Votre projet</span>
          </div>
        </div>
      </div>
    </div>
  )
}

// Timeline Pre-Mortem
function PreMortemTimeline({ timeline }) {
  const severityConfig = {
    low:      { color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0', label: 'Signal faible' },
    medium:   { color: '#d97706', bg: '#fffbeb', border: '#fde68a', label: 'Alerte' },
    high:     { color: '#dc2626', bg: '#fef2f2', border: '#fecaca', label: 'Critique' },
    critical: { color: '#7c3aed', bg: '#faf5ff', border: '#e9d5ff', label: 'Point de rupture' }
  }

  if (!timeline || timeline.length === 0) return null

  return (
    <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
      <div className="bg-gray-50 border-b border-gray-200 px-5 py-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-white border border-gray-200 flex items-center justify-center">
          <Clock className="w-4 h-4 text-gray-600" />
        </div>
        <div>
          <h3 className="font-semibold text-gray-900 text-sm">Chronologie de l'Échec</h3>
          <p className="text-gray-500 text-xs">Séquence d'événements simulée sur 5 ans</p>
        </div>
      </div>
      <div className="p-6">
        <div className="relative">
          {/* Vertical line */}
          <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-100" />
          <div className="space-y-6">
            {timeline.map((event, idx) => {
              const cfg = severityConfig[event.severity] || severityConfig.medium
              return (
                <motion.div key={idx}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.12 }}
                  className="flex gap-4 pl-10 relative">
                  {/* Node */}
                  <div className="absolute left-0 w-8 h-8 rounded-full border-2 flex items-center justify-center flex-shrink-0"
                    style={{ background: cfg.bg, borderColor: cfg.color }}>
                    <span className="text-[9px] font-black" style={{ color: cfg.color }}>{idx + 1}</span>
                  </div>
                  <div className="flex-1 pb-2">
                    <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                      <span className="text-xs font-bold text-gray-500 font-mono">{event.year}</span>
                      <span className="text-[9px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wide"
                        style={{ color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.border}` }}>
                        {cfg.label}
                      </span>
                    </div>
                    <p className="text-sm text-gray-700 leading-relaxed">{event.event}</p>
                  </div>
                </motion.div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

// ==================== COMPOSANTS POUR EMOTION AGENT ====================

//Sentiment Velocity
function SentimentVelocityTable({ data }) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
      {/* Header sobre */}
      <div className="bg-gray-50 border-b border-gray-200 p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-white border border-gray-200 flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 text-base">Sentiment Velocity</h3>
              <p className="text-gray-500 text-xs">Évolution de la satisfaction client sur 12 mois</p>
            </div>
          </div>
          <span className="text-xs text-gray-500 bg-white border border-gray-200 px-3 py-1 rounded-full">Live data</span>
        </div>
      </div>

      <div className="p-5 space-y-4">
        {data.map((item, idx) => {
          const prev = item.prev_score || 0
          const curr = item.current_score || 0
          const delta = (curr - prev).toFixed(1)
          const isDown = item.trend === 'down'
          const prevPct = (prev / 5) * 100
          const currPct = (curr / 5) * 100

          return (
            <motion.div
              key={idx}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.12 }}
              className="group"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-sm text-gray-900 dark:text-white">{item.competitor}</span>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${isDown ? 'bg-red-100 text-red-600 dark:bg-red-950/50 dark:text-red-400' : 'bg-emerald-100 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-400'}`}>
                      {isDown ? '↘' : '↗'} {isDown ? '' : '+'}{delta}
                    </span>
                    {item.source_url && (
                      <a href={item.source_url} target="_blank" rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-[10px] text-indigo-500 bg-indigo-50 dark:bg-indigo-950/30 px-2 py-0.5 rounded-full hover:underline transition-all">
                        <ExternalLink className="w-2.5 h-2.5" />
                        {item.source_label || 'Source'}
                      </a>
                    )}
                  </div>
                  {item.key_issue && (
                    <p className="text-xs text-gray-500 mt-0.5 italic">{item.key_issue}</p>
                  )}
                </div>
                <div className="text-right ml-4 flex-shrink-0">
                  <span className={`text-xl font-black ${isDown ? 'text-red-500' : 'text-emerald-500'}`}>
                    {curr}/5
                  </span>
                  <p className="text-[10px] text-gray-400">vs {prev}/5 avant</p>
                </div>
              </div>

              {/* Dual progress bar */}
              <div className="relative h-3 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${prevPct}%` }}
                  transition={{ duration: 0.8, delay: idx * 0.12 }}
                  className="absolute top-0 left-0 h-full bg-gray-300 dark:bg-gray-600 rounded-full"
                />
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${currPct}%` }}
                  transition={{ duration: 1, delay: idx * 0.12 + 0.2 }}
                  className={`absolute top-0 left-0 h-full rounded-full ${isDown ? 'bg-gradient-to-r from-red-500 to-rose-400' : 'bg-gradient-to-r from-emerald-500 to-teal-400'}`}
                />
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

// Platform icons for sources
function PlatformBadge({ source, sourceUrl, label }) {
  const platforms = {
    trustpilot: { color: 'bg-green-500', icon: '★', textColor: 'text-white' },
    reddit: { color: 'bg-orange-500', icon: '●', textColor: 'text-white' },
    google: { color: 'bg-blue-500', icon: 'G', textColor: 'text-white' },
  }
  const key = (source || '').toLowerCase()
  const platform = Object.entries(platforms).find(([k]) => key.includes(k))?.[1] || { color: 'bg-gray-400', icon: '○', textColor: 'text-white' }

  if (sourceUrl) {
    return (
      <a href={sourceUrl} target="_blank" rel="noopener noreferrer"
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${platform.color} ${platform.textColor} hover:opacity-80 transition-opacity`}>
        <span>{platform.icon}</span>
        <span>{label || source}</span>
        <ExternalLink className="w-2 h-2" />
      </a>
    )
  }
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${platform.color} ${platform.textColor}`}>
      <span>{platform.icon}</span>
      <span>{label || source}</span>
    </span>
  )
}

//Social Sentiment Mining (Le Mur des Lamentations)
function SentimentMining({ mining }) {
  const severityConfig = {
    critical: { label: '🔴 CRITIQUE', bg: 'bg-red-50 dark:bg-red-950/20', border: 'border-red-500', badge: 'bg-red-500 text-white', pulse: true },
    high: { label: '🟠 ÉLEVÉ', bg: 'bg-orange-50 dark:bg-orange-950/20', border: 'border-orange-400', badge: 'bg-orange-400 text-white', pulse: false },
    medium: { label: '🟡 MOYEN', bg: 'bg-yellow-50 dark:bg-yellow-950/20', border: 'border-yellow-400', badge: 'bg-yellow-400 text-white', pulse: false },
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-8 h-8 rounded-xl bg-red-100 dark:bg-red-950/30 flex items-center justify-center">
          <Search className="w-4 h-4 text-red-500" />
        </div>
        <div>
          <h3 className="font-bold text-sm">Le Mur des Lamentations</h3>
          <p className="text-[11px] text-gray-500">Verbatims réels extraits des plateformes d'avis</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {mining.map((item, idx) => {
          const sev = severityConfig[item.severity] || severityConfig.medium
          return (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
              whileHover={{ scale: 1.01, transition: { duration: 0.15 } }}
              className={`rounded-2xl border-l-4 ${sev.border} ${sev.bg} p-4 shadow-sm`}
            >
              {/* Header row */}
              <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${sev.badge} ${sev.pulse ? 'animate-pulse' : ''}`}>
                    {sev.label}
                  </span>
                  <span className="text-xs font-bold text-gray-700 dark:text-gray-300 uppercase tracking-wide">{item.topic}</span>
                  {item.competitor && (
                    <span className="text-[10px] text-gray-500 italic">— {item.competitor}</span>
                  )}
                </div>
                <PlatformBadge source={item.source} sourceUrl={item.source_url} label={item.source} />
              </div>

              {/* Verbatim quote */}
              <blockquote className="text-sm text-gray-700 dark:text-gray-300 italic leading-relaxed mb-3 pl-3 border-l-2 border-gray-300 dark:border-gray-600">
                "{item.verbatim}"
              </blockquote>

              {/* Opportunity */}
              <div className="bg-emerald-50 dark:bg-emerald-950/20 rounded-xl px-3 py-2 border border-emerald-200 dark:border-emerald-900">
                <p className="text-[10px] font-bold text-emerald-600 uppercase mb-0.5">💡 Opportunité StartWise</p>
                <p className="text-xs text-emerald-800 dark:text-emerald-300">{item.opportunity}</p>
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

//Loyalty Audit (Le Showroom des Récompenses)
function LoyaltyAudit({ audit }) {
  return (
    <div className="rounded-2xl overflow-hidden border border-gray-200 dark:border-gray-800">
      <div className="bg-gray-50 border-b border-gray-200 p-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-xl bg-white border border-gray-200 flex items-center justify-center">
          <Gift className="w-4 h-4 text-emerald-600" />
        </div>
        <div>
          <h3 className="font-semibold text-gray-900 text-sm">Showroom des Récompenses</h3>
          <p className="text-gray-500 text-xs">Concurrents vs votre approche</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 bg-white dark:bg-gray-900">
        {/* Système Concurrent */}
        <div className="p-5 border-b md:border-b-0 md:border-r border-gray-100 dark:border-gray-800">
          <div className="flex items-center gap-2 mb-3">
            <XCircle className="w-4 h-4 text-red-400" />
            <span className="text-xs font-bold text-red-400 uppercase">Approche Concurrente</span>
          </div>
          <h4 className="font-bold text-gray-900 dark:text-white mb-1">{audit.cold_system?.name}</h4>
          <p className="text-sm text-gray-500 mb-3 leading-relaxed">{audit.cold_system?.desc}</p>
          <div className="p-2.5 bg-gray-100 dark:bg-gray-800 rounded-lg text-xs font-mono text-red-400 opacity-80">
            {audit.cold_system?.visual}
          </div>
        </div>

        {/* Système StartWise */}
        <div className="p-5 bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-950/20 dark:to-teal-950/20">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
            <span className="text-xs font-bold text-emerald-500 uppercase">Approche StartWise</span>
          </div>
          <h4 className="font-bold text-gray-900 dark:text-white mb-1">{audit.warm_system?.name}</h4>
          <p className="text-sm text-gray-700 dark:text-gray-300 mb-3 leading-relaxed">{audit.warm_system?.desc}</p>
          <motion.div
            animate={{ scale: [1, 1.02, 1] }}
            transition={{ repeat: Infinity, duration: 2.5 }}
            className="p-2.5 bg-gradient-to-r from-emerald-500 to-teal-500 rounded-lg text-xs font-bold text-white shadow-lg shadow-emerald-500/20">
            {audit.warm_system?.visual}
          </motion.div>
        </div>
      </div>
    </div>
  )
}

//Voice-Matching (Le Battle des Tonalités)
function VoiceMatching({ matching }) {
  return (
    <div className="rounded-2xl overflow-hidden border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
      {/* Scenario header */}
      {matching.scenario && (
        <div className="bg-gray-50 dark:bg-gray-800/50 px-5 py-3 border-b border-gray-100 dark:border-gray-800">
          <div className="flex items-start gap-2">
            <span className="text-gray-400 text-sm mt-0.5">📋</span>
            <div>
              <p className="text-[10px] text-gray-400 uppercase font-bold tracking-wide mb-0.5">Scénario testé</p>
              <p className="text-sm text-gray-700 dark:text-gray-300 italic">"{matching.scenario}"</p>
              {matching.source_url && (
                <a href={matching.source_url} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 mt-1 text-[10px] text-indigo-500 hover:underline">
                  <ExternalLink className="w-2.5 h-2.5" />
                  Voir avis {matching.competitor_name || 'concurrent'} →
                </a>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="p-5">
        <div className="flex items-center gap-2 mb-4">
          <Mic2 className="w-4 h-4 text-purple-500" />
          <h3 className="font-bold text-sm">Battle des Tonalités — Voice Matching</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          {/* Bad reply */}
          <div className="relative">
            <div className="absolute -top-2 left-4 bg-red-500 text-white text-[9px] font-bold px-2 py-0.5 rounded-full uppercase">
              {matching.competitor_name || 'Concurrent'} — Robotique
            </div>
            <div className="bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900 rounded-xl p-4 pt-5">
              <div className="flex gap-2">
                <div className="w-7 h-7 rounded-full bg-red-200 dark:bg-red-900 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-xs">🤖</span>
                </div>
                <p className="text-sm text-gray-700 dark:text-gray-300 italic leading-relaxed">"{matching.bad_reply}"</p>
              </div>
            </div>
          </div>

          {/* Good reply */}
          <div className="relative">
            <div className="absolute -top-2 left-4 bg-emerald-500 text-white text-[9px] font-bold px-2 py-0.5 rounded-full uppercase">
              StartWise — Empathique
            </div>
            <div className="bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900 rounded-xl p-4 pt-5">
              <div className="flex gap-2">
                <div className="w-7 h-7 rounded-full bg-emerald-200 dark:bg-emerald-900 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-xs">✨</span>
                </div>
                <p className="text-sm font-medium text-gray-800 dark:text-gray-200 italic leading-relaxed">"{matching.good_reply}"</p>
              </div>
            </div>
          </div>
        </div>

        {matching.personality_gap && (
          <div className="bg-purple-50 dark:bg-purple-950/20 border border-purple-200 dark:border-purple-900 rounded-xl p-3">
            <p className="text-xs text-purple-700 dark:text-purple-300">
              <span className="font-bold">🎯 Personality Gap : </span>{matching.personality_gap}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

// ==================== CUSTOMER JOURNEY MAP — WAVE PATH PROFESSIONNEL ====================
function CustomerJourneyMap({ journey }) {
  const [expandedStep, setExpandedStep] = useState(null)
  if (!journey || journey.length === 0) return null

  // Palette sobre et professionnelle
  const stepColors = [
    { border: '#4f46e5', bg: '#eef2ff' },
    { border: '#b45309', bg: '#fef3c7' },
    { border: '#b91c1c', bg: '#fef2f2' },
    { border: '#047857', bg: '#ecfdf5' },
    { border: '#6d28d9', bg: '#f5f3ff' },
    { border: '#0369a1', bg: '#f0f9ff' },
  ]

  const n = journey.length
  const nodeD = 76
  const svgH = 230
  const topY = 68
  const bottomY = 162
  const minW = Math.max(n * 170, 680)

  // Construit le chemin SVG en vague (bezier) entre les noeuds
  const pts = journey.map((_, i) => ({
    x: (i / Math.max(n - 1, 1)) * (minW - nodeD) + nodeD / 2,
    y: i % 2 === 0 ? topY : bottomY,
  }))
  let pathD = `M ${pts[0].x} ${pts[0].y}`
  for (let i = 1; i < pts.length; i++) {
    const p = pts[i - 1], c = pts[i]
    const mx = (p.x + c.x) / 2
    pathD += ` C ${mx} ${p.y} ${mx} ${c.y} ${c.x} ${c.y}`
  }

  return (
    <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm">
      {/* Header sobre */}
      <div className="px-6 py-4 bg-gray-50 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-gray-200 flex items-center justify-center">
            <MapIcon className="w-3.5 h-3.5 text-gray-500" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-800">Customer Journey Map</h3>
            <p className="text-[11px] text-gray-400">Parcours idéal — basé sur les erreurs concurrentes · cliquer pour les détails</p>
          </div>
        </div>
        <span className="text-[10px] font-medium text-gray-500 bg-white border border-gray-200 px-2.5 py-1 rounded-full">
          {n} étapes
        </span>
      </div>

      {/* Wave visual */}
      <div className="px-6 pt-6 pb-4 overflow-x-auto">
        <div className="relative" style={{ minWidth: minW, height: svgH }}>
          {/* SVG wave connector */}
          <svg className="absolute inset-0 w-full h-full overflow-visible"
            viewBox={`0 0 ${minW} ${svgH}`} preserveAspectRatio="xMidYMid meet">
            {/* Ligne pointillée de base */}
            <line x1={nodeD / 2} y1={svgH / 2} x2={minW - nodeD / 2} y2={svgH / 2}
              stroke="#f1f5f9" strokeWidth="1.5" strokeDasharray="6 5" />
            {/* Vague bezier */}
            <motion.path d={pathD} fill="none" stroke="#e2e8f0"
              strokeWidth="2.5" strokeLinecap="round"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 1 }}
              transition={{ duration: 1.6, ease: 'easeInOut' }}
            />
          </svg>

          {/* Noeuds */}
          {journey.map((item, idx) => {
            const col = stepColors[idx % stepColors.length]
            const { x, y } = pts[idx]
            const isTop = idx % 2 === 0
            const isExpanded = expandedStep === idx
            return (
              <div key={idx} style={{ position: 'absolute', left: x, top: y, transform: 'translate(-50%,-50%)', zIndex: 10 }}>
                {/* Label au-dessus pour nœuds hauts */}
                {isTop && (
                  <div className="absolute bottom-full mb-3 left-1/2 -translate-x-1/2 text-center" style={{ minWidth: 110 }}>
                    <p className="text-[9px] font-bold text-gray-700 uppercase tracking-widest leading-tight">{item.step}</p>
                    <p className="text-[9px] text-gray-400 mt-0.5 font-medium">{item.emotion}</p>
                  </div>
                )}

                {/* Cercle */}
                <motion.button
                  onClick={() => setExpandedStep(isExpanded ? null : idx)}
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.95 }}
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: idx * 0.1, type: 'spring', stiffness: 260, damping: 20 }}
                  className="relative flex items-center justify-center rounded-full cursor-pointer"
                  style={{
                    width: nodeD, height: nodeD,
                    background: col.bg,
                    border: `2.5px solid ${isExpanded ? col.border : col.border + 'aa'}`,
                    boxShadow: isExpanded
                      ? `0 0 0 5px ${col.border}18, 0 6px 20px ${col.border}22`
                      : '0 2px 10px rgba(0,0,0,0.07)',
                  }}
                >
                  <span className="text-2xl select-none">{item.icon || '📍'}</span>
                  {/* Badge numéro */}
                  <div className="absolute -top-2 -right-2 w-5 h-5 rounded-full border-2 border-white text-[8px] font-black flex items-center justify-center shadow"
                    style={{ background: col.border, color: '#fff' }}>
                    {idx + 1}
                  </div>
                  {/* Point de type */}
                  <div className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-3 h-3 rounded-full border-2 border-white shadow-sm"
                    style={{ background: item.type === 'delight' ? '#059669' : item.type === 'friction' ? '#dc2626' : '#94a3b8' }} />
                </motion.button>

                {/* Label en-dessous pour nœuds bas */}
                {!isTop && (
                  <div className="absolute top-full mt-3 left-1/2 -translate-x-1/2 text-center" style={{ minWidth: 110 }}>
                    <p className="text-[9px] font-bold text-gray-700 uppercase tracking-widest leading-tight">{item.step}</p>
                    <p className="text-[9px] text-gray-400 mt-0.5 font-medium">{item.emotion}</p>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Légende */}
        <div className="flex items-center gap-5 pt-4 mt-2 border-t border-gray-100">
          {[
            { color: '#059669', label: 'Moment Plaisir' },
            { color: '#dc2626', label: 'Point de Friction' },
            { color: '#94a3b8', label: 'Neutre' },
          ].map(l => (
            <div key={l.label} className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full" style={{ background: l.color }} />
              <span className="text-[10px] text-gray-400 font-medium">{l.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Liste détaillée expandable */}
      <div className="border-t border-gray-100 divide-y divide-gray-50">
        {journey.map((item, idx) => {
          const col = stepColors[idx % stepColors.length]
          const isExpanded = expandedStep === idx
          return (
            <motion.div key={idx} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: idx * 0.05 }}>
              <button
                onClick={() => setExpandedStep(isExpanded ? null : idx)}
                className="w-full text-left px-5 py-3.5 hover:bg-gray-50 transition-colors flex items-center gap-3"
              >
                <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm flex-shrink-0 border"
                  style={{ background: col.bg, borderColor: col.border }}>
                  {item.icon || '📍'}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-gray-800">{idx + 1}. {item.step}</span>
                    <span className={`text-[9px] font-semibold px-2 py-0.5 rounded-full border ${item.type === 'delight' ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      : item.type === 'friction' ? 'bg-red-50 text-red-700 border-red-200'
                        : 'bg-gray-100 text-gray-500 border-gray-200'
                      }`}>
                      {item.type === 'delight' ? '✦ Moment Plaisir' : item.type === 'friction' ? '⚠ Friction' : '— Neutre'}
                    </span>
                  </div>
                  {item.persona_action && <p className="text-[11px] text-gray-400 italic truncate mt-0.5">{item.persona_action}</p>}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {item.emotion_score && (
                    <span className="text-sm font-bold" style={{ color: col.border }}>{item.emotion_score}%</span>
                  )}
                  <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                </div>
              </button>

              <AnimatePresence>
                {isExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="px-5 pb-5 space-y-3 bg-gray-50">
                      <p className="text-sm text-gray-600 leading-relaxed pt-3">{item.desc}</p>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {item.competitor_mistake && (
                          <div className="bg-red-50 border border-red-100 rounded-xl p-3">
                            <p className="text-[10px] font-bold text-red-600 uppercase mb-1">✕ Erreur Concurrente</p>
                            <p className="text-xs text-red-700 leading-relaxed">{item.competitor_mistake}</p>
                          </div>
                        )}
                        {item.our_advantage && (
                          <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-3">
                            <p className="text-[10px] font-bold text-emerald-700 uppercase mb-1">✓ Notre Avantage</p>
                            <p className="text-xs text-emerald-700 leading-relaxed">{item.our_advantage}</p>
                          </div>
                        )}
                      </div>
                      <div className="flex gap-2 flex-wrap">
                        {item.duration && (
                          <span className="text-[10px] px-2.5 py-1 rounded-md bg-white border border-gray-200 text-gray-500 inline-flex items-center gap-1">
                            <Clock className="w-2.5 h-2.5" />{item.duration}
                          </span>
                        )}
                        {item.kpi && (
                          <span className="text-[10px] px-2.5 py-1 rounded-md text-white inline-flex items-center gap-1"
                            style={{ background: col.border }}>
                            <Target className="w-2.5 h-2.5" />{item.kpi}
                          </span>
                        )}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

// ==================== ANIMATED COUNTER ====================
function AnimatedCounter({ target, suffix = '', duration = 1500 }) {
  const [count, setCount] = useState(0)
  useEffect(() => {
    let start = 0
    const step = target / (duration / 16)
    const timer = setInterval(() => {
      start += step
      if (start >= target) { setCount(target); clearInterval(timer) }
      else setCount(Math.floor(start))
    }, 16)
    return () => clearInterval(timer)
  }, [target, duration])
  return <span>{count}{suffix}</span>
}

// ==================== COGNITIVE STRATEGY — DARK PRO ====================
function CognitiveStrategyBanner({ strategy }) {
  if (!strategy || Object.keys(strategy).length === 0) return null
  const persona = strategy.target_persona || {}
  const abTests = strategy.ab_tests || []
  const diffs = strategy.key_differentiators || []

  return (
    <div className="space-y-4">
      {/* Insight Block */}
      {strategy.insight_summary && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl bg-white border border-gray-200 p-5"
        >
          <div className="flex items-center gap-2 mb-3">
            <div className="w-1.5 h-4 rounded-full bg-indigo-500" />
            <span className="text-[10px] font-bold text-indigo-600 uppercase tracking-widest">Synthèse Stratégique · Multi-Agents</span>
          </div>
          <p className="text-gray-700 text-sm leading-relaxed">{strategy.insight_summary}</p>
        </motion.div>
      )}

      {/* 3-col grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Persona */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="rounded-2xl bg-white border border-gray-200 p-5"
        >
          <div className="flex items-center gap-2 mb-4">
            <Users className="w-3.5 h-3.5 text-gray-400" />
            <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Persona Cible</span>
          </div>
          {persona.name && (
            <div className="mb-4 pb-4 border-b border-gray-100">
              <p className="font-bold text-gray-900 text-sm">{persona.name}</p>
              {persona.archetype && <p className="text-xs text-gray-400 mt-0.5 italic">{persona.archetype}</p>}
            </div>
          )}
          {persona.pain_points && persona.pain_points.length > 0 && (
            <div className="space-y-2 mb-4">
              <p className="text-[9px] font-bold text-red-500 uppercase tracking-widest">Pain Points</p>
              {persona.pain_points.slice(0, 3).map((p, i) => (
                <motion.div key={i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.2 + i * 0.08 }}
                  className="flex gap-2 items-start"
                >
                  <span className="w-1 h-1 rounded-full bg-red-400 mt-1.5 flex-shrink-0" />
                  <p className="text-xs text-gray-600 leading-relaxed">{p}</p>
                </motion.div>
              ))}
            </div>
          )}
          {persona.trigger_words && persona.trigger_words.length > 0 && (
            <div>
              <p className="text-[9px] font-bold text-gray-400 uppercase tracking-widest mb-2">Mots déclencheurs</p>
              <div className="flex flex-wrap gap-1">
                {persona.trigger_words.map((w, i) => (
                  <span key={i} className="text-[10px] px-2 py-0.5 rounded-md bg-gray-100 border border-gray-200 text-gray-600 font-medium">
                    {w}
                  </span>
                ))}
              </div>
            </div>
          )}
        </motion.div>

        {/* Differentiators */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="rounded-2xl bg-white border border-gray-200 p-5"
        >
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="w-3.5 h-3.5 text-gray-400" />
            <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Différenciateurs</span>
          </div>
          <div className="space-y-3">
            {diffs.map((d, i) => (
              <motion.div key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.3 + i * 0.1 }}
                className="flex gap-2.5 items-start group"
              >
                <div className="w-4 h-4 rounded-full border border-emerald-300 bg-emerald-50 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                </div>
                <p className="text-xs text-gray-600 leading-relaxed group-hover:text-gray-900 transition-colors">{d}</p>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* A/B Tests */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="rounded-2xl bg-white border border-gray-200 p-5"
        >
          <div className="flex items-center gap-2 mb-4">
            <FlaskConical className="w-3.5 h-3.5 text-gray-400" />
            <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">A/B Tests IA</span>
          </div>
          <div className="space-y-3">
            {abTests.slice(0, 3).map((test, i) => (
              <motion.div key={i}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.4 + i * 0.1 }}
                className="rounded-xl bg-gray-50 border border-gray-200 p-3"
              >
                <p className="text-[10px] text-gray-500 italic mb-2 leading-relaxed">{test.hypothesis}</p>
                <div className="space-y-1 mb-2">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[9px] text-gray-400 font-bold w-3">A</span>
                    <span className="text-[10px] text-gray-500">{test.variant_a}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[9px] text-indigo-500 font-bold w-3">B</span>
                    <span className="text-[10px] text-gray-700 font-medium">{test.variant_b}</span>
                  </div>
                </div>
                {test.expected_lift && (
                  <div className="text-[9px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-md inline-block">
                    {test.expected_lift}
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  )
}

// ==================== COGNITIVE PATHWAY — Tunnel friction zéro ====================
function CognitivePathway({ load }) {
  const steps = load?.ux_principles || []
  const maxSteps = load?.max_steps || 3
  const principles = steps.length > 0 ? steps : ['Choisir', 'Certifier', 'Payer']

  const STEP_ICONS = [
    // Loupe / Découverte
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>,
    // Bouclier / Confiance
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
    // Carte bancaire / Paiement
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>,
    // Check / Validation
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>,
  ]

  const colors = ['#6366f1', '#10b981', '#f59e0b', '#3b82f6']

  return (
    <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-100 dark:border-gray-800 flex items-center gap-3">
        <Zap className="w-4 h-4 text-emerald-500" />
        <h3 className="font-semibold text-sm">Cognitive Load Optimizer</h3>
        <span className="ml-auto text-xs font-mono bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 px-2 py-0.5 rounded-full">
          {maxSteps} étapes · Friction Zéro
        </span>
      </div>

      <div className="p-6 overflow-x-auto">
        <div className="flex items-center gap-0 min-w-max mx-auto" style={{ width: 'fit-content' }}>
          {principles.map((step, idx) => (
            <div key={idx} className="flex items-center">
              {/* Nœud */}
              <motion.div
                initial={{ opacity: 0, scale: 0.5 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: idx * 0.15, type: 'spring', stiffness: 200 }}
                className="flex flex-col items-center gap-2"
              >
                {/* Cercle avec icône */}
                <div
                  className="w-14 h-14 rounded-full flex items-center justify-center shadow-lg relative"
                  style={{ background: `${colors[idx % colors.length]}18`, border: `2px solid ${colors[idx % colors.length]}` }}
                >
                  <span style={{ color: colors[idx % colors.length] }}>
                    {STEP_ICONS[idx % STEP_ICONS.length]}
                  </span>
                  {/* Numéro */}
                  <span
                    className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full text-white text-[9px] font-bold flex items-center justify-center"
                    style={{ background: colors[idx % colors.length] }}
                  >
                    {idx + 1}
                  </span>
                </div>
                {/* Label */}
                <p className="text-xs font-medium text-gray-700 dark:text-gray-300 text-center max-w-[90px] leading-tight">
                  {step}
                </p>
              </motion.div>

              {/* Connecteur animé entre les étapes */}
              {idx < principles.length - 1 && (
                <div className="relative w-16 h-0.5 mx-1 flex-shrink-0" style={{ marginBottom: '1.5rem' }}>
                  <div className="absolute inset-0 bg-gray-200 dark:bg-gray-700 rounded-full" />
                  <motion.div
                    initial={{ scaleX: 0 }}
                    animate={{ scaleX: 1 }}
                    transition={{ delay: idx * 0.15 + 0.2, duration: 0.4 }}
                    className="absolute inset-0 rounded-full origin-left"
                    style={{ background: `linear-gradient(90deg, ${colors[idx % colors.length]}, ${colors[(idx + 1) % colors.length]})` }}
                  />
                  {/* Flèche */}
                  <svg className="absolute -right-1 -top-[7px] w-3.5 h-3.5" viewBox="0 0 10 10" style={{ color: colors[(idx + 1) % colors.length] }}>
                    <path d="M2 5h7M6 2l3 3-3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
                  </svg>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Recommandation */}
        {load?.recommendation && (
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-5 border-t border-gray-100 dark:border-gray-800 pt-4 italic">
            {load.recommendation}
          </p>
        )}
      </div>
    </div>
  )
}

// ==================== OCEAN RADAR CHART — SVG dynamique glassmorphism ====================
function OceanRadarChart({ profile }) {
  const traits = [
    { key: 'openness',         label: 'Ouverture',       short: 'O' },
    { key: 'conscientiousness',label: 'Rigueur',          short: 'C' },
    { key: 'extraversion',     label: 'Extraversion',    short: 'E' },
    { key: 'agreeableness',    label: 'Agréabilité',     short: 'A' },
    { key: 'neuroticism',      label: 'Névrosisme',      short: 'N' },
  ]

  const scores = traits.map(t => (profile[t.key]?.score || 50) / 100)
  const cx = 160, cy = 155, r = 110
  const levels = [0.25, 0.5, 0.75, 1]

  const angleOf = (i) => (Math.PI * 2 * i) / traits.length - Math.PI / 2

  const polarToXY = (angle, radius) => ({
    x: cx + radius * Math.cos(angle),
    y: cy + radius * Math.sin(angle),
  })

  // Points du radar
  const dataPoints = scores.map((s, i) => polarToXY(angleOf(i), s * r))
  const pathD = dataPoints.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ') + ' Z'

  if (!profile || Object.keys(profile).length === 0) {
    return (
      <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 flex items-center justify-center min-h-[300px]">
        <p className="text-sm text-gray-400">Données OCEAN non disponibles</p>
      </div>
    )
  }

  return (
    <div className="rounded-2xl border border-gray-200 dark:border-gray-800 overflow-hidden" style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)' }}>
      <div className="px-5 py-4 border-b border-white/10 flex items-center gap-3">
        <Brain className="w-4 h-4 text-indigo-400" />
        <span className="text-xs font-bold text-white/80 uppercase tracking-widest">Profil OCEAN · Big Five</span>
        <span className="ml-auto text-[10px] text-indigo-300 font-mono bg-indigo-500/20 px-2 py-0.5 rounded-full">Llama-3.1-70B</span>
      </div>

      <div className="flex flex-col items-center px-4 pb-4">
        <svg viewBox="0 0 320 310" className="w-full max-w-xs">
          <defs>
            <radialGradient id="radarGlass" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#818cf8" stopOpacity="0.15"/>
              <stop offset="100%" stopColor="#4f46e5" stopOpacity="0.05"/>
            </radialGradient>
            <filter id="glow">
              <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
              <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
          </defs>

          {/* Toile de fond glassmorphism */}
          <circle cx={cx} cy={cy} r={r + 20} fill="url(#radarGlass)" />

          {/* Niveaux concentriques */}
          {levels.map((lvl, i) => {
            const pts = traits.map((_, ti) => {
              const p = polarToXY(angleOf(ti), lvl * r)
              return `${p.x.toFixed(1)},${p.y.toFixed(1)}`
            }).join(' ')
            return <polygon key={i} points={pts} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
          })}

          {/* Axes */}
          {traits.map((t, i) => {
            const end = polarToXY(angleOf(i), r)
            return <line key={i} x1={cx} y1={cy} x2={end.x.toFixed(1)} y2={end.y.toFixed(1)} stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
          })}

          {/* Aire du radar — glassmorphism */}
          <motion.path
            d={pathD}
            fill="rgba(129,140,248,0.25)"
            stroke="#818cf8"
            strokeWidth="2"
            strokeLinejoin="round"
            filter="url(#glow)"
            initial={{ opacity: 0, scale: 0.3 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.7, ease: 'easeOut' }}
            style={{ transformOrigin: `${cx}px ${cy}px` }}
          />

          {/* Points de données */}
          {dataPoints.map((p, i) => (
            <motion.circle
              key={i}
              cx={p.x} cy={p.y} r="5"
              fill="#818cf8" stroke="white" strokeWidth="1.5"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.5 + i * 0.08, type: 'spring' }}
            />
          ))}

          {/* Labels */}
          {traits.map((t, i) => {
            const angle = angleOf(i)
            const lp = polarToXY(angle, r + 22)
            const score = profile[t.key]?.score || 50
            return (
              <g key={i}>
                <text x={lp.x.toFixed(1)} y={(lp.y - 6).toFixed(1)} textAnchor="middle"
                  fill="white" fontSize="11" fontWeight="700" fontFamily="system-ui">{t.short}</text>
                <text x={lp.x.toFixed(1)} y={(lp.y + 8).toFixed(1)} textAnchor="middle"
                  fill="rgba(255,255,255,0.5)" fontSize="9" fontFamily="system-ui">{score}%</text>
              </g>
            )
          })}
        </svg>

        {/* Légende rationale */}
        <div className="w-full space-y-1.5 px-2 pb-2">
          {traits.map((t, i) => (
            <div key={i} className="flex items-start gap-2">
              <span className="text-[10px] font-bold text-indigo-300 w-3 flex-shrink-0 mt-0.5">{t.short}</span>
              <p className="text-[10px] text-white/50 leading-relaxed">
                {profile[t.key]?.ux_recommendation || profile[t.key]?.rationale || ''}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ==================== ETHICAL HOOK INFINITY LOOP ====================
function EthicalHookInfinityLoop({ hook }) {
  if (!hook || Object.keys(hook).length === 0) {
    return (
      <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 flex items-center justify-center min-h-[300px]">
        <p className="text-sm text-gray-400">Hook Model non disponible</p>
      </div>
    )
  }

  const phases = [
    { key: 'trigger',         label: 'TRIGGER',         color: '#f59e0b', icon: '⚡', desc: hook.trigger },
    { key: 'action',          label: 'ACTION',          color: '#10b981', icon: '→',  desc: hook.action },
    { key: 'variable_reward', label: 'RÉCOMPENSE',      color: '#8b5cf6', icon: '🎁', desc: hook.variable_reward },
    { key: 'investment',      label: 'INVESTISSEMENT',  color: '#3b82f6', icon: '🔒', desc: hook.investment },
  ]

  return (
    <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-800 flex items-center gap-3">
        <Activity className="w-4 h-4 text-purple-500" />
        <span className="text-sm font-semibold">Ethical Hook Model</span>
        <span className="ml-auto text-[10px] text-purple-500 font-mono bg-purple-50 dark:bg-purple-950/40 px-2 py-0.5 rounded-full">Rétention Client</span>
      </div>

      <div className="p-5">
        {/* Infinity Loop SVG */}
        <div className="relative flex justify-center mb-5">
          <svg viewBox="0 0 340 120" className="w-full max-w-sm">
            <defs>
              {phases.map((p, i) => (
                <marker key={i} id={`arrow${i}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill={p.color} />
                </marker>
              ))}
            </defs>

            {/* Lobe gauche */}
            <motion.path
              d="M 170 60 C 170 20, 100 20, 70 60 C 40 100, 100 100, 170 60"
              fill="none" stroke="#e2e8f0" strokeWidth="14" strokeLinecap="round"
            />
            <motion.path
              d="M 170 60 C 170 20, 100 20, 70 60 C 40 100, 100 100, 170 60"
              fill="none" stroke="url(#loopGradL)" strokeWidth="4" strokeLinecap="round"
              initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
              transition={{ duration: 1.5, ease: 'easeInOut' }}
            />

            {/* Lobe droit */}
            <motion.path
              d="M 170 60 C 170 100, 240 100, 270 60 C 300 20, 240 20, 170 60"
              fill="none" stroke="#e2e8f0" strokeWidth="14" strokeLinecap="round"
            />
            <motion.path
              d="M 170 60 C 170 100, 240 100, 270 60 C 300 20, 240 20, 170 60"
              fill="none" stroke="url(#loopGradR)" strokeWidth="4" strokeLinecap="round"
              initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
              transition={{ duration: 1.5, delay: 0.3, ease: 'easeInOut' }}
            />

            <defs>
              <linearGradient id="loopGradL" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor={phases[0].color}/>
                <stop offset="100%" stopColor={phases[1].color}/>
              </linearGradient>
              <linearGradient id="loopGradR" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor={phases[2].color}/>
                <stop offset="100%" stopColor={phases[3].color}/>
              </linearGradient>
            </defs>

            {/* 4 points sur le ∞ */}
            {[
              { cx: 70,  cy: 60,  phase: 0 },
              { cx: 120, cy: 32,  phase: 1 },
              { cx: 270, cy: 60,  phase: 2 },
              { cx: 220, cy: 88, phase: 3 },
            ].map(({ cx, cy, phase }) => (
              <motion.circle key={phase} cx={cx} cy={cy} r="10"
                fill={phases[phase].color}
                initial={{ scale: 0 }} animate={{ scale: 1 }}
                transition={{ delay: 0.8 + phase * 0.15, type: 'spring' }}
              />
            ))}

            {/* Labels sur le ∞ */}
            {[
              { x: 70,  y: 60,  anchor: 'middle', dy: -16 },
              { x: 120, y: 32,  anchor: 'middle', dy: -14 },
              { x: 270, y: 60,  anchor: 'middle', dy: -16 },
              { x: 220, y: 88, anchor: 'middle', dy: 20  },
            ].map(({ x, y, anchor, dy }, i) => (
              <text key={i} x={x} y={y + dy} textAnchor={anchor}
                fill={phases[i].color} fontSize="9" fontWeight="800"
                fontFamily="system-ui, -apple-system, sans-serif">
                {phases[i].label}
              </text>
            ))}
          </svg>
        </div>

        {/* Détail des 4 phases */}
        <div className="grid grid-cols-2 gap-3">
          {phases.map((p, i) => (
            <motion.div key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 + i * 0.1 }}
              className="rounded-xl p-3 border"
              style={{ borderColor: p.color + '30', background: p.color + '08' }}
            >
              <div className="flex items-center gap-1.5 mb-1">
                <span className="text-sm">{p.icon}</span>
                <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: p.color }}>{p.label}</span>
              </div>
              <p className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed line-clamp-3">{p.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  )
}

// Carte OCEAN Profile — dark pro (conservé pour compatibilité)
function OceanProfileCard({ profile }) {
  const [hovered, setHovered] = useState(null)
  const dimensions = [
    { key: 'openness', label: 'Openness', abbr: 'O', barColor: '#818cf8' },
    { key: 'conscientiousness', label: 'Conscientiousness', abbr: 'C', barColor: '#38bdf8' },
    { key: 'extraversion', label: 'Extraversion', abbr: 'E', barColor: '#34d399' },
    { key: 'agreeableness', label: 'Agreeableness', abbr: 'A', barColor: '#fbbf24' },
    { key: 'neuroticism', label: 'Neuroticism', abbr: 'N', barColor: '#f87171' }
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl bg-white border border-gray-200 overflow-hidden"
    >
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="w-3.5 h-3.5 text-gray-400" />
          <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Profil OCEAN · Big Five</span>
        </div>
        <span className="text-[9px] text-gray-400">Réf. Netflix / Spotify</span>
      </div>
      <div className="p-5 space-y-3">
        {dimensions.map((dim, idx) => {
          const data = profile[dim.key] || { score: 50, rationale: '', ux_recommendation: '' }
          const isHovered = hovered === dim.key
          return (
            <motion.div
              key={dim.key}
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.08 }}
              onHoverStart={() => setHovered(dim.key)}
              onHoverEnd={() => setHovered(null)}
              className="cursor-pointer"
            >
              <div className="flex items-center gap-3 mb-1.5">
                <div className="w-6 h-6 rounded-md flex items-center justify-center text-[10px] font-black flex-shrink-0"
                  style={{ background: `${dim.barColor}15`, color: dim.barColor, border: `1px solid ${dim.barColor}30` }}>
                  {dim.abbr}
                </div>
                <span className="text-xs font-medium text-gray-700 flex-1">{dim.label}</span>
                <motion.span
                  animate={{ color: isHovered ? dim.barColor : '#6b7280' }}
                  className="text-sm font-black tabular-nums"
                >
                  {data.score}
                  <span className="text-[9px] font-normal text-gray-400">%</span>
                </motion.span>
              </div>
              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${data.score}%` }}
                  transition={{ duration: 1.2, delay: idx * 0.08, ease: "easeOut" }}
                  className="h-full rounded-full"
                  style={{ background: `linear-gradient(90deg, ${dim.barColor}60, ${dim.barColor})` }}
                />
              </div>
              <AnimatePresence>
                {isHovered && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="mt-2 p-2.5 bg-gray-50 rounded-lg border border-gray-100 space-y-1">
                      <p className="text-[11px] text-gray-500 leading-relaxed">{data.rationale}</p>
                      <p className="text-[11px] font-medium leading-relaxed" style={{ color: dim.barColor }}>
                        → {data.ux_recommendation}
                      </p>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )
        })}
      </div>
    </motion.div>
  )
}

// Carte Tone of Voice — dark pro
function ToneOfVoiceCard({ tone }) {
  const pillars = [
    { key: 'direct', label: 'Direct', accent: '#38bdf8' },
    { key: 'empathic', label: 'Empathique', accent: '#fb7185' },
    { key: 'inspiring', label: 'Inspirant', accent: '#fbbf24' },
    { key: 'non_judgmental', label: 'Non-Jugemental', accent: '#34d399' }
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl bg-white border border-gray-200 overflow-hidden"
    >
      <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
        <MessageSquare className="w-3.5 h-3.5 text-gray-400" />
        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Tone of Voice Matrix</span>
      </div>
      <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-3">
        {pillars.map((pillar, idx) => {
          const data = tone[pillar.key] || { example: '', when: '', micro_copy: '' }
          return (
            <motion.div
              key={pillar.key}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: idx * 0.08 }}
              whileHover={{ scale: 1.02 }}
              className="rounded-xl bg-gray-50 border border-gray-100 p-4 cursor-default"
              style={{ borderLeftColor: pillar.accent, borderLeftWidth: 2 }}
            >
              <p className="text-[10px] font-bold uppercase tracking-widest mb-2" style={{ color: pillar.accent }}>
                {pillar.label}
              </p>
              {data.example && (
                <p className="text-xs text-gray-500 italic leading-relaxed mb-2">
                  &ldquo;{data.example}&rdquo;
                </p>
              )}
              {data.when && (
                <p className="text-[10px] text-gray-400 mb-1.5">
                  <span className="text-gray-500 font-medium">Quand : </span>{data.when}
                </p>
              )}
              {data.micro_copy && (
                <div className="text-[10px] font-bold px-2 py-0.5 rounded inline-block"
                  style={{ color: pillar.accent, background: `${pillar.accent}15`, border: `1px solid ${pillar.accent}30` }}>
                  {data.micro_copy}
                </div>
              )}
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

// Carte Behavioral Nudges — dark pro
function NudgesCard({ nudges }) {
  const accents = ['#818cf8', '#fbbf24', '#34d399']

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl bg-white border border-gray-200 overflow-hidden"
    >
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Target className="w-3.5 h-3.5 text-gray-400" />
          <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Behavioral Nudges</span>
        </div>
        <span className="text-[9px] text-gray-400">Thaler & Sunstein · Nobel 2017</span>
      </div>
      <div className="p-5 grid grid-cols-1 md:grid-cols-3 gap-3">
        {(nudges || []).map((nudge, idx) => {
          const accent = accents[idx % accents.length]
          return (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
              whileHover={{ scale: 1.02, transition: { duration: 0.15 } }}
              className="rounded-xl bg-gray-50 border border-gray-100 overflow-hidden cursor-default"
            >
              <div className="h-1 w-full" style={{ background: accent }} />
              <div className="p-4">
                <p className="text-xs font-bold text-gray-800 mb-2">{nudge.name}</p>
                <p className="text-[11px] text-gray-500 leading-relaxed mb-3">{nudge.mechanism}</p>
                <p className="text-[10px] font-medium" style={{ color: accent }}>→ {nudge.application}</p>
              </div>
            </motion.div>
          )
        })}
      </div>
    </motion.div>
  )
}

// Carte Hook Model — dark pro
function HookModelCard({ hook }) {
  const steps = [
    { key: 'trigger', label: 'Déclencheur', accent: '#fbbf24', num: '01' },
    { key: 'action', label: 'Action', accent: '#38bdf8', num: '02' },
    { key: 'variable_reward', label: 'Récompense Variable', accent: '#34d399', num: '03' },
    { key: 'investment', label: 'Investissement', accent: '#c4b5fd', num: '04' }
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl bg-white border border-gray-200 overflow-hidden"
    >
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap className="w-3.5 h-3.5 text-gray-400" />
          <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Ethical Hook Model</span>
        </div>
        <span className="text-[9px] text-gray-400">Nir Eyal</span>
      </div>
      <div className="p-5 space-y-2">
        {steps.map((step, idx) => (
          <motion.div
            key={step.key}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.09 }}
            className="flex items-start gap-3 p-3 rounded-xl bg-gray-50 border border-gray-100"
          >
            <span className="text-[10px] font-black tabular-nums flex-shrink-0 mt-0.5" style={{ color: step.accent }}>{step.num}</span>
            <div className="flex-1 min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-widest mb-1" style={{ color: step.accent }}>{step.label}</p>
              <p className="text-xs text-gray-600 leading-relaxed">{hook[step.key] || 'À définir avec l\'équipe produit'}</p>
            </div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  )
}

// Carte Cognitive Load — dark pro avec compteur
function CognitiveLoadCard({ load }) {
  const maxSteps = load.max_steps || 3
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl bg-white border border-gray-200 overflow-hidden"
    >
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-gray-400" />
          <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Cognitive Load Optimizer</span>
        </div>
        <span className="text-[9px] text-gray-400">Sweller 1988</span>
      </div>
      <div className="p-5">
        {/* Metric hero */}
        <div className="flex items-center gap-4 mb-5 p-4 rounded-xl bg-gray-50 border border-gray-100">
          <div className="relative flex-shrink-0">
            <svg viewBox="0 0 64 64" className="w-16 h-16 -rotate-90">
              <circle cx="32" cy="32" r="26" fill="none" stroke="#e5e7eb" strokeWidth="6" />
              <motion.circle cx="32" cy="32" r="26" fill="none" stroke="#6366f1" strokeWidth="6"
                strokeLinecap="round"
                initial={{ strokeDasharray: '0 163.4' }}
                animate={{ strokeDasharray: `${(maxSteps / 7) * 163.4} 163.4` }}
                transition={{ duration: 1.5, ease: 'easeOut' }}
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-2xl font-black text-gray-800">{maxSteps}</span>
              <span className="text-[8px] text-gray-400">étapes</span>
            </div>
          </div>
          <div className="flex-1">
            <p className="text-xs font-bold text-gray-800 mb-1">Objectif friction zéro</p>
            <p className="text-xs text-gray-500 leading-relaxed">{load.recommendation || 'Tunnel optimisé'}</p>
          </div>
        </div>

        {/* Step indicators */}
        <div className="flex items-center gap-2 mb-4">
          {Array.from({ length: maxSteps }).map((_, i) => (
            <div key={i} className="flex items-center gap-1.5 flex-1">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: i * 0.15, type: 'spring' }}
                className="w-full h-8 rounded-lg flex items-center justify-center text-xs font-bold text-gray-700 border border-gray-200 bg-white"
                style={{ borderColor: i === 0 ? '#6366f1' : undefined, color: i === 0 ? '#6366f1' : undefined }}
              >
                {i + 1}
              </motion.div>
              {i < maxSteps - 1 && <ChevronRight className="w-3 h-3 text-gray-300 flex-shrink-0" />}
            </div>
          ))}
        </div>

        {/* Principles */}
        <div className="flex flex-wrap gap-1.5">
          {(load.ux_principles || []).map((principle, idx) => (
            <span key={idx} className="text-[10px] px-2 py-0.5 rounded-md bg-gray-100 border border-gray-200 text-gray-500">
              {principle}
            </span>
          ))}
        </div>
      </div>
    </motion.div>
  )
}

// ==================== DISRUPTION RADAR CHART — Creative Director ====================
function DisruptionRadarChart({ scores }) {
  const axes = [
    { key: 'innovation',  label: 'Innovation',   color: '#f97316' },
    { key: 'scalabilite', label: 'Scalabilité',  color: '#a855f7' },
    { key: 'risque',      label: 'Risque',       color: '#ef4444' },
    { key: 'cout',        label: 'Coût',         color: '#eab308' },
    { key: 'ux',          label: 'UX',           color: '#10b981' },
  ]
  const n = axes.length
  const cx = 160, cy = 160, R = 120
  const polarToXY = (i, r) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2
    return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)]
  }
  const gridLevels = [0.2, 0.4, 0.6, 0.8, 1.0]

  if (!scores || Object.keys(scores).length === 0) return null

  const dataPoints = axes.map((a, i) => {
    const val = (scores[a.key] || 0) / 100
    return polarToXY(i, val * R)
  })
  const polygonPoints = dataPoints.map(p => p.join(',')).join(' ')

  return (
    <div className="bg-gray-950 rounded-3xl p-6 border border-orange-500/20 shadow-2xl shadow-orange-500/10">
      <div className="flex items-center gap-2 mb-4">
        <Zap className="w-5 h-5 text-orange-400" />
        <span className="text-xs font-black uppercase tracking-widest text-orange-400">Score de Disruption</span>
      </div>
      <div className="flex flex-col md:flex-row items-center gap-6">
        <svg width="320" height="320" viewBox="0 0 320 320" className="flex-shrink-0">
          <defs>
            <radialGradient id="disruptGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#f97316" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#f97316" stopOpacity="0" />
            </radialGradient>
          </defs>
          {/* Grid circles */}
          {gridLevels.map((lvl, gi) => {
            const pts = axes.map((_, i) => polarToXY(i, lvl * R).join(',')).join(' ')
            return <polygon key={gi} points={pts} fill="none" stroke="#374151" strokeWidth="1" strokeDasharray="3,3" />
          })}
          {/* Axis lines */}
          {axes.map((_, i) => {
            const [x, y] = polarToXY(i, R)
            return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="#4b5563" strokeWidth="1" />
          })}
          {/* Data polygon */}
          <polygon points={polygonPoints} fill="url(#disruptGlow)" stroke="#f97316" strokeWidth="2" opacity="0.9" />
          {/* Data points */}
          {dataPoints.map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r="5" fill={axes[i].color} stroke="#111827" strokeWidth="2" />
          ))}
          {/* Labels */}
          {axes.map((a, i) => {
            const [x, y] = polarToXY(i, R + 22)
            return (
              <text key={i} x={x} y={y} textAnchor="middle" dominantBaseline="middle"
                fill={a.color} fontSize="11" fontWeight="700" fontFamily="system-ui">
                {a.label}
              </text>
            )
          })}
        </svg>
        {/* Score bars */}
        <div className="flex-1 space-y-3 w-full">
          {axes.map(a => (
            <div key={a.key}>
              <div className="flex justify-between mb-1">
                <span className="text-xs font-bold text-gray-300">{a.label}</span>
                <span className="text-xs font-black" style={{ color: a.color }}>{scores[a.key] || 0}/100</span>
              </div>
              <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${scores[a.key] || 0}%` }}
                  transition={{ duration: 0.8, delay: 0.2 }}
                  className="h-full rounded-full"
                  style={{ background: `linear-gradient(90deg, ${a.color}99, ${a.color})` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ==================== ROADMAP TIMELINE — 3D Vertical Interactive ====================
function RoadmapTimeline({ phases }) {
  const [expanded, setExpanded] = useState(null)
  const phaseColors = ['#f97316', '#a855f7', '#06b6d4', '#10b981']

  if (!phases || phases.length === 0) return null

  return (
    <div className="space-y-0">
      {phases.map((phase, idx) => {
        const color = phaseColors[idx % phaseColors.length]
        const isOpen = expanded === idx
        return (
          <div key={idx} className="relative flex gap-6">
            {/* Vertical line */}
            <div className="flex flex-col items-center">
              <motion.div
                whileHover={{ scale: 1.15 }}
                onClick={() => setExpanded(isOpen ? null : idx)}
                className="w-12 h-12 rounded-full flex items-center justify-center font-black text-sm cursor-pointer shadow-xl z-10 flex-shrink-0"
                style={{
                  background: `linear-gradient(135deg, ${color}33, ${color}11)`,
                  border: `2px solid ${color}`,
                  color: color,
                  boxShadow: `0 0 20px ${color}44`
                }}
              >
                {idx + 1}
              </motion.div>
              {idx < phases.length - 1 && (
                <div className="w-0.5 flex-1 min-h-[2rem]" style={{ background: `linear-gradient(180deg, ${color}66, ${phaseColors[(idx+1) % phaseColors.length]}66)` }} />
              )}
            </div>

            {/* Content card */}
            <motion.div
              className="flex-1 mb-8 rounded-3xl overflow-hidden border cursor-pointer"
              style={{ borderColor: `${color}33`, background: 'rgba(17,24,39,0.8)' }}
              onClick={() => setExpanded(isOpen ? null : idx)}
              whileHover={{ y: -2, boxShadow: `0 8px 40px ${color}22` }}
            >
              {/* Card header */}
              <div className="p-5 flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] font-black uppercase tracking-widest" style={{ color }}>{phase.phase}</span>
                    <span className="text-[10px] text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">{phase.duration}</span>
                  </div>
                  <h3 className="text-lg font-black text-white">{phase.title}</h3>
                  <p className="text-sm text-gray-400 mt-1">{phase.objective}</p>
                </div>
                <ChevronRight className={`w-5 h-5 flex-shrink-0 transition-transform mt-1 ${isOpen ? 'rotate-90' : ''}`} style={{ color }} />
              </div>

              {/* Expanded content */}
              <AnimatePresence>
                {isOpen && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.35 }}
                    className="overflow-hidden"
                  >
                    <div className="px-5 pb-5 grid grid-cols-1 md:grid-cols-2 gap-5">
                      {/* Image */}
                      {phase.image && (
                        <div className="rounded-2xl overflow-hidden" style={{ boxShadow: `0 4px 30px ${color}33` }}>
                          <img src={phase.image} alt={phase.title} className="w-full h-48 object-cover" />
                        </div>
                      )}
                      {/* Details */}
                      <div className="space-y-4">
                        {/* Milestones */}
                        <div>
                          <p className="text-[10px] font-black uppercase tracking-widest text-gray-500 mb-2">Milestones</p>
                          <div className="space-y-2">
                            {(phase.milestones || []).map((m, mi) => (
                              <div key={mi} className="flex items-start gap-2">
                                <div className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ background: color }} />
                                <span className="text-sm text-gray-300">{m}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                        {/* Visual style note */}
                        {phase.visual_style_integration && (
                          <div className="rounded-xl p-3" style={{ background: `${color}11`, border: `1px solid ${color}33` }}>
                            <p className="text-[10px] font-black uppercase tracking-widest mb-1" style={{ color }}>Design Directive</p>
                            <p className="text-xs text-gray-400">{phase.visual_style_integration}</p>
                          </div>
                        )}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          </div>
        )
      })}
    </div>
  )
}

// ==================== KILLER FEATURE CARD ====================
function KillerFeatureCard({ feature, index }) {
  const colors = ['#f97316', '#a855f7', '#06b6d4', '#10b981', '#f43f5e', '#eab308']
  const color = colors[index % colors.length]

  const iconMap = {
    shield: <Shield className="w-6 h-6" />,
    rocket: <Rocket className="w-6 h-6" />,
    zap: <Zap className="w-6 h-6" />,
    star: <Star className="w-6 h-6" />,
    target: <Target className="w-6 h-6" />,
    brain: <Brain className="w-6 h-6" />,
    eye: <Eye className="w-6 h-6" />,
    lock: <Shield className="w-6 h-6" />,
  }
  const icon = iconMap[feature.icon_type] || <Zap className="w-6 h-6" />

  return (
    <motion.div
      whileHover={{ y: -4, boxShadow: `0 12px 40px ${color}33` }}
      className="rounded-3xl p-6 border relative overflow-hidden"
      style={{ background: 'rgba(17,24,39,0.9)', borderColor: `${color}33` }}
    >
      {/* Glow bg */}
      <div className="absolute top-0 right-0 w-32 h-32 rounded-full blur-3xl opacity-20 pointer-events-none"
        style={{ background: color }} />
      {/* Icon */}
      <div className="w-12 h-12 rounded-2xl flex items-center justify-center mb-4 shadow-lg"
        style={{ background: `${color}22`, color }}>
        {icon}
      </div>
      <h4 className="font-black text-white text-lg mb-2">{feature.name}</h4>
      <p className="text-sm text-gray-400 mb-4 leading-relaxed">{feature.description}</p>
      <div className="rounded-xl p-3" style={{ background: `${color}11`, border: `1px solid ${color}33` }}>
        <p className="text-[10px] font-black uppercase tracking-widest mb-1" style={{ color }}>Avantage vs Concurrents</p>
        <p className="text-xs text-gray-400">{feature.competitor_gap}</p>
      </div>
    </motion.div>
  )
}

// ==================== COMPOSANT PRINCIPAL ====================

export default function AgentPage() {
  const params = useParams()
  const agentId = params?.id || params?.agentId
  const router = useRouter()

  // Lecture depuis le contexte global — l'analyse continue même pendant la navigation
  const { agentsResults, agentsStatus, projectDesc: ctxProjectDesc, isRunning } = useApp()

  // Données depuis le contexte global (pas de router state en Next.js)
  const liveResult = agentsResults?.[agentId]
  const result = liveResult
  const projectDesc = ctxProjectDesc
  const agentThoughts = result?.agent_thoughts || []
  const agentStatus = agentsStatus[agentId]?.status || 'idle'

  const [activeTab, setActiveTab] = useState(() => result?.activeTab || 'overview')

  const isVisionAgent = agentId === 'visual_semiotics'

  // Configuration des onglets selon l'agent
  const getTabs = () => {
    if (isVisionAgent) {
      return [
        { id: 'overview', label: 'Vue d\'ensemble', icon: BarChart3 },
        { id: 'visual_identity', label: '🎨 Identité Visuelle', icon: Palette },
        { id: 'strategy_analysis', label: '🖼️ Brand Moodboard', icon: Target },
      ]
    }

    if (agentId === 'emotional_intelligence') {
      return [
        { id: 'overview', label: 'Vue d\'ensemble', icon: BarChart3 },
        { id: 'deep_intelligence', label: '🧠 Deep Intelligence', icon: Brain },
      ]
    }

    if (agentId === 'creative_director') {
      return [
        { id: 'overview', label: 'Vue d\'ensemble', icon: BarChart3 },
        { id: 'execution', label: '🛠️ Plan d\'Exécution', icon: Rocket },
      ];
    }
    return [
      { id: 'overview', label: 'Vue d\'ensemble', icon: BarChart3 },
      { id: 'risks', label: 'Risques', icon: AlertTriangle },
      { id: 'strategy', label: 'Stratégie & Signaux', icon: Lightbulb },
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
  const visionImages = result?.images || {}
  const imageLabels = result?.image_labels || {}
  const companyName = result?.company_name || ''
  const brandPrimary = result?.brand_primary_color || (colorPalette?.primary?.hex || '#0D9488')
  const brandFont = result?.brand_font || 'Inter'

  // Données Trend (fallback)
  const analysis = result?.analysis || {}
  const weakSignals = result?.weak_signals || []
  const risks = analysis?.main_risks || []
  const recommendations = analysis?.recommendations || []
  const gapAnalysis = result?.gap_analysis || {}
  const preMortem = result?.pre_mortem || {}
  const trendImages = result?.images || {}

  // Données Emotion Agent
  const oceanProfile = result?.ocean_profile || {}
  const toneOfVoice = result?.tone_of_voice || {}
  const ethicalHook = result?.ethical_hook || {}
  const behavioralNudges = result?.behavioral_nudges || []
  const cognitiveLoad = result?.cognitive_load || {}
  const cognitiveStrategy = result?.cognitive_strategy || {}

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
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="text-center space-y-4">
          <div className="relative w-20 h-20 mx-auto">
            <div className="absolute inset-0 rounded-full border-4 border-purple-500/20" />
            <motion.div animate={{ rotate: 360 }} transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
              className="absolute inset-0 rounded-full border-4 border-purple-500 border-t-transparent" />
            <div className="absolute inset-0 flex items-center justify-center text-2xl">
              {config.icon && <config.icon className={`w-8 h-8 ${config.iconColor}`} />}
            </div>
          </div>
          <div>
            <p className="text-gray-700 dark:text-gray-300 font-semibold">Agent en cours d'analyse...</p>
            <p className="text-sm text-gray-400 mt-1">Les résultats apparaîtront dès que l'agent publie ses premières données</p>
          </div>
          <button onClick={() => router.push('/dashboard')}
            className="flex items-center gap-2 mx-auto text-sm text-gray-500 hover:text-purple-500 transition-colors">
            <ArrowLeft className="w-4 h-4" /> Retour au tableau de bord
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
          <button
            onClick={() => router.push('/dashboard')}
            className="flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="text-sm">Retour</span>
          </button>
          {/* Live status banner — analysis continues in background */}
          {isRunning && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800">
              <motion.div animate={{ scale: [1, 1.4, 1] }} transition={{ duration: 1, repeat: Infinity }}
                className="w-2 h-2 rounded-full bg-green-500" />
              <span className="text-xs font-semibold text-green-700 dark:text-green-400">
                Analyse en cours — les autres agents continuent en parallèle
              </span>
            </div>
          )}
          {/* Current agent live progress */}
          {agentStatus === 'running' && (
            <div className="flex items-center gap-2">
              <motion.div animate={{ rotate: 360 }} transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
                className="w-3.5 h-3.5 border-2 border-purple-500 border-t-transparent rounded-full" />
              <span className="text-xs text-purple-600 dark:text-purple-400 font-semibold">
                {agentsStatus[agentId]?.progress || 0}% — Cet agent travaille...
              </span>
            </div>
          )}
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
                    {agentId === 'creative_director' ? <Zap className="w-4 h-4 text-orange-500" /> : agentId === 'emotional_intelligence' ? <Brain className="w-4 h-4 text-emerald-500" /> : isVisionAgent ? <Palette className="w-4 h-4 text-purple-500" /> : <AlertTriangle className="w-4 h-4 text-red-500" />}
                    <span className="text-sm text-gray-500">
                      {agentId === 'creative_director' ? "Score Innovation" : agentId === 'emotional_intelligence' ? "Concurrents analysés" : isVisionAgent ? "Score de cohérence" : "Score de risque"}
                    </span>
                  </div>
                  <div className="text-2xl font-bold">
                    {agentId === 'creative_director' ? `${result?.disruption_scores?.innovation || 0}/100` : agentId === 'emotional_intelligence' ? (result?.sentiment_velocity?.length || 0) : isVisionAgent ? `${vibeCheck.aesthetic_score || 92}%` : `${analysis.risk_score || 7}/10`}
                  </div>
                </div>
                <div className="bg-white dark:bg-gray-900 rounded-xl p-5 border border-gray-200 dark:border-gray-800">
                  <div className="flex items-center gap-2 mb-2">
                    {agentId === 'creative_director' ? <Rocket className="w-4 h-4 text-orange-500" /> : agentId === 'emotional_intelligence' ? <MessageSquare className="w-4 h-4 text-emerald-500" /> : isVisionAgent ? <Sparkles className="w-4 h-4 text-purple-500" /> : <Zap className="w-4 h-4 text-yellow-500" />}
                    <span className="text-sm text-gray-500">
                      {agentId === 'creative_director' ? "Phases planifiées" : agentId === 'emotional_intelligence' ? "Frustrations identifiées" : isVisionAgent ? "Visuels générés" : "Signaux détectés"}
                    </span>
                  </div>
                  <div className="text-2xl font-bold">
                    {agentId === 'creative_director' ? (result?.roadmap_phases?.length || 0) : agentId === 'emotional_intelligence' ? (result?.sentiment_mining?.length || 0) : isVisionAgent ? `${Object.values(visionImages).filter(Boolean).length}/6` : weakSignals.length}
                  </div>
                </div>
                <div className="bg-white dark:bg-gray-900 rounded-xl p-5 border border-gray-200 dark:border-gray-800">
                  <div className="flex items-center gap-2 mb-2">
                    {agentId === 'creative_director' ? <Target className="w-4 h-4 text-orange-500" /> : agentId === 'emotional_intelligence' ? <MapIcon className="w-4 h-4 text-emerald-500" /> : isVisionAgent ? <Users className="w-4 h-4 text-purple-500" /> : <Lightbulb className="w-4 h-4 text-green-500" />}
                    <span className="text-sm text-gray-500">
                      {agentId === 'creative_director' ? "Killer Features" : agentId === 'emotional_intelligence' ? "Étapes du parcours" : isVisionAgent ? "Concurrents analysés" : "Recommandations"}
                    </span>
                  </div>
                  <div className="text-2xl font-bold">
                    {agentId === 'creative_director' ? (result?.killer_features?.length || 0) : agentId === 'emotional_intelligence' ? (result?.customer_journey?.length || 0) : isVisionAgent ? (result?.competitors_analyzed || competitors.length) : recommendations.length}
                  </div>
                </div>
              </div>

              {/* Terminal de raisonnement */}
              {agentThoughts && agentThoughts.length > 0 && (
                <div className="rounded-xl border border-gray-200 overflow-hidden">
                  <div className="bg-gray-800 px-4 py-2.5 flex items-center gap-3">
                    <div className="flex gap-1.5">
                      <div className="w-2.5 h-2.5 rounded-full bg-red-400" />
                      <div className="w-2.5 h-2.5 rounded-full bg-amber-400" />
                      <div className="w-2.5 h-2.5 rounded-full bg-green-400" />
                    </div>
                    <span className="text-xs text-gray-400 font-mono">trend_hunter.log — agent raisonnement</span>
                    <div className="ml-auto flex items-center gap-1.5">
                      <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                      <span className="text-[10px] text-gray-500 font-mono">{agentThoughts.length} lignes</span>
                    </div>
                  </div>
                  <div className="bg-gray-950 p-4 space-y-1 max-h-96 overflow-y-auto font-mono text-xs">
                    {agentThoughts.map((thought, idx) => {
                      const tag = thought.match(/^\[([A-Z_]+)\s*\]/)?.[1] || ''
                      const tagColors = {
                        'THINKING': 'text-cyan-400',
                        'SEARCH':   'text-yellow-400',
                        'READ':     'text-blue-400',
                        'GREP':     'text-blue-400',
                        'CHECK':    'text-violet-400',
                        'FILTER':   'text-violet-400',
                        'ANALYSIS': 'text-amber-400',
                        'SIGNALS':  'text-teal-400',
                        'OK':       'text-green-400',
                        'ERROR':    'text-red-400',
                        'SYNTHESIS':'text-emerald-400',
                      }
                      const tagColor = tagColors[tag] || 'text-gray-400'
                      const rest = thought.replace(/^\[[A-Z_\s]+\]\s*/, '')
                      return (
                        <motion.div key={idx}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ delay: idx * 0.02 }}
                          className="flex gap-2 leading-relaxed">
                          <span className="text-gray-600 select-none w-6 text-right flex-shrink-0">{idx + 1}</span>
                          <span className="text-gray-600">│</span>
                          {tag && (
                            <span className={`font-bold flex-shrink-0 ${tagColor}`}>
                              [{tag}]
                            </span>
                          )}
                          <span className="text-gray-300">{rest || thought}</span>
                        </motion.div>
                      )
                    })}
                    <div className="flex gap-2 leading-relaxed mt-1">
                      <span className="text-gray-600 select-none w-6 text-right">_</span>
                      <span className="text-gray-600">│</span>
                      <span className="text-green-400 animate-pulse">█</span>
                    </div>
                  </div>
                </div>
              )}

              {/* CognitivePathway — tunnel de friction zéro (emotion uniquement) */}
              {agentId === 'emotional_intelligence' && cognitiveLoad?.max_steps && (
                <CognitivePathway load={cognitiveLoad} />
              )}

              {/* Contexte du projet */}
              <div className="bg-white dark:bg-gray-900 rounded-xl p-5 border border-gray-200 dark:border-gray-800">
                <h3 className="font-semibold mb-3">Contexte du projet</h3>
                <p className="text-gray-600 dark:text-gray-400">{projectDesc}</p>
              </div>

              {/* Benchmark concurrents — affiché AVANT le modèle IA pour Vision */}
              {isVisionAgent && competitors.length > 0 && (
                <CompetitorAnalysisCard competitors={competitors} />
              )}

              {/* ── CREATIVE DIRECTOR : fusion Stratégie & Pivot dans la Vue d'ensemble ── */}
              {agentId === 'creative_director' && (
                <div className="space-y-6">

                  {/* Disruption Radar */}
                  <DisruptionRadarChart scores={result?.disruption_scores} />

                  {/* Alerte Radical Pivot */}
                  {result?.radical_pivot?.concept && (
                    <div className="rounded-3xl border-2 border-orange-400 bg-orange-50 dark:bg-orange-950/40 shadow-lg overflow-hidden">
                      <div className="bg-orange-500 px-6 py-3 flex items-center gap-2">
                        <span className="animate-pulse w-2 h-2 rounded-full bg-white inline-block" />
                        <span className="text-[11px] font-black uppercase tracking-widest text-white">Alerte de Marché — Radical Pivot Détecté</span>
                      </div>
                      <div className="p-8">
                        <h2 className="text-3xl font-black text-gray-900 dark:text-white mb-3 leading-tight">{result.radical_pivot.concept}</h2>
                        <p className="text-gray-600 dark:text-gray-300 text-lg italic leading-relaxed max-w-2xl">"{result.radical_pivot.why}"</p>
                        {result.radical_pivot.market_signal && (
                          <div className="mt-5 inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-orange-100 dark:bg-orange-500/20 border border-orange-300 dark:border-orange-500/40">
                            <TrendingUp className="w-4 h-4 text-orange-600 dark:text-orange-400" />
                            <span className="text-sm font-medium text-orange-700 dark:text-orange-300">{result.radical_pivot.market_signal}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Stress Test */}
                  {result?.stress_test?.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-4">
                        <ShieldAlert className="w-5 h-5 text-orange-400" />
                        <h3 className="text-sm font-black uppercase tracking-widest text-orange-400">Stress Test — Scénarios Critiques</h3>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {result.stress_test.map((s, i) => {
                          const resColor = s.resilience > 70 ? '#10b981' : s.resilience > 45 ? '#eab308' : '#ef4444'
                          return (
                            <motion.div key={i} whileHover={{ y: -4 }} className="rounded-2xl p-6 border"
                              style={{ background: 'rgba(17,24,39,0.9)', borderColor: `${resColor}33` }}>
                              <span className="text-[10px] font-black uppercase tracking-widest" style={{ color: resColor }}>{s.scenario}</span>
                              <div className="flex items-end gap-3 my-4">
                                <span className="text-4xl font-black text-white">{s.resilience}%</span>
                                <span className="text-xs text-gray-500 mb-1">résilience</span>
                              </div>
                              <div className="h-1.5 bg-gray-800 rounded-full mb-4 overflow-hidden">
                                <motion.div initial={{ width: 0 }} animate={{ width: `${s.resilience}%` }} transition={{ duration: 0.8 }}
                                  className="h-full rounded-full" style={{ background: `linear-gradient(90deg, ${resColor}99, ${resColor})` }} />
                              </div>
                              <p className="text-xs text-gray-400 leading-relaxed mb-3">{s.impact}</p>
                              <div className="rounded-lg p-2.5 text-xs text-gray-300" style={{ background: `${resColor}11`, border: `1px solid ${resColor}33` }}>
                                <span className="font-bold" style={{ color: resColor }}>Tactique :</span> {s.survival_tip}
                              </div>
                            </motion.div>
                          )
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}

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

              {/* Style visuel */}
              <StyleCard style={visualStyle} />

              {/* Concepts Graphiques — logos hybrides (icône FLUX.1 + texte HTML) */}
              <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-100 dark:border-gray-800 flex items-center gap-3">
                  <Sparkles className="w-5 h-5 text-purple-500" />
                  <h3 className="font-semibold">Concepts Graphiques</h3>
                  <span className="ml-auto text-xs text-gray-400 font-mono bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded-full">FLUX.1 × HTML · Logo Hybride</span>
                </div>
                <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-4">
                  <LogoHybride
                    iconSrc={visionImages.logo_a}
                    companyName={companyName}
                    label={imageLabels.logo_a || 'Piste A · Minimalisme'}
                    variant="light"
                    primaryColor={brandPrimary}
                    fontFamily={brandFont}
                  />
                  <LogoHybride
                    iconSrc={visionImages.logo_b}
                    companyName={companyName}
                    label={imageLabels.logo_b || 'Piste B · Modernité'}
                    variant="dark"
                    primaryColor={brandPrimary}
                    fontFamily={brandFont}
                  />
                  <LogoHybride
                    iconSrc={visionImages.logo_c}
                    companyName={companyName}
                    label={imageLabels.logo_c || 'Piste C · Premium'}
                    variant="badge"
                    primaryColor={brandPrimary}
                    fontFamily={brandFont}
                  />
                </div>
              </div>
            </motion.div>
          )}

          {/* ==================== VISION - BRAND MOODBOARD ==================== */}
          {isVisionAgent && activeTab === 'strategy_analysis' && (
            <motion.div
              key="strategy_analysis"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-6"
            >
              {/* Header moodboard */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold">Brand Moodboard</h3>
                  <p className="text-sm text-gray-500 mt-0.5">
                    Atmosphères visuelles générées selon l'archétype{semioticsAnalysis.recommended_archetype ? ` "${semioticsAnalysis.recommended_archetype}"` : ''} détecté
                  </p>
                </div>
                <span className="text-xs text-gray-400 font-mono bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded-full">FLUX.1 · IA</span>
              </div>

              {/* Grille asymétrique moodboard */}
              <div className="grid grid-cols-2 gap-4">
                {/* Image 1 — grande, colonne gauche */}
                <div className="row-span-2">
                  <VisionImageCard
                    src={visionImages.mood_1}
                    label={imageLabels.mood_1 || "Ambiance · Atmosphère"}
                    tall
                  />
                </div>
                {/* Images 2 et 3 — colonne droite */}
                <VisionImageCard
                  src={visionImages.mood_2}
                  label={imageLabels.mood_2 || "Univers · Mise en Situation"}
                />
                <VisionImageCard
                  src={visionImages.mood_3}
                  label={imageLabels.mood_3 || "Texture · Signal de Marque"}
                />
              </div>

              {/* Analyse sémiotique (contexte stratégique) */}
              {semioticsAnalysis.dominant_signifiers?.length > 0 && (
                <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <Hash className="w-5 h-5 text-purple-500" />
                    <h3 className="font-semibold">Positionnement Sémiotique</h3>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Signifiants concurrents</p>
                      <div className="flex flex-wrap gap-2">
                        {(semioticsAnalysis.dominant_signifiers || []).map((s, idx) => (
                          <span key={idx} className="px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded text-xs text-gray-600 dark:text-gray-400">{s}</span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Contre-signifiants (votre opportunité)</p>
                      <div className="flex flex-wrap gap-2">
                        {(semioticsAnalysis.counter_signifiers || []).map((s, idx) => (
                          <span key={idx} className="px-2 py-1 bg-purple-100 dark:bg-purple-950/30 text-purple-700 dark:text-purple-400 rounded text-xs">{s}</span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Archétype recommandé</p>
                      <p className="text-base font-semibold text-purple-600 dark:text-purple-400">
                        {semioticsAnalysis.recommended_archetype || "Non défini"}
                      </p>
                      {semioticsAnalysis.strategic_rationale && (
                        <p className="text-xs text-gray-500 mt-2">{semioticsAnalysis.strategic_rationale}</p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Vibe Check */}
              <VibeCheckCard vibe={vibeCheck} />
            </motion.div>
          )}


          {/* ==================== TREND - RISQUES ==================== */}
          {!isVisionAgent && activeTab === 'risks' && (
            <motion.div
              key="risks"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-4"
            >
              {risks.length > 0 && <RiskMatrixChart risks={risks} />}
              <AIImagePanel
                src={trendImages.risks}
                title="Infographie IA · Chaîne de Causalité des Risques"
                description="Visualisation générée dynamiquement par FLUX.1-schnell selon le contexte du projet"
              />
              <div className="space-y-3">
                {risks.map((risk, idx) => (
                  <RiskCard key={idx} risk={risk} index={idx} />
                ))}
              </div>
            </motion.div>
          )}

          {/* ==================== TREND - STRATÉGIE & SIGNAUX ==================== */}
          {!isVisionAgent && activeTab === 'strategy' && (
            <motion.div
              key="strategy"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-6"
            >
              {/* Roadmap Gantt */}
              {recommendations.length > 0 && (
                <StrategyRoadmap recommendations={recommendations} />
              )}
              <AIImagePanel
                src={trendImages.strategy}
                title="Infographie IA · Roadmap Stratégique 3D"
                description="Visualisation de la roadmap générée par FLUX.1-schnell — style cabinet de conseil"
              />
              {/* Recommendation cards */}
              <div className="space-y-3">
                {recommendations.map((rec, idx) => (
                  <RecommendationCard key={idx} recommendation={rec} index={idx} />
                ))}
              </div>
              {/* Signaux faibles fusionnés */}
              {weakSignals.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <Zap className="w-4 h-4 text-amber-500" />
                    <h3 className="font-semibold text-gray-900 text-sm">Signaux Faibles Détectés</h3>
                    <span className="text-[10px] text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">{weakSignals.length} signaux</span>
                  </div>
                  <div className="space-y-3">
                    {weakSignals.map((signal, idx) => (
                      <WeakSignalCard key={idx} signal={signal} index={idx} />
                    ))}
                  </div>
                </div>
              )}
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
              {/* Blue Ocean Canvas SVG */}
              {(gapAnalysis.canvas_factors || []).length > 0 && (
                <BlueOceanCanvas gapAnalysis={gapAnalysis} />
              )}
              {/* Blue Ocean zone */}
              {gapAnalysis.blue_ocean_opportunity && (
                <div className="bg-white border border-indigo-200 rounded-2xl p-5">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-7 h-7 rounded-lg bg-indigo-50 border border-indigo-200 flex items-center justify-center">
                      <Target className="w-3.5 h-3.5 text-indigo-600" />
                    </div>
                    <h3 className="font-semibold text-gray-900 text-sm">Zone Blue Ocean</h3>
                  </div>
                  <p className="text-gray-700 text-sm leading-relaxed">
                    {getText(gapAnalysis.blue_ocean_opportunity)}
                  </p>
                  {gapAnalysis.competitive_advantage && (
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <p className="text-[10px] text-gray-400 uppercase tracking-widest font-bold mb-1">Avantage concurrentiel recommandé</p>
                      <p className="text-sm text-indigo-700 font-medium">{getText(gapAnalysis.competitive_advantage)}</p>
                    </div>
                  )}
                </div>
              )}
              {/* Opportunity zones */}
              <div>
                <h3 className="font-semibold text-gray-900 text-sm mb-3 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                  Zones d'opportunité identifiées
                </h3>
                <div className="grid grid-cols-1 gap-2">
                  {(gapAnalysis.opportunity_zones || []).map((zone, idx) => (
                    <motion.div key={idx}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.06 }}
                      className="bg-white border border-gray-200 rounded-xl p-4 flex gap-3 items-start">
                      <div className="w-5 h-5 rounded-full bg-green-50 border border-green-200 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <span className="text-[9px] font-bold text-green-600">{idx + 1}</span>
                      </div>
                      <p className="text-sm text-gray-700 leading-relaxed">{getText(zone)}</p>
                    </motion.div>
                  ))}
                </div>
              </div>
              {/* Crowded zones */}
              <div>
                <h3 className="font-semibold text-gray-900 text-sm mb-3 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
                  Segments saturés à éviter
                </h3>
                <div className="flex flex-wrap gap-2">
                  {(gapAnalysis.crowded_zones || []).map((zone, idx) => (
                    <span key={idx} className="px-3 py-1.5 bg-white border border-red-200 text-red-600 rounded-lg text-xs font-medium">
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
              className="space-y-5"
            >
              {/* Cause principale */}
              <div className="bg-white border border-red-200 rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-7 h-7 rounded-lg bg-red-50 border border-red-200 flex items-center justify-center">
                    <Shield className="w-3.5 h-3.5 text-red-500" />
                  </div>
                  <h2 className="font-semibold text-gray-900 text-sm">Cause principale d'échec simulée</h2>
                </div>
                <p className="text-gray-800 text-sm leading-relaxed font-medium">
                  {getText(preMortem.primary_cause)}
                </p>
              </div>
              {/* Timeline */}
              <PreMortemTimeline timeline={preMortem.failure_timeline || []} />
              <AIImagePanel
                src={trendImages.premortem}
                title="Infographie IA · Trajectoire du Déclin"
                description="Timeline illustrée générée par FLUX.1-schnell — visualisation sobre du scénario d'échec"
              />
              {/* Causes secondaires + Comment éviter */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-white rounded-2xl border border-gray-200 p-5">
                  <h3 className="font-semibold text-gray-900 text-sm mb-3 flex items-center gap-2">
                    <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                    Causes secondaires
                  </h3>
                  <ul className="space-y-2">
                    {(preMortem.secondary_causes || []).map((cause, idx) => (
                      <li key={idx} className="text-sm text-gray-600 flex items-start gap-2">
                        <span className="text-red-300 mt-1 flex-shrink-0">—</span>
                        {getText(cause)}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="bg-white rounded-2xl border border-gray-200 p-5">
                  <h3 className="font-semibold text-gray-900 text-sm mb-3 flex items-center gap-2">
                    <Rocket className="w-3.5 h-3.5 text-green-500" />
                    Comment l'éviter
                  </h3>
                  <p className="text-sm text-gray-700 leading-relaxed">
                    {getText(preMortem.could_it_have_been_saved)}
                  </p>
                  {preMortem.lessons_learned && (
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <p className="text-[10px] text-gray-400 uppercase tracking-widest font-bold mb-1.5">Leçon principale</p>
                      <p className="text-sm text-indigo-700 italic leading-relaxed">{getText(preMortem.lessons_learned)}</p>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}

          {/* ==================== EMOTION - DEEP INTELLIGENCE (FUSIONNÉ) ==================== */}

          {agentId === 'emotional_intelligence' && activeTab === 'deep_intelligence' && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-8">

              {/* Sentiment Velocity */}
              <SentimentVelocityTable data={result?.sentiment_velocity || []} />

              {/* Social Sentiment Mining + Hall of Shame */}
              <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                <div className="lg:col-span-3">
                  <SentimentMining mining={result?.sentiment_mining || []} />
                </div>
                <div className="lg:col-span-2 rounded-2xl overflow-hidden border border-red-200 dark:border-red-900">
                  <div className="bg-gradient-to-r from-red-600 to-rose-600 px-4 py-3 flex items-center gap-2">
                    <Camera className="w-4 h-4 text-white" />
                    <h4 className="text-xs font-bold text-white uppercase">Hall of Shame — Captures Réelles</h4>
                  </div>
                  <div className="bg-white dark:bg-gray-900 p-4">
                    <div dangerouslySetInnerHTML={{ __html: result?.hall_of_shame_html }} />
                  </div>
                </div>
              </div>

              {/* Customer Journey Map */}
              <CustomerJourneyMap journey={result?.customer_journey || []} />

              {/* Cognitive Strategy */}
              <CognitiveStrategyBanner strategy={cognitiveStrategy} />

              {/* OCEAN Radar + Ethical Hook Infinity Loop côte à côte */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <OceanRadarChart profile={oceanProfile} />
                <EthicalHookInfinityLoop hook={ethicalHook} />
              </div>

            </motion.div>
          )}

          {agentId === 'creative_director' && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-8">

              {/* ── ONGLET 2 : PLAN D'EXÉCUTION ── */}
              {activeTab === 'execution' && (
                <div className="space-y-10">

                  {/* Roadmap Verticale */}
                  <div>
                    <div className="flex items-center gap-2 mb-6">
                      <Rocket className="w-5 h-5 text-orange-400" />
                      <h3 className="text-sm font-black uppercase tracking-widest text-orange-400">Roadmap d'Exécution — 4 Phases</h3>
                    </div>
                    <RoadmapTimeline phases={result?.roadmap_phases} />
                  </div>

                  {/* Killer Features */}
                  {result?.killer_features?.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-6">
                        <Zap className="w-5 h-5 text-orange-400" />
                        <h3 className="text-sm font-black uppercase tracking-widest text-orange-400">Killer Features — Avantages Compétitifs</h3>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                        {result.killer_features.map((f, i) => (
                          <KillerFeatureCard key={i} feature={f} index={i} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* MVP Blueprint */}
                  {result?.mvp_blueprint?.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-4">
                        <Target className="w-5 h-5 text-orange-400" />
                        <h3 className="text-sm font-black uppercase tracking-widest text-orange-400">MVP Blueprint</h3>
                      </div>
                      <div className="rounded-3xl border border-orange-500/20 overflow-hidden" style={{ background: 'rgba(17,24,39,0.9)' }}>
                        <table className="w-full">
                          <thead className="border-b border-gray-800 text-left">
                            <tr>
                              <th className="p-5 text-[10px] uppercase font-black text-gray-500">Feature Stratégique</th>
                              <th className="p-5 text-[10px] uppercase font-black text-gray-500">Counter-Attack</th>
                              <th className="p-5 text-[10px] uppercase font-black text-gray-500 text-right">Priorité</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-800">
                            {result.mvp_blueprint.map((f, i) => {
                              const priorityColor = f.priority === 'CRITICAL' ? '#ef4444' : f.priority === 'HIGH' ? '#f97316' : '#eab308'
                              return (
                                <tr key={i} className="hover:bg-white/5 transition-colors">
                                  <td className="p-5 font-bold text-white">{f.feature}</td>
                                  <td className="p-5 text-sm text-gray-400 italic">{f.counter_attack}</td>
                                  <td className="p-5 text-right">
                                    <span className="px-3 py-1 rounded-full text-[10px] font-black" style={{ background: `${priorityColor}22`, color: priorityColor, border: `1px solid ${priorityColor}44` }}>
                                      {f.priority}
                                    </span>
                                  </td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                        <div className="p-5 border-t border-gray-800 flex justify-center gap-6">
                          {result?.sources?.map(s => (
                            <span key={s} className="flex items-center gap-2 text-[10px] font-bold text-gray-600 uppercase tracking-widest">
                              <Database className="w-3 h-3" /> {s}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}