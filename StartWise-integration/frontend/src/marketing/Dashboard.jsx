'use client'
// src/pages/Dashboard.jsx — StartWise (Next.js compatible)
import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useRouter } from 'next/navigation'
import { useApp, TRANSLATIONS } from '../context/AppContext'
import GlobeNetwork from '../components/GlobeNetwork'
import { X, Download, ChevronLeft, ChevronRight, Target, Users, Zap, Radio, TrendingUp, DollarSign, Layers, Building2, ArrowRight, Printer } from 'lucide-react'

const AGENT_CONFIG = {
  trend_hunter:          { name: 'The Hunter',      emoji: '📡', color: '#3b82f6', role: 'Trend Agent',       model: 'Mistral Large', speed: '45-60s', skills: ['Web Research','FAISS Vector DB','Weak Signals','Risk Analysis','Pre-Mortem'] },
  visual_semiotics:      { name: 'The Artist',       emoji: '🎨', color: '#a855f7', role: 'Visual Agent',      model: 'Llama-3.1-70B', speed: '30-45s', skills: ['Semiotics','Color Psychology','Typography','Logo Gen','Moodboard'] },
  emotional_intelligence:{ name: 'The Psychologist', emoji: '🧠', color: '#10b981', role: 'Emotion Agent',     model: 'Llama-3.1-70B', speed: '15-25s', skills: ['OCEAN Profile','Sentiment Analysis','Journey Map','Behavioral Nudges','Cognitive Load'] },
  creative_director:     { name: 'The Architect',    emoji: '⚡', color: '#f97316', role: 'Creative Unit',     model: 'Llama-3.1-70B', speed: '60-90s', skills: ['Strategy Synthesis','Roadmap Gen','Disruption Score','Killer Features','FLUX.1 Images'] },
  commercial_agent:      { name: 'The Dealmaker',    emoji: '🤝', color: '#ec4899', role: 'Commercial Agent',  model: 'Llama-3.3-70B', speed: '30-50s', skills: ['Prospect Finding','Email Drafting','Facebook Posts','Instagram Posts','Hunter.io','Resend'] },
}

// ==================== TYPEWRITER INPUT ====================
function TypewriterInput({ value, onChange, disabled, t }) {
  const [placeholder, setPlaceholder] = useState('')
  const [suggIdx, setSuggIdx] = useState(0)
  const [charIdx, setCharIdx] = useState(0)
  const [deleting, setDeleting] = useState(false)
  const [paused, setPaused] = useState(false)
  const suggestions = t.suggestions || []

  useEffect(() => {
    if (value || disabled || suggestions.length === 0) return
    const current = suggestions[suggIdx % suggestions.length]
    const timeout = setTimeout(() => {
      if (paused) { setPaused(false); setDeleting(true); return }
      if (!deleting) {
        if (charIdx < current.length) {
          setPlaceholder(current.slice(0, charIdx + 1))
          setCharIdx(c => c + 1)
        } else {
          setPaused(true)
        }
      } else {
        if (charIdx > 0) {
          setPlaceholder(current.slice(0, charIdx - 1))
          setCharIdx(c => c - 1)
        } else {
          setDeleting(false)
          setSuggIdx(i => i + 1)
        }
      }
    }, paused ? 1800 : deleting ? 30 : 60)
    return () => clearTimeout(timeout)
  }, [charIdx, deleting, paused, suggIdx, value, disabled, suggestions])

  return (
    <textarea
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder || (t.placeholder)}
      className="w-full bg-transparent border-0 focus:ring-0 text-sm resize-none h-20 placeholder:text-gray-400 dark:placeholder:text-gray-500"
      disabled={disabled}
      dir={t === TRANSLATIONS.ar ? 'rtl' : 'ltr'}
    />
  )
}

// ==================== PROMPT SUGGESTIONS ====================
function PromptSuggestions({ onSelect, t }) {
  const suggestions = t.suggestions || []
  return (
    <div className="flex flex-wrap gap-2 mt-2">
      {suggestions.slice(0, 3).map((s, i) => (
        <motion.button
          key={i}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.1 }}
          whileHover={{ scale: 1.02 }}
          onClick={() => onSelect(s)}
          className="text-xs px-3 py-1.5 rounded-full border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:border-purple-400 hover:text-purple-600 dark:hover:text-purple-400 transition-all bg-white/60 dark:bg-gray-900/60 backdrop-blur-sm truncate max-w-[200px]"
        >
          {s.slice(0, 40)}{s.length > 40 ? '…' : ''}
        </motion.button>
      ))}
    </div>
  )
}

// ==================== LAUNCH ANIMATION OVERLAY ====================
function LaunchOverlay({ messages, t }) {
  const [msgIdx, setMsgIdx] = useState(0)
  useEffect(() => {
    const iv = setInterval(() => setMsgIdx(i => Math.min(i + 1, messages.length - 1)), 1200)
    return () => clearInterval(iv)
  }, [messages.length])
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-gray-950/90 backdrop-blur-xl">
      <div className="text-center space-y-6 px-8">
        <motion.div className="relative w-24 h-24 mx-auto">
          {[0,1,2].map(i => (
            <motion.div key={i} className="absolute inset-0 rounded-full border-2 border-purple-500/40"
              animate={{ scale: [1, 1.5 + i * 0.3, 1], opacity: [0.8, 0, 0.8] }}
              transition={{ duration: 2, repeat: Infinity, delay: i * 0.4 }} />
          ))}
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-4xl">🚀</span>
          </div>
        </motion.div>
        <AnimatePresence mode="wait">
          <motion.p key={msgIdx} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}
            className="text-white text-lg font-medium">
            {messages[msgIdx]}
          </motion.p>
        </AnimatePresence>
        <div className="flex justify-center gap-2">
          {messages.map((_, i) => (
            <div key={i} className={`w-2 h-2 rounded-full transition-colors duration-300 ${i <= msgIdx ? 'bg-purple-500' : 'bg-gray-700'}`} />
          ))}
        </div>
      </div>
    </motion.div>
  )
}

// ==================== AGENT CARD — SaaS Minimaliste ====================
function AgentCard({ agentId, status, progress, onClick, t }) {
  const cfg = AGENT_CONFIG[agentId]
  const [simulatedProgress, setSimulatedProgress] = useState(0)

  useEffect(() => {
    if (status !== 'running') { if (status === 'completed') setSimulatedProgress(100); return }
    setSimulatedProgress(prev => Math.max(prev, 5))
    const iv = setInterval(() => {
      setSimulatedProgress(prev => {
        if (prev >= 92) return prev
        return Math.min(prev + (prev < 30 ? 4 : prev < 60 ? 2 : 0.8), 92)
      })
    }, 600)
    return () => clearInterval(iv)
  }, [status])

  useEffect(() => { if (status === 'completed') setSimulatedProgress(100) }, [status])

  const pct = status === 'completed' ? 100 : simulatedProgress
  const isCompleted = status === 'completed'
  const isRunning   = status === 'running'

  return (
    <motion.button
      whileHover={{ y: -2, boxShadow: `0 8px 30px ${cfg.color}18` }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      className={`w-full text-left p-5 rounded-2xl border bg-white dark:bg-gray-900 transition-all shadow-sm
        ${isCompleted ? 'border-gray-200 dark:border-gray-700' : isRunning ? 'border-gray-200 dark:border-gray-700' : 'border-gray-100 dark:border-gray-800'}`}
    >
      {/* Top row */}
      <div className="flex items-center justify-between mb-4">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center text-lg"
          style={{ background: `${cfg.color}12` }}>
          {cfg.emoji}
        </div>
        {isCompleted ? (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800">
            <svg className="w-3 h-3 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">Prêt</span>
          </div>
        ) : isRunning ? (
          <div className="flex items-center gap-1.5">
            <motion.div animate={{ scale: [1, 1.3, 1] }} transition={{ duration: 1, repeat: Infinity }}
              className="w-1.5 h-1.5 rounded-full" style={{ background: cfg.color }} />
            <span className="text-[10px] font-semibold text-blue-500">{Math.round(pct)}%</span>
          </div>
        ) : (
          <span className="text-[10px] font-medium text-gray-300 dark:text-gray-600">—</span>
        )}
      </div>

      {/* Name + role */}
      <p className="font-semibold text-sm text-gray-900 dark:text-white leading-tight">{cfg.name}</p>
      <p className="text-xs text-gray-400 mt-0.5">{cfg.role}</p>

      {/* Progress bar */}
      <div className="mt-4 h-1 rounded-full overflow-hidden bg-gray-100 dark:bg-gray-800">
        <motion.div className="h-full rounded-full"
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          style={{ background: isCompleted
            ? `linear-gradient(90deg, #10b981, #059669)`
            : `linear-gradient(90deg, ${cfg.color}80, ${cfg.color})` }}
        />
      </div>
    </motion.button>
  )
}

// ==================== STAT CARD ====================
function StatCard({ label, value, unit, icon, color = '#a855f7' }) {
  const [displayed, setDisplayed] = useState(0)
  useEffect(() => {
    const target = Number(value) || 0
    if (target === displayed) return
    const step = target > displayed ? 1 : -1
    const iv = setInterval(() => {
      setDisplayed(prev => {
        if (prev === target) { clearInterval(iv); return prev }
        return prev + step
      })
    }, 30)
    return () => clearInterval(iv)
  }, [value])

  return (
    <div className="bg-white dark:bg-gray-900 rounded-2xl p-5 border border-gray-100 dark:border-gray-800 relative overflow-hidden">
      <div className="absolute top-0 right-0 w-20 h-20 rounded-full blur-2xl opacity-10 pointer-events-none" style={{ background: color }} />
      <div className="flex items-center gap-3 mb-2">
        <span className="text-2xl">{icon}</span>
        <span className="text-3xl font-black text-gray-900 dark:text-white">{displayed}{unit}</span>
      </div>
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  )
}

// ==================== ACTIVITY FEED ====================
function ActivityFeedPanel({ activities, t }) {
  const bottomRef = useRef(null)
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [activities.length])
  const agentColors = { trend_hunter: '#3b82f6', visual_semiotics: '#a855f7', emotional_intelligence: '#10b981', creative_director: '#f97316' }

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-y-auto space-y-2 p-4">
        <AnimatePresence>
          {activities.slice(-30).map((a, i) => (
            <motion.div key={`${a.id}-${i}`} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
              className="flex gap-2 items-start">
              <div className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0"
                style={{ background: agentColors[a.agent] || '#6b7280' }} />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-gray-700 dark:text-gray-300 leading-relaxed">{a.text}</p>
                <p className="text-[10px] text-gray-400 mt-0.5">{a.agent?.replace(/_/g, ' ').toUpperCase()}</p>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {activities.length === 0 && (
          <div className="flex flex-col items-center justify-center h-32 text-gray-400 text-xs text-center">
            <span className="text-2xl mb-2">💤</span>
            Aucune activité
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

// ==================== BUSINESS PLAN + PITCH DECK ====================

const DOC_I18N = {
  fr: {
    bmcTitle: 'Business Model Canvas', bmcSub: 'Généré depuis votre analyse StartWise',
    valueProp: 'Proposition de Valeur Unique', keyPartners: 'Partenaires Clés',
    customerSeg: 'Segments Clients', channels: 'Canaux de Distribution',
    keyActivities: 'Activités Clés', keyResources: 'Ressources Clés',
    costStructure: 'Structure de Coûts', revenueStreams: 'Flux de Revenus',
    exportPdf: 'Exporter PDF', close: 'Fermer',
    pitchTitle: 'Pitch Deck', pitchSub: 'Présentation investisseurs — 5 slides',
    slide1: 'Le Problème', slide2: 'Notre Solution', slide3: 'La Cible',
    slide4: 'Modèle Économique', slide5: 'Passons à l\'Action',
    prev: 'Précédent', next: 'Suivant',
    signalsLabel: 'signaux marché', innovLabel: 'score innovation',
    viabilityLabel: 'viabilité', journeyLabel: 'étapes parcours',
    topFeatureLabel: 'Avantage décisif', pivotLabel: 'Pivot stratégique',
    mvpLabel: 'Priorité MVP', firstStepLabel: 'Première action concrète',
    oceanTitle: 'Profil Psychologique (OCEAN)', triggerLabel: 'Mots déclencheurs',
    // buildBMC content
    specialistAgencies: (arch) => `Agences spécialisées ${arch}`,
    techPartners: 'Partenaires technologiques',
    visualIdentity: (arch) => `Identité visuelle **${arch}**`,
    messaging: (w) => `Messaging "${w}"`,
    organicContent: 'Contenu organique & SEO',
    community: 'Communauté & bouche-à-oreille',
    founderTeam: 'Équipe fondatrice pluridisciplinaire',
    brandIdentity: (arch) => `Identité de marque (${arch})`,
    techInfra: 'Infrastructure technique MVP',
    mvpDev: (n) => `Développement MVP (${n} features critiques)`,
    customerAcq: 'Acquisition clients (marketing)',
    cloudInfra: 'Infrastructure cloud & hosting',
    initialTeam: 'Équipe initiale (3–5 collaborateurs)',
    legalCosts: 'Coûts légaux & conformité',
    saasSubscription: 'Abonnement SaaS (mensuel/annuel)',
    premiumOffer: (name) => `Offre Premium — ${name}`,
    // buildPitchSlides headlines
    pitchH1: 'Un problème réel, non résolu',
    pitchH2: 'Une solution différenciante',
    pitchH3: 'Profil cible identifié',
    pitchH4: 'Un modèle économique viable',
    pitchH5: 'L\'opportunité est maintenant.',
    differentiating: 'différenciante',
    premiumSegment: 'segment haut de gamme',
  },
  en: {
    bmcTitle: 'Business Model Canvas', bmcSub: 'Generated from your StartWise analysis',
    valueProp: 'Unique Value Proposition', keyPartners: 'Key Partners',
    customerSeg: 'Customer Segments', channels: 'Distribution Channels',
    keyActivities: 'Key Activities', keyResources: 'Key Resources',
    costStructure: 'Cost Structure', revenueStreams: 'Revenue Streams',
    exportPdf: 'Export PDF', close: 'Close',
    pitchTitle: 'Pitch Deck', pitchSub: 'Investor presentation — 5 slides',
    slide1: 'The Problem', slide2: 'Our Solution', slide3: 'The Target',
    slide4: 'Business Model', slide5: 'Let\'s Build This',
    prev: 'Previous', next: 'Next',
    signalsLabel: 'market signals', innovLabel: 'innovation score',
    viabilityLabel: 'viability', journeyLabel: 'journey steps',
    topFeatureLabel: 'Key differentiator', pivotLabel: 'Strategic pivot',
    mvpLabel: 'MVP Priority', firstStepLabel: 'First concrete step',
    oceanTitle: 'Psychological Profile (OCEAN)', triggerLabel: 'Trigger words',
    specialistAgencies: (arch) => `${arch} specialist agencies`,
    techPartners: 'Technology partners',
    visualIdentity: (arch) => `**${arch}** visual identity`,
    messaging: (w) => `Messaging "${w}"`,
    organicContent: 'Organic content & SEO',
    community: 'Community & word-of-mouth',
    founderTeam: 'Multidisciplinary founding team',
    brandIdentity: (arch) => `Brand identity (${arch})`,
    techInfra: 'MVP technical infrastructure',
    mvpDev: (n) => `MVP development (${n} critical features)`,
    customerAcq: 'Customer acquisition (marketing)',
    cloudInfra: 'Cloud & hosting infrastructure',
    initialTeam: 'Initial team (3–5 members)',
    legalCosts: 'Legal & compliance costs',
    saasSubscription: 'SaaS subscription (monthly/annual)',
    premiumOffer: (name) => `Premium offer — ${name}`,
    pitchH1: 'A real, unsolved problem',
    pitchH2: 'A differentiating solution',
    pitchH3: 'Identified target profile',
    pitchH4: 'A viable business model',
    pitchH5: 'The opportunity is now.',
    differentiating: 'differentiating',
    premiumSegment: 'premium segment',
  },
  bm: {
    bmcTitle: 'Business Model Canvas', bmcSub: 'StartWise sèbèni kɔnɔ',
    valueProp: 'Dɔnni Kɛrɛnkɛrɛnnen', keyPartners: 'Baarakɛlaw Kɔrɔw',
    customerSeg: 'Jateminɛbaw', channels: 'Sira Jamanaw',
    keyActivities: 'Baaraw Gɛlɛnw', keyResources: 'Cogoyaw',
    costStructure: 'Sɔrɔminɛ', revenueStreams: 'Wari Sɔrɔ',
    exportPdf: 'PDF Bɔ', close: 'Dɔgɔ',
    pitchTitle: 'Pitch Deck', pitchSub: 'Jateminɛbaw — 5 ladon',
    slide1: 'Gɛlɛya', slide2: 'An ka Jaabi', slide3: 'Jateminɛba',
    slide4: 'Sɔrɔ Cogoya', slide5: 'A Daminɛ',
    prev: 'Kɔfɛ', next: 'Ntɛ',
    signalsLabel: 'marchɛ sinyaliw', innovLabel: 'hakɛ kura',
    viabilityLabel: 'kɛcogo', journeyLabel: 'sira daminɛ',
    topFeatureLabel: 'Fanga Kɛrɛnkɛrɛnnen', pivotLabel: 'Sira Kura',
    mvpLabel: 'MVP Fɔlɔ', firstStepLabel: 'Kɔlɔsili Fɔlɔ',
    oceanTitle: 'OCEAN Hakili', triggerLabel: 'Kuma kɔrɔfeliw',
    specialistAgencies: (arch) => `${arch} ka jɔyɔrɔ`,
    techPartners: 'Teknoloji baarakɛlaw',
    visualIdentity: (arch) => `**${arch}** jira`,
    messaging: (w) => `Kumakan "${w}"`,
    organicContent: 'SEO ni jiridenw',
    community: 'Jɛkulu ni kuma',
    founderTeam: 'Daminɛbaw ka sègè',
    brandIdentity: (arch) => `Marque jira (${arch})`,
    techInfra: 'MVP teknoloji sira',
    mvpDev: (n) => `MVP kɛ (${n} baara gɛlɛnw)`,
    customerAcq: 'Jateminɛbaw sɔrɔ',
    cloudInfra: 'Cloud ni hosting',
    initialTeam: 'Fɔlɔ sègè (3–5)',
    legalCosts: 'Sariya ni dɛmɛ',
    saasSubscription: 'SaaS sɔrɔ (kɔnkɔ/san)',
    premiumOffer: (name) => `Premium — ${name}`,
    pitchH1: 'Gɛlɛya kelen, a ma furakɛ',
    pitchH2: 'Jaabi kɛrɛnkɛrɛnnen',
    pitchH3: 'Jateminɛba sɔrɔlen',
    pitchH4: 'Wari cogoya ɲɛ',
    pitchH5: 'Waati ye sisan ye.',
    differentiating: 'kɛrɛnkɛrɛnnen',
    premiumSegment: 'gɛlɛn jateminɛbaw',
  },
  ar: {
    bmcTitle: 'نموذج العمل التجاري', bmcSub: 'مُولَّد من تحليل StartWise',
    valueProp: 'عرض القيمة الفريد', keyPartners: 'الشركاء الرئيسيون',
    customerSeg: 'شرائح العملاء', channels: 'قنوات التوزيع',
    keyActivities: 'الأنشطة الرئيسية', keyResources: 'الموارد الرئيسية',
    costStructure: 'هيكل التكاليف', revenueStreams: 'تدفقات الإيرادات',
    exportPdf: 'تصدير PDF', close: 'إغلاق',
    pitchTitle: 'عرض المستثمرين', pitchSub: '5 شرائح للمستثمرين',
    slide1: 'المشكلة', slide2: 'الحل', slide3: 'الجمهور المستهدف',
    slide4: 'نموذج الأعمال', slide5: 'ابدأ الآن',
    prev: 'السابق', next: 'التالي',
    signalsLabel: 'إشارات السوق', innovLabel: 'نقاط الابتكار',
    viabilityLabel: 'الجدوى', journeyLabel: 'خطوات الرحلة',
    topFeatureLabel: 'الميزة الحاسمة', pivotLabel: 'المحور الاستراتيجي',
    mvpLabel: 'أولوية MVP', firstStepLabel: 'الخطوة الأولى',
    oceanTitle: 'الملف النفسي (OCEAN)', triggerLabel: 'كلمات محفزة',
    specialistAgencies: (arch) => `وكالات متخصصة في ${arch}`,
    techPartners: 'شركاء تقنيون',
    visualIdentity: (arch) => `**${arch}** الهوية البصرية`,
    messaging: (w) => `رسالة تسويقية "${w}"`,
    organicContent: 'محتوى عضوي وتحسين SEO',
    community: 'مجتمع والتسويق الشفهي',
    founderTeam: 'فريق مؤسس متعدد التخصصات',
    brandIdentity: (arch) => `هوية العلامة التجارية (${arch})`,
    techInfra: 'بنية تقنية لـ MVP',
    mvpDev: (n) => `تطوير MVP (${n} ميزات حرجة)`,
    customerAcq: 'اكتساب العملاء (تسويق)',
    cloudInfra: 'بنية سحابية واستضافة',
    initialTeam: 'الفريق الأولي (3–5 أعضاء)',
    legalCosts: 'تكاليف قانونية وامتثال',
    saasSubscription: 'اشتراك SaaS (شهري/سنوي)',
    premiumOffer: (name) => `عرض مميز — ${name}`,
    pitchH1: 'مشكلة حقيقية غير محلولة',
    pitchH2: 'حل مميز ومختلف',
    pitchH3: 'الملف الشخصي المستهدف',
    pitchH4: 'نموذج أعمال قابل للتطبيق',
    pitchH5: 'الفرصة الآن.',
    differentiating: 'مميز',
    premiumSegment: 'الشريحة المميزة',
  },
}

function buildBMC(agentsResults, lang) {
  const trend = agentsResults.trend_hunter || {}
  const vision = agentsResults.visual_semiotics || {}
  const emotion = agentsResults.emotional_intelligence || {}
  const creative = agentsResults.creative_director || {}
  const l = DOC_I18N[lang] || DOC_I18N.fr

  const persona = emotion.cognitive_strategy?.target_persona || {}
  const topFeature = creative.killer_features?.[0]
  const features = creative.killer_features || []
  const mvp = creative.mvp_blueprint || []
  const signals = trend.weak_signals || []
  const archetype = vision.semiotics_analysis?.recommended_archetype || ''
  const pivot = creative.radical_pivot

  return {
    valueProp: [
      topFeature ? `**${topFeature.name}** — ${topFeature.description}` : null,
      pivot ? `${l.pivotLabel} : "${pivot.concept}"` : null,
      topFeature?.competitor_gap ? `${l.topFeatureLabel} : ${topFeature.competitor_gap}` : null,
    ].filter(Boolean),

    keyPartners: [
      ...(signals.slice(0, 3).map(s => (typeof s === 'string' ? s : s.signal || '').slice(0, 60)).filter(Boolean)),
      archetype ? l.specialistAgencies(archetype) : null,
      l.techPartners,
    ].filter(Boolean).slice(0, 5),

    customerSegments: [
      persona.name ? `**${persona.name}**` : null,
      persona.archetype || null,
      ...(persona.pain_points || []).slice(0, 2),
    ].filter(Boolean).slice(0, 5),

    channels: [
      archetype ? l.visualIdentity(archetype) : null,
      ...(persona.trigger_words || []).slice(0, 3).map(w => l.messaging(w)),
      l.organicContent,
      l.community,
    ].filter(Boolean).slice(0, 5),

    keyActivities: mvp.slice(0, 5).map(m => `${m.priority === 'CRITICAL' ? '🔴 ' : m.priority === 'HIGH' ? '🟠 ' : '🟡 '}${m.feature}`).filter(Boolean),

    keyResources: [
      l.founderTeam,
      l.brandIdentity(archetype || l.differentiating),
      l.techInfra,
      ...(features.slice(1, 3).map(f => f.name)),
    ].filter(Boolean).slice(0, 5),

    costStructure: [
      l.mvpDev(mvp.filter(m => m.priority === 'CRITICAL').length),
      l.customerAcq,
      l.cloudInfra,
      l.initialTeam,
      l.legalCosts,
    ],

    revenueStreams: [
      ...(features.slice(0, 3).map(f => f.name)),
      l.saasSubscription,
      l.premiumOffer(persona.name || l.premiumSegment),
    ].filter(Boolean).slice(0, 5),
  }
}

function buildPitchSlides(agentsResults, lang, projectDesc) {
  const trend = agentsResults.trend_hunter || {}
  const emotion = agentsResults.emotional_intelligence || {}
  const creative = agentsResults.creative_director || {}
  const vision = agentsResults.visual_semiotics || {}
  const l = DOC_I18N[lang] || DOC_I18N.fr

  const persona = emotion.cognitive_strategy?.target_persona || {}
  const topFeature = creative.killer_features?.[0]
  const oceanProfile = emotion.ocean_profile || {}
  const masterScore = Math.round(
    ((trend.score || 5) * 10 + (vision.vibe_check?.aesthetic_score || 70) +
     (creative.disruption_scores?.innovation || 60) + (100 - (creative.disruption_scores?.risque || 50))) / 4
  )
  const mvpCritical = (creative.mvp_blueprint || []).filter(m => m.priority === 'CRITICAL')
  const pivotConcept = creative.radical_pivot?.concept

  return [
    {
      id: 1, title: l.slide1,
      mesh: 'radial-gradient(ellipse at 20% 30%, rgba(239,68,68,0.35) 0%, transparent 60%), radial-gradient(ellipse at 80% 70%, rgba(124,45,18,0.4) 0%, transparent 60%), #030712',
      accent: '#ef4444',
      number: '01',
      headline: (emotion.sentiment_mining?.[0]?.topic || l.pitchH1),
      bullets: (emotion.sentiment_mining || []).slice(0, 3).map(s => s.verbatim || s.topic).filter(Boolean),
      stat: { value: trend.weak_signals?.length || 0, label: l.signalsLabel },
      footer: (emotion.sentiment_mining?.[0]?.opportunity || ''),
    },
    {
      id: 2, title: l.slide2,
      mesh: 'radial-gradient(ellipse at 70% 20%, rgba(168,85,247,0.4) 0%, transparent 60%), radial-gradient(ellipse at 20% 80%, rgba(99,102,241,0.3) 0%, transparent 55%), #030712',
      accent: '#a855f7',
      number: '02',
      headline: topFeature?.name || l.pitchH2,
      bullets: [
        topFeature?.description,
        topFeature?.competitor_gap ? `${l.topFeatureLabel} : ${topFeature.competitor_gap}` : null,
        pivotConcept ? `${l.pivotLabel} — "${pivotConcept}"` : null,
      ].filter(Boolean),
      stat: { value: creative.disruption_scores?.innovation || 0, label: l.innovLabel },
      footer: (creative.killer_features?.[1]?.name || ''),
    },
    {
      id: 3, title: l.slide3,
      mesh: 'radial-gradient(ellipse at 50% 10%, rgba(16,185,129,0.35) 0%, transparent 60%), radial-gradient(ellipse at 80% 80%, rgba(6,78,59,0.4) 0%, transparent 55%), #030712',
      accent: '#10b981',
      number: '03',
      headline: persona.name || l.pitchH3,
      bullets: (persona.pain_points || []).slice(0, 3),
      ocean: oceanProfile,
      triggerWords: (persona.trigger_words || []).slice(0, 5),
      stat: { value: emotion.customer_journey?.length || 0, label: l.journeyLabel },
      footer: persona.archetype || '',
    },
    {
      id: 4, title: l.slide4,
      mesh: 'radial-gradient(ellipse at 30% 70%, rgba(59,130,246,0.35) 0%, transparent 60%), radial-gradient(ellipse at 80% 20%, rgba(30,58,138,0.4) 0%, transparent 55%), #030712',
      accent: '#3b82f6',
      number: '04',
      headline: pivotConcept || l.pitchH4,
      bullets: (creative.killer_features || []).slice(0, 4).map(f => `${f.name} — ${f.description?.slice(0, 80)}`).filter(Boolean),
      stat: { value: Math.round((trend.score || 5) * 10), label: l.viabilityLabel },
      footer: (creative.mvp_blueprint || []).find(m => m.priority === 'CRITICAL')?.counter_attack || '',
    },
    {
      id: 5, title: l.slide5,
      mesh: 'radial-gradient(ellipse at 60% 30%, rgba(249,115,22,0.4) 0%, transparent 60%), radial-gradient(ellipse at 20% 80%, rgba(124,45,18,0.35) 0%, transparent 55%), #030712',
      accent: '#f97316',
      number: '05',
      headline: l.pitchH5,
      bullets: mvpCritical.slice(0, 3).map(m => `✦ ${m.feature}`),
      stat: { value: masterScore, label: l.viabilityLabel, big: true },
      footer: `${projectDesc?.slice(0, 80)}${projectDesc?.length > 80 ? '…' : ''}`,
    },
  ]
}

function printBMC(bmcData, projectDesc, lang) {
  const l = DOC_I18N[lang] || DOC_I18N.fr
  const renderSection = (title, items, icon) => `
    <div class="bmc-cell">
      <div class="cell-header"><span class="cell-icon">${icon}</span><span class="cell-title">${title}</span></div>
      <ul>${(items || []).map(i => `<li>${i.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')}</li>`).join('')}</ul>
    </div>`

  const html = `<!DOCTYPE html><html><head><meta charset="UTF-8">
  <title>${l.bmcTitle} — ${projectDesc?.slice(0,40)}</title>
  <style>
    * { margin:0; padding:0; box-sizing:border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:#fff; color:#0f172a; }
    .header { padding:32px 40px 20px; border-bottom:2px solid #f1f5f9; }
    .header h1 { font-size:28px; font-weight:900; color:#0f172a; letter-spacing:-0.5px; }
    .header p { font-size:14px; color:#64748b; margin-top:4px; }
    .project { display:inline-block; margin-top:8px; padding:4px 12px; background:#f8fafc; border-radius:20px; font-size:13px; color:#475569; border:1px solid #e2e8f0; }
    .grid { display:grid; grid-template-columns:1fr 2fr 1fr; grid-template-rows:auto auto auto; gap:1px; background:#e2e8f0; margin:24px 40px; border-radius:12px; overflow:hidden; }
    .bmc-cell { background:#fff; padding:20px; }
    .bmc-cell.vp { grid-column:2; grid-row:1/3; background:#fafafa; }
    .bmc-cell.wide { grid-column:1/4; }
    .cell-header { display:flex; align-items:center; gap:8px; margin-bottom:12px; }
    .cell-icon { font-size:16px; }
    .cell-title { font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:1.5px; color:#94a3b8; }
    .bmc-cell.vp .cell-title { color:#6366f1; }
    ul { list-style:none; padding:0; }
    li { font-size:13px; color:#334155; padding:4px 0; border-bottom:1px solid #f1f5f9; line-height:1.5; }
    li:last-child { border:none; }
    strong { color:#0f172a; font-weight:700; }
    .vp-headline { font-size:18px; font-weight:800; color:#0f172a; line-height:1.4; margin-bottom:16px; }
    .bottom-grid { display:grid; grid-template-columns:1fr 1fr; gap:1px; background:#e2e8f0; margin:0 40px 40px; border-radius:12px; overflow:hidden; }
    @media print { body { -webkit-print-color-adjust:exact; } }
  </style></head>
  <body>
  <div class="header">
    <h1>${l.bmcTitle}</h1>
    <p>${l.bmcSub}</p>
    <span class="project">📊 ${projectDesc?.slice(0,60)}</span>
  </div>
  <div class="grid">
    ${renderSection(l.keyPartners, bmcData.keyPartners, '🤝')}
    <div class="bmc-cell vp">
      <div class="cell-header"><span class="cell-icon">⚡</span><span class="cell-title" style="color:#6366f1">${l.valueProp}</span></div>
      ${bmcData.valueProp.map(v => `<p class="vp-headline">${v.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')}</p>`).join('')}
    </div>
    ${renderSection(l.customerSeg, bmcData.customerSegments, '👤')}
    ${renderSection(l.keyActivities, bmcData.keyActivities, '⚙️')}
    ${renderSection(l.channels, bmcData.channels, '📢')}
  </div>
  <div class="bottom-grid">
    ${renderSection(l.costStructure, bmcData.costStructure, '💰')}
    ${renderSection(l.revenueStreams, bmcData.revenueStreams, '📈')}
  </div>
  </body></html>`

  const win = window.open('', '_blank', 'width=1100,height=850')
  if (!win) return
  win.document.write(html)
  win.document.close()
  win.focus()
  setTimeout(() => { win.print() }, 600)
}

// ==================== BUSINESS PLAN MODAL ====================
function BusinessPlanModal({ open, onClose, agentsResults, lang, projectDesc }) {
  const l = DOC_I18N[lang] || DOC_I18N.fr
  const bmc = open ? buildBMC(agentsResults, lang) : null

  const BentoCell = ({ icon: Icon, title, items, accent = '#6366f1', large = false, className = '' }) => (
    <div className={`relative rounded-2xl border border-slate-800 bg-slate-900/80 p-5 flex flex-col overflow-hidden group transition-all hover:border-slate-600 ${className}`}>
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"
        style={{ background: `radial-gradient(ellipse at 50% 0%, ${accent}15, transparent 70%)` }}/>
      <div className="flex items-center gap-2 mb-4 relative">
        <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: `${accent}20`, border: `1px solid ${accent}40` }}>
          <Icon size={14} style={{ color: accent }} />
        </div>
        <p className="text-[10px] font-black uppercase tracking-[2px]" style={{ color: accent }}>{title}</p>
      </div>
      {large ? (
        <div className="space-y-3 relative flex-1">
          {(items || []).map((item, i) => (
            <p key={i} className="text-sm text-slate-200 leading-relaxed font-medium">
              <BoldText text={item} />
            </p>
          ))}
        </div>
      ) : (
        <ul className="space-y-2 relative flex-1">
          {(items || []).map((item, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-slate-300 leading-relaxed">
              <span className="w-1 h-1 rounded-full mt-2 flex-shrink-0" style={{ background: accent }}/>
              <BoldText text={item} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )

  return (
    <AnimatePresence>
      {open && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 bg-slate-950/95 backdrop-blur-2xl overflow-y-auto">
          {/* Header bar */}
          <div className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/90 backdrop-blur-xl px-8 py-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-900/50">
                <Layers size={18} className="text-white" />
              </div>
              <div>
                <h2 className="text-white font-black text-lg tracking-tight">{l.bmcTitle}</h2>
                <p className="text-slate-500 text-xs mt-0.5">{projectDesc?.slice(0, 60)}{projectDesc?.length > 60 ? '…' : ''}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                onClick={() => bmc && printBMC(bmc, projectDesc, lang)}
                className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold text-white transition-all border border-indigo-500/50 shadow-lg shadow-indigo-900/30"
                style={{ background: 'linear-gradient(135deg, #4f46e5, #7c3aed)' }}>
                <Printer size={15} />
                {l.exportPdf}
              </motion.button>
              <button onClick={onClose}
                className="w-9 h-9 rounded-xl border border-slate-700 bg-slate-800 flex items-center justify-center text-slate-400 hover:text-white hover:border-slate-500 transition-all">
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Bento Grid */}
          {bmc && (
            <div className="max-w-7xl mx-auto px-8 py-8 space-y-4">
              {/* Row 1: Value Prop (large) + Customer Segments */}
              <div className="grid grid-cols-5 gap-4" style={{ minHeight: 220 }}>
                <BentoCell icon={Target} title={l.valueProp} items={bmc.valueProp} accent="#6366f1" large className="col-span-3"/>
                <BentoCell icon={Users} title={l.customerSeg} items={bmc.customerSegments} accent="#ec4899" className="col-span-2"/>
              </div>

              {/* Row 2: Partners + Activities + Channels */}
              <div className="grid grid-cols-3 gap-4" style={{ minHeight: 180 }}>
                <BentoCell icon={Building2} title={l.keyPartners} items={bmc.keyPartners} accent="#3b82f6"/>
                <BentoCell icon={Zap} title={l.keyActivities} items={bmc.keyActivities} accent="#f97316"/>
                <BentoCell icon={Radio} title={l.channels} items={bmc.channels} accent="#a855f7"/>
              </div>

              {/* Row 3: Key Resources */}
              <div className="grid grid-cols-1 gap-4" style={{ minHeight: 100 }}>
                <BentoCell icon={Layers} title={l.keyResources} items={bmc.keyResources} accent="#06b6d4" className="grid grid-cols-2 md:grid-cols-4 gap-0"/>
              </div>

              {/* Row 4: Costs + Revenue — wider, more imposing */}
              <div className="grid grid-cols-2 gap-4" style={{ minHeight: 160 }}>
                <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 relative overflow-hidden group hover:border-slate-600 transition-all">
                  <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"
                    style={{ background: 'radial-gradient(ellipse at 0% 50%, #dc262615, transparent 70%)' }}/>
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: '#dc262620', border: '1px solid #dc262640' }}>
                      <DollarSign size={14} className="text-red-400" />
                    </div>
                    <p className="text-[10px] font-black uppercase tracking-[2px] text-red-400">{l.costStructure}</p>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {bmc.costStructure.map((c, i) => (
                      <div key={i} className="rounded-xl px-3 py-2 text-xs text-slate-300" style={{ background: '#dc262608', border: '1px solid #dc262620' }}>
                        <BoldText text={c}/>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 relative overflow-hidden group hover:border-slate-600 transition-all">
                  <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"
                    style={{ background: 'radial-gradient(ellipse at 100% 50%, #16a34a15, transparent 70%)' }}/>
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: '#16a34a20', border: '1px solid #16a34a40' }}>
                      <TrendingUp size={14} className="text-green-400" />
                    </div>
                    <p className="text-[10px] font-black uppercase tracking-[2px] text-green-400">{l.revenueStreams}</p>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {bmc.revenueStreams.map((r, i) => (
                      <div key={i} className="rounded-xl px-3 py-2 text-xs text-slate-300 flex items-center gap-2" style={{ background: '#16a34a08', border: '1px solid #16a34a20' }}>
                        <ArrowRight size={10} className="text-green-500 flex-shrink-0"/>
                        <BoldText text={r}/>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// ==================== PITCH DECK MODAL ====================
const OCEAN_LABELS = { openness: 'Ouverture', conscientiousness: 'Rigueur', extraversion: 'Extraversion', agreeableness: 'Bienveillance', neuroticism: 'Émotivité' }

function PitchDeckModal({ open, onClose, agentsResults, lang, projectDesc }) {
  const [current, setCurrent] = useState(0)
  const l = DOC_I18N[lang] || DOC_I18N.fr
  const slides = open ? buildPitchSlides(agentsResults, lang, projectDesc) : []
  const slide = slides[current]

  useEffect(() => { if (open) setCurrent(0) }, [open])

  const goNext = () => setCurrent(c => Math.min(c + 1, slides.length - 1))
  const goPrev = () => setCurrent(c => Math.max(c - 1, 0))

  useEffect(() => {
    const handler = (e) => {
      if (!open) return
      if (e.key === 'ArrowRight') goNext()
      if (e.key === 'ArrowLeft') goPrev()
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, current])

  return (
    <AnimatePresence>
      {open && slide && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex flex-col"
          style={{ background: '#030712' }}>

          {/* Close */}
          <div className="absolute top-5 right-5 z-10 flex items-center gap-3">
            <div className="text-xs font-bold text-slate-500 uppercase tracking-widest">
              {current + 1} / {slides.length}
            </div>
            <button onClick={onClose}
              className="w-9 h-9 rounded-xl border border-slate-700 bg-slate-900/80 flex items-center justify-center text-slate-400 hover:text-white transition-all">
              <X size={16} />
            </button>
          </div>

          {/* Slide progress bar */}
          <div className="absolute top-0 left-0 right-0 h-0.5 bg-slate-800 z-10">
            <motion.div className="h-full" style={{ background: slide.accent }}
              animate={{ width: `${((current + 1) / slides.length) * 100}%` }}
              transition={{ duration: 0.4 }}/>
          </div>

          {/* Slide content */}
          <AnimatePresence mode="wait">
            <motion.div key={current}
              initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -40 }}
              transition={{ duration: 0.3 }}
              className="flex-1 flex flex-col justify-between p-12 md:p-20 relative overflow-hidden"
              style={{ background: slide.mesh }}>

              {/* Grain texture overlay */}
              <div className="absolute inset-0 pointer-events-none opacity-[0.03]"
                style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 256 256\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'n\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.9\' numOctaves=\'4\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23n)\'/%3E%3C/svg%3E")', backgroundSize: '200px' }}/>

              {/* Slide number watermark */}
              <div className="absolute right-16 top-1/2 -translate-y-1/2 font-black text-[160px] leading-none pointer-events-none select-none"
                style={{ color: `${slide.accent}08`, fontVariantNumeric: 'tabular-nums' }}>
                {slide.number}
              </div>

              {/* Top section */}
              <div className="relative">
                <div className="flex items-center gap-3 mb-8">
                  <div className="h-0.5 w-12 rounded-full" style={{ background: slide.accent }}/>
                  <span className="text-xs font-black uppercase tracking-[3px]" style={{ color: slide.accent }}>{slide.title}</span>
                </div>
                <h1 className="text-4xl md:text-5xl font-black text-white leading-tight max-w-3xl mb-8 tracking-tight">
                  {slide.headline}
                </h1>
              </div>

              {/* Middle section — bullets or OCEAN */}
              <div className="relative flex-1 flex items-center">
                {slide.ocean && Object.keys(slide.ocean).length > 0 ? (
                  <div className="w-full space-y-5">
                    {/* OCEAN bars */}
                    <div className="grid grid-cols-5 gap-3 mb-6">
                      {Object.entries(slide.ocean).map(([trait, data]) => (
                        <div key={trait} className="flex flex-col items-center gap-2">
                          <div className="w-full h-24 rounded-xl relative overflow-hidden" style={{ background: `${slide.accent}15`, border: `1px solid ${slide.accent}25` }}>
                            <motion.div className="absolute bottom-0 left-0 right-0 rounded-b-xl"
                              initial={{ height: 0 }} animate={{ height: `${data?.score || 0}%` }}
                              transition={{ delay: 0.3, duration: 0.8 }}
                              style={{ background: `linear-gradient(to top, ${slide.accent}, ${slide.accent}44)` }}/>
                            <span className="absolute inset-0 flex items-center justify-center font-black text-sm" style={{ color: slide.accent }}>{data?.score || 0}</span>
                          </div>
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest text-center">{OCEAN_LABELS[trait] || trait}</span>
                        </div>
                      ))}
                    </div>
                    {slide.triggerWords?.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {slide.triggerWords.map((w, i) => (
                          <span key={i} className="px-3 py-1 rounded-full text-sm font-semibold"
                            style={{ background: `${slide.accent}20`, color: slide.accent, border: `1px solid ${slide.accent}40` }}>
                            {w}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <ul className="space-y-4 max-w-2xl">
                    {slide.bullets.map((b, i) => (
                      <motion.li key={i} initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 + i * 0.1 }}
                        className="flex items-start gap-4">
                        <div className="w-1.5 h-1.5 rounded-full mt-2.5 flex-shrink-0" style={{ background: slide.accent }}/>
                        <span className="text-lg md:text-xl text-slate-200 leading-relaxed font-light">{b}</span>
                      </motion.li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Bottom — stat + footer */}
              <div className="relative flex items-end justify-between mt-8">
                <div>
                  {slide.footer && <p className="text-sm text-slate-500 max-w-lg line-clamp-2">{slide.footer}</p>}
                </div>
                <div className="text-right">
                  <div className={`font-black text-white ${slide.stat.big ? 'text-7xl' : 'text-5xl'}`}
                    style={{ textShadow: `0 0 60px ${slide.accent}66` }}>
                    {slide.stat.value}
                    {slide.stat.big ? '' : <span className="text-2xl text-slate-400 font-light ml-1">/100</span>}
                  </div>
                  <p className="text-xs font-bold uppercase tracking-widest mt-1" style={{ color: slide.accent }}>{slide.stat.label}</p>
                </div>
              </div>
            </motion.div>
          </AnimatePresence>

          {/* Navigation */}
          <div className="flex items-center justify-between px-12 py-5 border-t border-slate-800/60 bg-slate-950/80">
            <motion.button onClick={goPrev} disabled={current === 0}
              whileHover={{ scale: current === 0 ? 1 : 1.05 }} whileTap={{ scale: 0.95 }}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-sm transition-all disabled:opacity-20 disabled:cursor-not-allowed border border-slate-700 text-slate-300 hover:text-white hover:border-slate-500">
              <ChevronLeft size={16}/>{l.prev}
            </motion.button>

            {/* Dot indicators */}
            <div className="flex items-center gap-2">
              {slides.map((s, i) => (
                <button key={i} onClick={() => setCurrent(i)}
                  className="transition-all rounded-full"
                  style={{ width: i === current ? 24 : 8, height: 8, background: i === current ? slide.accent : '#334155' }}/>
              ))}
            </div>

            <motion.button onClick={goNext} disabled={current === slides.length - 1}
              whileHover={{ scale: current === slides.length - 1 ? 1 : 1.05 }} whileTap={{ scale: 0.95 }}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-sm transition-all disabled:opacity-20 disabled:cursor-not-allowed text-white"
              style={{ background: current === slides.length - 1 ? '#334155' : `linear-gradient(135deg, ${slide.accent}cc, ${slide.accent})`, border: `1px solid ${slide.accent}44` }}>
              {l.next}<ChevronRight size={16}/>
            </motion.button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// ==================== EXECUTIVE AI SYNTHESIS ====================
// Renders **bold** markdown syntax as bold spans
function BoldText({ text, className = '' }) {
  if (!text) return null
  const parts = text.split(/\*\*(.*?)\*\*/g)
  return (
    <span className={className}>
      {parts.map((part, i) =>
        i % 2 === 1
          ? <strong key={i} className="text-gray-900 dark:text-white font-bold">{part}</strong>
          : part
      )}
    </span>
  )
}

const NARRATIVE_I18N = {
  fr: {
    oceanMap: { openness: "ouverture à l'innovation", conscientiousness: 'recherche de rigueur et de structure', extraversion: 'expériences sociales et de visibilité', agreeableness: 'confiance et empathie', neuroticism: 'réassurance et de clarté' },
    verdictStrong: (n) => `Les **${n} signaux de marché** captés convergent vers une **demande solidement établie** : le timing est optimal. Le marché ne se cherche plus, il appelle des solutions capables de s'imposer rapidement.`,
    verdictMed: (n) => `Avec **${n} signaux de marché détectés**, le secteur entre dans une **phase d'émergence accélérée** — la fenêtre stratégique est ouverte, mais elle ne le restera pas longtemps. Entrer maintenant signifie définir les règles du jeu avant les suiveurs.`,
    verdictLow: () => `Le volume de signaux indique un **marché de niche à fort potentiel pionnier**. Peu de concurrents structurés, une demande latente non satisfaite : c'est précisément ce type de terrain qui produit les **entreprises catégorie-reine**.`,
    verdictConfirm: (s) => ` La solidité du concept est confirmée par un **niveau de viabilité de ${s}/100** — un seuil qui témoigne d'une opportunité réelle, pas d'une intuition.`,
    verdictRisk: (r) => ` Le principal défi à anticiper est **${r}**, un risque identifiable et actionnable dès la phase MVP.`,
    identity: (arch, persona, ocean, triggers, aes) => `L'archétype **${arch}** recommandé par l'agent visuel n'est pas un simple choix esthétique — c'est une réponse directe au profil psychologique de **${persona}**, dont le trait dominant est une forte **${ocean}**. Un design cohérent avec cet archétype active immédiatement les bons leviers de confiance et de désir${triggers.length > 0 ? `, en jouant sur des mots-déclencheurs comme **"${triggers.join('", "')}"**` : ''}. Avec un score d'intégrité visuelle de **${aes}%**, l'identité est prête à convertir, pas seulement à séduire.`,
    leverFeature: (n, d, g) => `Parmi toutes les opportunités identifiées, **${n}** se distingue comme le **levier de différenciation décisif** : ${d}. Là où les solutions actuelles ${g}, ce concept comble un vide stratégique réel.`,
    leverPivot: (c) => ` Le **pivot radical** recommandé — "${c}" — amplifie cet avantage en repositionnant l'offre sur un terrain où aucun concurrent n'est encore positionné.`,
    leverInnovation: () => ` Avec un potentiel d'innovation dans le **top 30% du secteur**, ce n'est pas une amélioration incrémentale : c'est une rupture.`,
    leverFallback: (p) => `L'analyse créative révèle un **espace de différenciation majeur** non exploité par les acteurs existants. ${p ? `Le pivot stratégique — **"${p}"** — offre un positionnement singulier, difficile à répliquer rapidement par la concurrence.` : "Le plan d'exécution en 4 phases dessine une trajectoire de croissance crédible et progressive."}`,
    action: (s) => `La convergence des quatre analyses constitue une **preuve de viabilité à ${s}/100** — suffisamment robuste pour initier les premières actions concrètes sans sur-investir.`,
    actionMvp: (f) => ` La priorité absolue est de **${f}** : c'est la fondation sur laquelle repose l'ensemble de la proposition de valeur. Sans elle, le reste reste théorique.`,
    actionClose: () => ` L'enjeu n'est pas de tout construire d'un coup, mais de **valider le cœur du concept en 30 jours** et de laisser les données du marché guider la suite.`,
    sections: ["Le Verdict de l'Opportunité", "L'Identité Gagnante", "Le Levier de Croissance", "Action Immédiate & Viabilité"],
  },
  en: {
    oceanMap: { openness: 'openness to innovation', conscientiousness: 'rigor and structure', extraversion: 'social experiences and visibility', agreeableness: 'trust and empathy', neuroticism: 'reassurance and clarity' },
    verdictStrong: (n) => `The **${n} market signals** captured converge on a **solidly established demand**: the timing is optimal. The market is no longer searching — it's calling for solutions that can establish themselves quickly.`,
    verdictMed: (n) => `With **${n} market signals detected**, the sector is entering an **accelerated emergence phase** — the strategic window is open, but it won't stay that way long. Entering now means setting the rules before the followers do.`,
    verdictLow: () => `The signal volume indicates a **niche market with strong pioneer potential**. Few structured competitors, unsatisfied latent demand: this is precisely the terrain that produces **category-defining companies**.`,
    verdictConfirm: (s) => ` The concept's strength is confirmed by a **viability score of ${s}/100** — a threshold that reflects a real opportunity, not merely an intuition.`,
    verdictRisk: (r) => ` The main challenge to anticipate is **${r}**, an identifiable and actionable risk from the MVP phase.`,
    identity: (arch, persona, ocean, triggers, aes) => `The **${arch}** archetype recommended by the visual agent is not merely an aesthetic choice — it's a direct response to the psychological profile of **${persona}**, whose dominant trait is **${ocean}**. A design consistent with this archetype immediately activates the right trust and desire levers${triggers.length > 0 ? `, leveraging trigger words like **"${triggers.join('", "')}"**` : ''}. With a visual integrity score of **${aes}%**, the identity is ready to convert, not just to seduce.`,
    leverFeature: (n, d, g) => `Among all identified opportunities, **${n}** stands out as the **decisive differentiation lever**: ${d}. Where current solutions **${g}**, this concept fills a real strategic gap.`,
    leverPivot: (c) => ` The recommended **radical pivot** — "${c}" — amplifies this advantage by repositioning the offer on terrain where no competitor is yet positioned.`,
    leverInnovation: () => ` With innovation potential in the **top 30% of the sector**, this is not an incremental improvement: it's a disruption.`,
    leverFallback: (p) => `The creative analysis reveals a **major differentiation space** unexploited by existing players. ${p ? `The strategic pivot — **"${p}"** — offers a singular positioning, difficult for competitors to replicate quickly.` : 'The 4-phase execution plan outlines a credible and progressive growth trajectory.'}`,
    action: (s) => `The convergence of all four analyses constitutes a **viability proof of ${s}/100** — robust enough to initiate concrete first actions without over-investing.`,
    actionMvp: (f) => ` The absolute priority is to **${f}**: this is the foundation on which the entire value proposition rests. Without it, everything else remains theoretical.`,
    actionClose: () => ` The challenge is not to build everything at once, but to **validate the core concept in 30 days** and let market data guide the rest.`,
    sections: ["The Opportunity Verdict", "The Winning Identity", "The Growth Lever", "Immediate Action & Viability"],
  },
  bm: {
    oceanMap: { openness: 'yɛlɛma ɲini', conscientiousness: 'tɔgɔ kɛ ka ɲi', extraversion: 'jama fɛ kɛ', agreeableness: 'dɛmɛ ni diya', neuroticism: 'lafiɲɛ ɲini' },
    verdictStrong: (n) => `**${n} marchɛ sinyaliw** jɔra: **ɲɛ-ɲɛ fanga** bɛ yen. Waati ka ɲi.`,
    verdictMed: (n) => `**${n} sinyaliw** sɔrɔlen: marchɛ **bɛ daminɛ** — sira bɛ yɛlɛ sisan.`,
    verdictLow: () => `Sinyaliw ka hakɛ b'a jira ko **nisɔndiya baaraw bɛ yen** minnu tɛ sɔrɔ. Olu ye **yɔrɔ sira**.`,
    verdictConfirm: (s) => ` Hakɛ **${s}/100** b'a jira ko a ka bon.`,
    verdictRisk: (r) => ` Gɛlɛya fɔlɔ ye **${r}**.`,
    identity: (arch, persona, ocean, triggers, aes) => `**${arch}** ye jaabi dɔ **${persona}** ma, min bɛ ɲini **${ocean}**${triggers.length > 0 ? `, ani kuma **"${triggers.join('", "')}"**` : ''}. Yɛlɛma ye **${aes}%**.`,
    leverFeature: (n, d, g) => `**${n}** ye baara faran: ${d}. Cogoyaw bɛ **${g}**, nka nin be don yɔrɔ min tɛ sɔrɔ.`,
    leverPivot: (c) => ` **"${c}"** be yɛlɛma kɛ.`,
    leverInnovation: () => ` **Top 30%** kɔnɔ.`,
    leverFallback: (p) => `Yɔrɔ dɔ sɔrɔlen minnu tɛ kɛ. ${p ? `**"${p}"** ka ɲi.` : 'Jɛkulu 4-fasɛ ka ɲi.'}`,
    action: (s) => `**${s}/100** ye sɔrɔ. Baara daminɛ.`,
    actionMvp: (f) => ` **${f}** ye fɔlɔ baara.`,
    actionClose: () => ` **Si tile 30** kɔnɔ kɛ.`,
    sections: ["Sɔrɔ Sɛbɛni", "Tɔgɔ Gɛlɛn", "Kolosi Fanga", "Baara Siran ni Dɛsɛ"],
  },
  ar: {
    oceanMap: { openness: 'الانفتاح على الابتكار', conscientiousness: 'الدقة والانضباط', extraversion: 'التجارب الاجتماعية والظهور', agreeableness: 'الثقة والتعاطف', neuroticism: 'الطمأنينة والوضوح' },
    verdictStrong: (n) => `تتقاطع **${n} إشارة سوقية** نحو **طلب راسخ**: التوقيت مثالي. السوق لا يبحث بعد الآن — بل يدعو الحلول التي تفرض نفسها.`,
    verdictMed: (n) => `مع **${n} إشارة سوقية**، القطاع يدخل **مرحلة نمو متسارع** — النافذة الاستراتيجية مفتوحة، لكنها لن تبقى كذلك طويلاً.`,
    verdictLow: () => `حجم الإشارات يشير إلى **سوق متخصص ذي إمكانيات رائدة**. قلة المنافسين وطلب كامن غير مُلبَّى: هذه الأرضية التي تُنتج **شركات تحدد الفئة**.`,
    verdictConfirm: (s) => ` متانة المشروع تتجلى في **درجة جدوى ${s}/100**.`,
    verdictRisk: (r) => ` التحدي الأبرز هو **${r}**، خطر قابل للتصرف منذ مرحلة MVP.`,
    identity: (arch, persona, ocean, triggers, aes) => `نموذج **${arch}** ليس مجرد خيار جمالي — إنه استجابة مباشرة للملف النفسي لـ **${persona}**، الذي يتميز بـ **${ocean}**${triggers.length > 0 ? `، مع تفعيل كلمات محفِّزة مثل **"${triggers.join('", "')}"**` : ''}. بدرجة نزاهة بصرية **${aes}%**، الهوية جاهزة للتحويل.`,
    leverFeature: (n, d, g) => `من بين جميع الفرص، تبرز **${n}** كـ **رافعة تمييز حاسمة**: ${d}. حيث تفشل الحلول الحالية في **${g}**، يسد هذا المشروع الفراغ الاستراتيجي.`,
    leverPivot: (c) => ` **التحول الجذري** — "${c}" — يضاعف هذه الميزة.`,
    leverInnovation: () => ` إمكانية ابتكارية ضمن **أفضل 30% في القطاع**.`,
    leverFallback: (p) => `يكشف التحليل عن **مساحة تمييز كبرى** غير مستغلة. ${p ? `التحول — **"${p}"** — يوفر تموضعاً فريداً.` : 'خطة التنفيذ من 4 مراحل ترسم مسار نمو موثوق.'}`,
    action: (s) => `تقاطع التحليلات الأربعة يمثل **دليل جدوى بـ ${s}/100** — متين بما يكفي لبدء الإجراءات الأولى.`,
    actionMvp: (f) => ` الأولوية القصوى هي **${f}**: هذا هو الأساس الذي تقوم عليه القيمة المقدمة.`,
    actionClose: () => ` التحدي هو **التحقق من جوهر المشروع في 30 يوماً** وترك بيانات السوق توجه الباقي.`,
    sections: ["حكم الفرصة", "الهوية الرابحة", "رافعة النمو", "العمل الفوري والجدوى"],
  },
}

function buildNarrativeSynthesis(trend, vision, emotion, creative, masterScore, lang = 'fr') {
  const T = NARRATIVE_I18N[lang] || NARRATIVE_I18N.fr
  const signalCount = trend.weak_signals?.length || 0
  const marketScore = Math.round((trend.score || 5) * 10)
  const archetype = vision.semiotics_analysis?.recommended_archetype || 'différenciant'
  const aestheticScore = vision.vibe_check?.aesthetic_score || 75
  const persona = emotion.cognitive_strategy?.target_persona
  const personaName = persona?.name || 'cible'
  const triggerWords = persona?.trigger_words?.slice(0, 3) || []

  const oceanProfile = emotion.ocean_profile || {}
  const topOcean = Object.entries(oceanProfile).sort((a, b) => (b[1]?.score || 0) - (a[1]?.score || 0))[0]
  const topOceanLabel = topOcean ? (T.oceanMap[topOcean[0]] || topOcean[0]) : 'engagement'

  const topFeature = creative.killer_features?.[0]
  const pivotConcept = creative.radical_pivot?.concept || null
  const firstMvp = creative.mvp_blueprint?.find(f => f.priority === 'CRITICAL') || creative.mvp_blueprint?.[0]
  const innovationScore = creative.disruption_scores?.innovation || 0

  // Section 1
  let verdict = signalCount >= 8 ? T.verdictStrong(signalCount) : signalCount >= 4 ? T.verdictMed(signalCount) : T.verdictLow()
  if (marketScore >= 70) verdict += T.verdictConfirm(masterScore)
  else if (trend.analysis?.main_risks?.[0]?.risk) verdict += T.verdictRisk(trend.analysis.main_risks[0].risk)

  // Section 2
  const identity = T.identity(archetype, personaName, topOceanLabel, triggerWords, aestheticScore)

  // Section 3
  let lever = ''
  if (topFeature) {
    lever = T.leverFeature(topFeature.name, topFeature.description, topFeature.competitor_gap)
    if (pivotConcept) lever += T.leverPivot(pivotConcept)
    if (innovationScore >= 70) lever += T.leverInnovation()
  } else {
    lever = T.leverFallback(pivotConcept)
  }

  // Section 4
  let action = T.action(masterScore)
  if (firstMvp) action += T.actionMvp(firstMvp.feature)
  action += T.actionClose()

  return { verdict, identity, lever, action, sections: T.sections }
}

function ExecutiveSynthesis({ agentsResults, agentsStatus, t, lang, isDarkMode, onOpenBPlan, onOpenPitch }) {
  const completed = Object.values(agentsStatus).filter(a => a?.status === 'completed').length
  const allDone = completed === 5
  const trend = agentsResults.trend_hunter || {}
  const emotion = agentsResults.emotional_intelligence || {}
  const creative = agentsResults.creative_director || {}
  const vision = agentsResults.visual_semiotics || {}

  const masterScore = allDone ? Math.round(
    ((trend.score || 5) * 10 + (vision.vibe_check?.aesthetic_score || 70) + (creative.disruption_scores?.innovation || 60) + (100 - (creative.disruption_scores?.risque || 50))) / 4
  ) : null

  const narrative = allDone ? buildNarrativeSynthesis(trend, vision, emotion, creative, masterScore, lang || 'fr') : null

  const sections = narrative ? [
    { icon: '📡', title: narrative.sections[0], color: '#3b82f6', text: narrative.verdict },
    { icon: '🎨', title: narrative.sections[1], color: '#ec4899', text: narrative.identity },
    { icon: '⚡', title: narrative.sections[2], color: '#f97316', text: narrative.lever },
    { icon: '🚀', title: narrative.sections[3], color: '#a855f7', text: narrative.action },
  ] : []

  return (
    <div id="reach-investors" className="bg-white dark:bg-gray-900 rounded-3xl border border-gray-100 dark:border-gray-800 overflow-hidden scroll-mt-24">
      {/* Header */}
      <div className="p-6 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
        <div>
          <h3 className="font-black text-lg text-gray-900 dark:text-white">{t.synthTitle}</h3>
          <p className="text-sm text-gray-500 mt-0.5">{allDone ? t.synthReady : t.synthWaiting}</p>
        </div>
        {allDone && masterScore !== null && (
          <div className="text-center">
            <motion.div animate={{ scale: [1, 1.05, 1] }} transition={{ duration: 2, repeat: Infinity }}
              className="text-3xl font-black text-purple-500">{masterScore}</motion.div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">{t.masterScore}</p>
          </div>
        )}
      </div>

      {/* Agent progress */}
      <div className="px-6 pt-5">
        <div className="flex items-center gap-3 mb-5">
          {['trend_hunter','visual_semiotics','emotional_intelligence','creative_director'].map((id) => {
            const cfg = AGENT_CONFIG[id]
            const done = agentsStatus[id]?.status === 'completed'
            return (
              <div key={id} className="flex flex-col items-center gap-1 flex-1">
                <motion.div
                  animate={done ? { boxShadow: [`0 0 0px ${cfg.color}`, `0 0 16px ${cfg.color}88`, `0 0 6px ${cfg.color}55`] } : {}}
                  transition={{ duration: 1.2, repeat: done ? Infinity : 0 }}
                  className="w-10 h-10 rounded-full flex items-center justify-center text-lg border-2 transition-all"
                  style={{ borderColor: done ? cfg.color : '#374151', background: done ? `${cfg.color}22` : 'transparent' }}>
                  {done ? cfg.emoji : <span className="text-xs text-gray-500">{cfg.emoji}</span>}
                </motion.div>
                <div className="h-1 w-full rounded-full" style={{ background: done ? cfg.color : (isDarkMode ? '#1f2937' : '#e5e7eb') }}/>
              </div>
            )
          })}
          <div className="flex-1">
            <div className="h-2 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
              <motion.div className="h-full rounded-full" style={{ background: 'linear-gradient(90deg, #3b82f6, #ec4899, #f97316, #a855f7)' }}
                animate={{ width: `${completed * 25}%` }} transition={{ duration: 0.6 }} />
            </div>
            <p className="text-xs text-gray-400 mt-1 text-right">{completed}/5</p>
          </div>
        </div>

        {/* Narrative sections */}
        <AnimatePresence>
          {narrative && (
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
              className="space-y-5 pb-5">
              {sections.map((sec, i) => (
                <motion.div key={sec.title} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.12 }}
                  className="rounded-2xl p-4 border"
                  style={{ borderColor: `${sec.color}22`, background: `${sec.color}08` }}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-base">{sec.icon}</span>
                    <p className="text-xs font-black uppercase tracking-widest" style={{ color: sec.color }}>{sec.title}</p>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
                    <BoldText text={sec.text} />
                  </p>
                </motion.div>
              ))}

              {/* Next steps */}
              <div className="grid grid-cols-3 gap-3 pt-1">
                {[
                  { label: t.nextStep1, icon: '📋', color: '#6366f1', action: onOpenBPlan },
                  { label: t.nextStep2, icon: '🎯', color: '#a855f7', action: onOpenPitch },
                  { label: t.nextStep3, icon: '🤝', color: '#10b981', action: null },
                ].map((step, i) => (
                  <motion.button key={i}
                    whileHover={{ y: -3, scale: 1.02, boxShadow: `0 12px 32px ${step.color}33` }}
                    whileTap={{ scale: 0.97 }}
                    onClick={step.action || undefined}
                    className="p-4 rounded-2xl text-sm font-bold text-center transition-all border relative overflow-hidden group"
                    style={{ borderColor: `${step.color}55`, background: `${step.color}10`, color: step.color }}>
                    <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity"
                      style={{ background: `radial-gradient(ellipse at 50% 0%, ${step.color}20, transparent 70%)` }}/>
                    <span className="block text-2xl mb-2 relative">{step.icon}</span>
                    <span className="relative text-xs font-black uppercase tracking-wide">{step.label}</span>
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Waiting state */}
        {!allDone && (
          <div className="pb-6 space-y-2">
            {[...Array(4)].map((_, i) => (
              <motion.div key={i} animate={{ opacity: [0.3, 0.6, 0.3] }} transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.2 }}
                className="h-4 rounded-full bg-gray-100 dark:bg-gray-800"
                style={{ width: `${85 - i * 10}%` }}/>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ==================== ARCHIVE HOLOGRAPHIQUE ====================
function ArchiveView({ history, agentsResults, agentsStatus, t, onReload }) {
  const hasData = history.length > 0

  // Deduplicate by id — archive shows saved analyses only (no live "current" item)
  const allItems = history.filter((item, idx, arr) => arr.findIndex(h => h.id === item.id) === idx)

  // SVG Crystal component
  function Crystal({ score, risk, size = 80 }) {
    const hue = risk > 6 ? (risk > 8 ? 0 : 30) : 160
    const color = `hsl(${hue}, 95%, 58%)`
    const glow = `hsl(${hue}, 95%, 78%)`
    const uid = `c${hue}s${size}`
    return (
      <svg width={size} height={size} viewBox="0 0 100 100">
        <defs>
          <radialGradient id={`cg${uid}`} cx="40%" cy="30%">
            <stop offset="0%" stopColor="white" stopOpacity="0.9"/>
            <stop offset="40%" stopColor={glow} stopOpacity="1"/>
            <stop offset="100%" stopColor={color} stopOpacity="0.7"/>
          </radialGradient>
          <filter id={`glow${uid}`} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="7" result="blur1"/>
            <feGaussianBlur stdDeviation="3" in="SourceGraphic" result="blur2"/>
            <feMerge>
              <feMergeNode in="blur1"/>
              <feMergeNode in="blur2"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>
        {/* Ambient base glow */}
        <ellipse cx="50" cy="72" rx="26" ry="7" fill={color} opacity="0.35"/>
        <circle cx="50" cy="42" r="35" fill={color} opacity="0.08"/>
        <motion.g filter={`url(#glow${uid})`}
          animate={{ rotateY: [0, 360] }} transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}>
          <polygon points="50,5 83,32 73,78 27,78 17,32" fill={`url(#cg${uid})`} stroke={glow} strokeWidth="2.5" opacity="1"/>
          <polygon points="50,5 83,32 50,48" fill={glow} opacity="0.7"/>
          <polygon points="50,5 17,32 50,48" fill={color} opacity="0.65"/>
          <polygon points="50,48 27,78 73,78" fill={color} opacity="0.5"/>
          <line x1="50" y1="5" x2="50" y2="78" stroke={glow} strokeWidth="1.5" opacity="0.95"/>
          <line x1="17" y1="32" x2="83" y2="32" stroke={glow} strokeWidth="1.5" opacity="0.8"/>
          {/* Highlight sparkle */}
          <circle cx="50" cy="18" r="3" fill="white" opacity="0.9"/>
          <circle cx="65" cy="28" r="1.5" fill="white" opacity="0.6"/>
        </motion.g>
      </svg>
    )
  }

  return (
    <div className="p-8 space-y-6">
      <div>
        <h2 className="text-2xl font-black text-gray-900 dark:text-white">{t.archiveTitle}</h2>
        <p className="text-sm text-gray-500 mt-1">{t.archiveSub}</p>
      </div>

      {/* Starfield background */}
      <div className="relative">
        <div className="absolute inset-0 overflow-hidden rounded-3xl pointer-events-none">
          {[...Array(40)].map((_, i) => (
            <motion.div key={i} className="absolute w-0.5 h-0.5 rounded-full bg-gray-400 dark:bg-white"
              style={{ left: `${Math.random()*100}%`, top: `${Math.random()*100}%`, opacity: Math.random()*0.6+0.1 }}
              animate={{ opacity: [0.1, 0.8, 0.1] }}
              transition={{ duration: 2+Math.random()*3, repeat: Infinity, delay: Math.random()*2 }} />
          ))}
        </div>

        {!hasData ? (
          <div className="h-64 flex items-center justify-center rounded-3xl border border-dashed border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-950/50">
            <div className="text-center">
              <span className="text-5xl mb-4 block">🔮</span>
              <p className="text-gray-400 text-sm">{t.noArchive}</p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {allItems.map((item, idx) => (
              <motion.div key={`${item.id}-${idx}`}
                initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: idx * 0.1 }}
                whileHover={{ y: -5 }}
                className="group relative rounded-2xl overflow-hidden cursor-pointer bg-white dark:bg-gray-900/80 border border-gray-200 dark:border-white/10 backdrop-blur-md">
                <div className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <Crystal score={item.confidence || 0} risk={item.riskScore || 0} size={70} />
                    <div className="text-right">
                      <p className="text-xs text-gray-500">{new Date(item.date).toLocaleDateString()}</p>
                      <p className="text-2xl font-black text-gray-900 dark:text-white mt-1">{item.confidence || 0}<span className="text-sm text-gray-400">%</span></p>
                      <p className="text-[10px] uppercase tracking-widest text-purple-500 dark:text-purple-400">{t.confidence}</p>
                    </div>
                  </div>
                  <p className="text-sm font-semibold text-gray-900 dark:text-white line-clamp-2 mb-2">{item.project}</p>
                  {(item.archetype || item.persona) && (
                    <div className="flex flex-wrap gap-1 mb-3">
                      {item.archetype && <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 border border-purple-300 dark:border-purple-800">{item.archetype}</span>}
                      {item.persona && <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 border border-blue-300 dark:border-blue-800">{item.persona}</span>}
                    </div>
                  )}

                  {/* Stats */}
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { label: t.riskScore, value: item.riskScore || 0, color: '#ef4444' },
                      { label: t.signals, value: item.signals || 0, color: '#3b82f6' },
                      { label: 'Innov.', value: item.innovation || 0, color: '#f97316' },
                    ].map((stat, i) => (
                      <div key={i} className="rounded-lg p-2 text-center" style={{ background: `${stat.color}11` }}>
                        <p className="text-sm font-bold" style={{ color: stat.color }}>{stat.value}</p>
                        <p className="text-[10px] text-gray-500">{stat.label}</p>
                      </div>
                    ))}
                  </div>
                  {item.results && Object.keys(item.results).length > 0 ? (
                    <motion.button onClick={() => onReload(item)}
                      whileHover={{ scale: 1.02 }}
                      className="mt-4 w-full py-2 rounded-xl text-xs font-bold text-white opacity-0 group-hover:opacity-100 transition-opacity"
                      style={{ background: 'linear-gradient(90deg, #6366f1, #a855f7)' }}>
                      {t.reloadAnalysis}
                    </motion.button>
                  ) : (
                    <div className="mt-4 w-full py-2 rounded-xl text-xs font-bold text-center text-gray-500 border border-dashed border-gray-300 dark:border-gray-700">
                      Données non disponibles — relancez
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ==================== AGENT TEAM — La Ruche ====================
function AgentTeamView({ t }) {
  const [selected, setSelected] = useState(null)
  const agents = Object.entries(AGENT_CONFIG)

  // SVG hologram per agent
  function AgentHologram({ id, color, emoji, selected }) {
    return (
      <svg width="120" height="120" viewBox="0 0 120 120" className="mx-auto">
        <defs>
          <radialGradient id={`hg${id}`} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={color} stopOpacity="0.75"/>
            <stop offset="60%" stopColor={color} stopOpacity="0.25"/>
            <stop offset="100%" stopColor={color} stopOpacity="0"/>
          </radialGradient>
          <filter id={`hglow${id}`} x="-35%" y="-35%" width="170%" height="170%">
            <feGaussianBlur stdDeviation="6" result="b1"/>
            <feGaussianBlur stdDeviation="2" in="SourceGraphic" result="b2"/>
            <feMerge>
              <feMergeNode in="b1"/>
              <feMergeNode in="b1"/>
              <feMergeNode in="b2"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>
        {/* Ambient outer glow */}
        <circle cx="60" cy="60" r="54" fill={color} opacity="0.1"/>
        <motion.g filter={`url(#hglow${id})`}
          animate={{ y: selected ? [-4, 4, -4] : [-2, 2, -2], opacity: [0.9, 1, 0.9] }}
          transition={{ duration: 2.5, repeat: Infinity }}>
          <circle cx="60" cy="60" r="48" fill={`url(#hg${id})`} stroke={color} strokeWidth="2.5" strokeDasharray="5,3"/>
          {/* Inner rings */}
          {[36,26,16].map((r, i) => (
            <circle key={i} cx="60" cy="60" r={r} fill="none" stroke={color} strokeWidth={1.2 - i * 0.3} opacity={0.75 - i * 0.15}/>
          ))}
          {/* Cross lines */}
          <line x1="14" y1="60" x2="106" y2="60" stroke={color} strokeWidth="0.6" opacity="0.35" strokeDasharray="4,8"/>
          <line x1="60" y1="14" x2="60" y2="106" stroke={color} strokeWidth="0.6" opacity="0.35" strokeDasharray="4,8"/>
          {/* Corner dots */}
          {[[60,16],[104,60],[60,104],[16,60]].map(([cx,cy],i) => (
            <circle key={i} cx={cx} cy={cy} r="2.5" fill={color} opacity="0.8"/>
          ))}
          <text x="60" y="68" textAnchor="middle" fontSize="28" dominantBaseline="middle">{emoji}</text>
          {/* Scan line — motion.g wrapper because Framer Motion can't animate SVG attrs y1/y2 */}
          <motion.g animate={{ y: [-42, 42, -42] }} transition={{ duration: 3, repeat: Infinity }}>
            <line x1="14" y1="60" x2="106" y2="60" stroke={color} strokeWidth="2" opacity="0.9"/>
          </motion.g>
        </motion.g>
      </svg>
    )
  }

  return (
    <div className="p-8 space-y-6">
      <div>
        <h2 className="text-2xl font-black text-gray-900 dark:text-white">{t.teamTitle}</h2>
        <p className="text-sm text-gray-500 mt-1">{t.teamSub}</p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
        {agents.map(([id, cfg]) => (
          <motion.div key={id}
            whileHover={{ scale: 1.04 }}
            onClick={() => setSelected(selected === id ? null : id)}
            className="rounded-3xl p-5 cursor-pointer border-2 transition-all"
            style={{ borderColor: selected === id ? cfg.color : `${cfg.color}33`, background: selected === id ? `${cfg.color}11` : 'rgba(17,24,39,0.6)', backdropFilter: 'blur(8px)' }}>
            <AgentHologram id={id} color={cfg.color} emoji={cfg.emoji} selected={selected === id} />
            <div className="text-center mt-3">
              <p className="font-black text-white text-sm">{cfg.name}</p>
              <p className="text-[11px] text-gray-400 mt-0.5">{cfg.role}</p>
            </div>
          </motion.div>
        ))}
      </div>
      <AnimatePresence>
        {selected && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 20 }}
            className="rounded-3xl p-6 border"
            style={{ borderColor: `${AGENT_CONFIG[selected].color}44`, background: `${AGENT_CONFIG[selected].color}08` }}>
            <div className="flex items-center gap-4 mb-4">
              <span className="text-4xl">{AGENT_CONFIG[selected].emoji}</span>
              <div>
                <h3 className="font-black text-xl text-white">{AGENT_CONFIG[selected].name}</h3>
                <p className="text-sm text-gray-400">{AGENT_CONFIG[selected].role}</p>
              </div>
              <div className="ml-auto text-right">
                <p className="text-xs text-gray-500">{t.model}</p>
                <p className="text-sm font-bold text-white">{AGENT_CONFIG[selected].model}</p>
                <p className="text-xs text-gray-500 mt-1">{t.speed}</p>
                <p className="text-sm font-bold" style={{ color: AGENT_CONFIG[selected].color }}>{AGENT_CONFIG[selected].speed}</p>
              </div>
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-gray-500 mb-3">{t.skills}</p>
              <div className="flex flex-wrap gap-2">
                {AGENT_CONFIG[selected].skills.map((skill, i) => (
                  <motion.span key={skill} initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.06 }}
                    className="px-3 py-1.5 rounded-full text-xs font-semibold"
                    style={{ background: `${AGENT_CONFIG[selected].color}22`, color: AGENT_CONFIG[selected].color, border: `1px solid ${AGENT_CONFIG[selected].color}44` }}>
                    {skill}
                  </motion.span>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ==================== BRAIN MAP — Documentation ====================
const NODES_I18N = {
  fr: {
    center: 'Plateforme multi-agent d\'intelligence stratégique. 5 agents IA orchestrés par LangGraph : Trend + Vision + Emotion → Creative → Commercial. Backend Django + Channels, frontend React + Framer Motion. Stack : Python 3.11, Django 5, React 18, Tailwind CSS, WebSocket temps réel.',
    trend: 'Agent de veille marché en temps réel. Scrape DuckDuckGo (15–20 sources). Calcule un score de marché (0–10). Détecte les signaux faibles. Utilise Groq 70B → ESPRIT en secours. Génère une analyse de risques + pre-mortem + gap analysis concurrentielle.',
    vision: 'Agent de sémiotique visuelle et branding. Analyse l\'archétype visuel du secteur (Glassmorphism, Brutalism…). Génère : palettes hex, paires typographiques, icône SVG, moodboard 4 visuels. Modèle : Groq 8B → ESPRIT. Images : HuggingFace FLUX.1 → Pollinations.',
    emotion: 'Agent de psychologie comportementale. Construit un profil OCEAN (Big Five). Produit : Customer Journey Map, Sentiment Velocity, Hall of Shame, nudges comportementaux, Tone of Voice. Modèle : Groq 8B → ESPRIT.',
    creative: 'Agent de synthèse stratégique finale. Produit : Disruption Scores (5 axes), Roadmap 4 phases + images FLUX.1, Killer Features, Radical Pivot, Stress Test, MVP Blueprint. Modèle : Groq 70B → ESPRIT.',
    langgraph: 'Framework d\'orchestration multi-agent. StateGraph avec TypedDict partagé. Les agents Trend + Vision + Emotion s\'exécutent en parallèle via asyncio.gather, puis Creative synthétise. compiled_graph.astream() stream les événements vers le WebSocket.',
    ws: 'Django Channels (ASGI) — AsyncWebsocketConsumer. Envoie les résultats agent par agent dès qu\'ils terminent. Adaptive split : images base64 > 800KB envoyées séparément. Frontend : WebSocket singleton global dans AppContext, ne se ferme jamais entre navigations.',
    ocean: 'Modèle psychologique Big Five (Costa & McCrae, 1992). Cinq traits de 0 à 100 : Ouverture, Conscienciosité, Extraversion, Agréabilité, Névrotisme. Utilisé pour cibler les messages marketing et la tonalité de marque.',
    flux: 'Modèle text-to-image de Black Forest Labs. Architecture Diffusion Transformer. Accessible via HuggingFace InferenceClient (40s timeout) → Pollinations.ai fallback. Génère des rendus 3D photoréalistes pour roadmap et moodboard.',
    faiss: 'Facebook AI Similarity Search — recherche vectorielle haute performance. Utilisé par le Trend Hunter pour indexer les documents web scrappés. Embeddings HuggingFace all-MiniLM-L6-v2. Permet un RAG local sans base de données externe.',
  },
  en: {
    center: 'Multi-agent strategic intelligence platform. 4 AI agents orchestrated by LangGraph in parallel: Trend + Vision + Emotion → Creative. Backend Django + Channels, frontend React + Framer Motion. Stack: Python 3.11, Django 4.2, React 18, Tailwind CSS, real-time WebSocket.',
    trend: 'Real-time market intelligence agent. Scrapes DuckDuckGo (15–20 sources). Computes a market score (0–10). Detects weak signals. Uses Groq 70B → ESPRIT fallback. Generates risk analysis + pre-mortem + competitive gap analysis.',
    vision: 'Visual semiotics & branding agent. Analyzes dominant visual archetype (Glassmorphism, Brutalism…). Generates: hex palettes, typography pairs, SVG icon, 4-visual moodboard. Model: Groq 8B → ESPRIT. Images: HuggingFace FLUX.1 → Pollinations.',
    emotion: 'Behavioral psychology agent. Builds OCEAN (Big Five) profile. Produces: Customer Journey Map, Sentiment Velocity, Hall of Shame, behavioral nudges, Tone of Voice. Model: Groq 8B → ESPRIT.',
    creative: 'Final strategic synthesis agent. Produces: Disruption Scores (5 axes), 4-phase Roadmap + FLUX.1 images, Killer Features, Radical Pivot, Stress Test, MVP Blueprint. Model: Groq 70B → ESPRIT.',
    langgraph: 'Multi-agent orchestration framework. StateGraph with shared TypedDict. Trend + Vision + Emotion run in parallel via asyncio.gather, then Creative synthesizes. compiled_graph.astream() streams events to the WebSocket.',
    ws: 'Django Channels (ASGI) — AsyncWebsocketConsumer. Sends results agent by agent as they finish. Adaptive split: base64 images > 800KB sent separately. Frontend: global singleton WebSocket in AppContext, never closes between navigations.',
    ocean: 'Big Five psychological model (Costa & McCrae, 1992). Five traits from 0 to 100: Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism. Used to target marketing messages and brand tone.',
    flux: 'Black Forest Labs text-to-image model. Diffusion Transformer architecture. Accessible via HuggingFace InferenceClient (40s timeout) → Pollinations.ai fallback. Generates photorealistic 3D renders for roadmap and moodboard.',
    faiss: 'Facebook AI Similarity Search — high-performance vector search. Used by Trend Hunter to index scraped web documents. HuggingFace all-MiniLM-L6-v2 embeddings. Enables local RAG without an external database.',
  },
  bm: {
    center: 'AI agent 4 platform. LangGraph baara kɛla: Trend + Vision + Emotion → Creative. Backend Django, frontend React. Python 3.11, WebSocket.',
    trend: 'Marchɛ sèbèni agent. DuckDuckGo 15-20 kunnafoni sɔrɔ. Score (0-10). Sinyali gɛlɛnw sɔrɔ. Groq 70B → ESPRIT. Risk + pre-mortem sèbèni.',
    vision: 'Visual branding agent. Archétype sèbèni. Couleur, typographie, SVG, moodboard kɛ. Groq 8B → ESPRIT. HuggingFace FLUX.1 → Pollinations.',
    emotion: 'Haminɛ sèbèni agent. OCEAN profile (Big Five) kɛ. Journey Map, Sentiment, nudges, Tone of Voice. Groq 8B → ESPRIT.',
    creative: 'Sèbèni gɛlɛn agent. Disruption Scores, Roadmap 4, Killer Features, Pivot, MVP. Groq 70B → ESPRIT.',
    langgraph: 'Multi-agent framework. StateGraph. Trend + Vision + Emotion asyncio.gather → Creative. astream() WebSocket ma.',
    ws: 'Django Channels ASGI. Agent kelen kelen ka jaabi bila. Image > 800KB wɛrɛ message kɛ. AppContext WebSocket singleton.',
    ocean: 'Big Five (Costa & McCrae, 1992). Traits 5: Ouverture, Conscienciosité, Extraversion, Agréabilité, Névrotisme. Marketing tone kama.',
    flux: 'Black Forest Labs image model. HuggingFace (40s) → Pollinations. 3D renders roadmap kama.',
    faiss: 'Facebook vector search. Trend Hunter ka documents index kɛ. HuggingFace MiniLM embeddings. Local RAG.',
  },
  ar: {
    center: 'منصة متعددة الوكلاء للذكاء الاستراتيجي. 4 وكلاء AI منسقون بواسطة LangGraph بالتوازي: Trend + Vision + Emotion → Creative. الخلفية Django + Channels، الواجهة React + Framer Motion. المكدس: Python 3.11، WebSocket في الوقت الفعلي.',
    trend: 'وكيل استخبارات السوق في الوقت الفعلي. يجمع من DuckDuckGo (15-20 مصدراً). يحسب درجة السوق (0-10). يكتشف الإشارات الضعيفة. يستخدم Groq 70B ← ESPRIT احتياطياً. يولد تحليل المخاطر + التحليل التنافسي.',
    vision: 'وكيل السيميائيات البصرية والعلامة التجارية. يحلل النمط البصري المهيمن (Glassmorphism، Brutalism...). يولد: لوحات الألوان، أزواج الخطوط، أيقونة SVG، لوحة مزاجية. النموذج: Groq 8B ← ESPRIT. الصور: HuggingFace FLUX.1 ← Pollinations.',
    emotion: 'وكيل علم النفس السلوكي. يبني ملف OCEAN (Big Five). ينتج: خريطة رحلة العميل، سرعة المشاعر، قاعة العار، التلميحات السلوكية، نبرة الصوت. النموذج: Groq 8B ← ESPRIT.',
    creative: 'وكيل التوليف الاستراتيجي النهائي. ينتج: درجات التعطيل (5 محاور)، خارطة طريق 4 مراحل + صور FLUX.1، ميزات قاتلة، محور جذري، اختبار ضغط، مخطط MVP. النموذج: Groq 70B ← ESPRIT.',
    langgraph: 'إطار تنسيق متعدد الوكلاء. StateGraph مع TypedDict مشترك. Trend + Vision + Emotion يعملون بالتوازي عبر asyncio.gather، ثم Creative يجمع. compiled_graph.astream() يبث الأحداث إلى WebSocket.',
    ws: 'Django Channels (ASGI) — AsyncWebsocketConsumer. يرسل النتائج وكيلاً بوكيل فور انتهائه. الانقسام التكيفي: صور base64 > 800KB ترسل بشكل منفصل. الواجهة: WebSocket singleton عالمي في AppContext.',
    ocean: 'نموذج Big Five النفسي (Costa & McCrae, 1992). خمس سمات من 0 إلى 100: الانفتاح، الضمير، الانبساط، المقبولية، العصابية. يُستخدم لاستهداف رسائل التسويق ونبرة العلامة التجارية.',
    flux: 'نموذج توليد الصور من Black Forest Labs. معمارية Diffusion Transformer. يعمل عبر HuggingFace InferenceClient (مهلة 40 ثانية) ← Pollinations احتياطياً. يولد عروضاً ثلاثية الأبعاد لخارطة الطريق.',
    faiss: 'Facebook AI Similarity Search — بحث متجهي عالي الأداء. يستخدمه Trend Hunter لفهرسة الوثائق المجمعة من الويب. تضمينات HuggingFace all-MiniLM-L6-v2. يتيح RAG محلياً بدون قاعدة بيانات خارجية.',
  },
}

function BrainMapView({ t, lang }) {
  const [selectedNode, setSelectedNode] = useState(null)
  const nodeDescs = NODES_I18N[lang] || NODES_I18N.fr
  const nodes = [
    { id: 'center', label: 'StartWise', x: 320, y: 200, r: 30, color: '#a855f7', desc: nodeDescs.center },
    { id: 'trend',  label: 'Trend Hunter', x: 120, y: 80, r: 22, color: '#3b82f6', desc: nodeDescs.trend },
    { id: 'vision', label: 'Visual Agent', x: 520, y: 80, r: 22, color: '#ec4899', desc: nodeDescs.vision },
    { id: 'emotion',label: 'Emotion AI',   x: 120, y: 330, r: 22, color: '#10b981', desc: nodeDescs.emotion },
    { id: 'creative',label: 'Creative Dir.',x: 520, y: 330, r: 22, color: '#f97316', desc: nodeDescs.creative },
    { id: 'langgraph',label: 'LangGraph',  x: 320, y: 350, r: 18, color: '#6366f1', desc: nodeDescs.langgraph },
    { id: 'ws',     label: 'WebSocket',    x: 200, y: 200, r: 16, color: '#06b6d4', desc: nodeDescs.ws },
    { id: 'ocean',  label: 'OCEAN',        x: 430, y: 200, r: 16, color: '#10b981', desc: nodeDescs.ocean },
    { id: 'flux',   label: 'FLUX.1',       x: 320, y: 80,  r: 16, color: '#f59e0b', desc: nodeDescs.flux },
    { id: 'faiss',  label: 'FAISS',        x: 60,  y: 200, r: 14, color: '#3b82f6', desc: nodeDescs.faiss },
  ]
  const edges = [
    ['center','trend'],['center','vision'],['center','emotion'],['center','creative'],
    ['center','langgraph'],['center','ws'],['center','ocean'],['center','flux'],
    ['trend','faiss'],['emotion','ocean'],['vision','flux'],['creative','flux'],
  ]

  return (
    <div className="p-8 space-y-4">
      <div>
        <h2 className="text-2xl font-black text-gray-900 dark:text-white">{t.docsTitle}</h2>
        <p className="text-sm text-gray-500 mt-1">{t.docsSub}</p>
        <p className="text-xs text-gray-400 mt-1">{t.clickNode}</p>
      </div>
      <div className="flex gap-6 flex-col md:flex-row">
        <div className="flex-shrink-0 bg-gray-950 rounded-3xl border border-gray-800 overflow-hidden" style={{ width: 640, height: 420 }}>
          <svg width="640" height="420" viewBox="0 0 640 420">
            {edges.map(([a, b], i) => {
              const na = nodes.find(n => n.id === a)
              const nb = nodes.find(n => n.id === b)
              if (!na || !nb) return null
              return <line key={i} x1={na.x} y1={na.y} x2={nb.x} y2={nb.y} stroke="#374151" strokeWidth="1" strokeDasharray="4,4" opacity="0.6"/>
            })}
            {nodes.map(node => (
              <g key={node.id} onClick={() => setSelectedNode(selectedNode?.id === node.id ? null : node)}
                style={{ cursor: 'pointer' }}>
                {/* scale instead of r — Framer Motion can't animate SVG attrs directly */}
                <motion.circle cx={node.x} cy={node.y} r={node.r + 10} fill={node.color} opacity="0.1"
                  animate={{ scale: [0.7, 1.3, 0.7], opacity: [0.08, 0.18, 0.08] }}
                  transition={{ duration: 2.5, repeat: Infinity, delay: nodes.indexOf(node) * 0.3 }}
                  style={{ transformOrigin: `${node.x}px ${node.y}px` }}/>
                <circle cx={node.x} cy={node.y} r={node.r} fill={`${node.color}33`} stroke={node.color} strokeWidth={selectedNode?.id === node.id ? 2.5 : 1.5}/>
                <text x={node.x} y={node.y + 1} textAnchor="middle" dominantBaseline="middle" fill="white" fontSize={node.id === 'center' ? 11 : 9} fontWeight="700">{node.label}</text>
              </g>
            ))}
          </svg>
        </div>
        <AnimatePresence>
          {selectedNode && (
            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}
              className="flex-1 rounded-3xl p-6 border overflow-y-auto"
              style={{ borderColor: `${selectedNode.color}55`, background: `linear-gradient(135deg, ${selectedNode.color}12, ${selectedNode.color}06)`, maxHeight: 420 }}>
              <div className="flex items-center gap-3 mb-5">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center shadow-lg" style={{ background: `${selectedNode.color}33`, border: `2px solid ${selectedNode.color}88` }}>
                  <span className="text-base font-black" style={{ color: selectedNode.color }}>{selectedNode.label.slice(0,2).toUpperCase()}</span>
                </div>
                <div>
                  <h3 className="font-black text-lg text-white">{selectedNode.label}</h3>
                  <div className="w-8 h-0.5 rounded-full mt-1" style={{ background: selectedNode.color }}/>
                </div>
              </div>
              <p className="text-sm text-gray-200 leading-relaxed whitespace-pre-line">{selectedNode.desc}</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

// ==================== SETTINGS — Engine Room ====================
// Modèles Groq réels disponibles — mappés dans SmartInferenceProvider côté backend
const REAL_MODELS = [
  { id: 'llama-70b', label: 'Llama 70B', emoji: '🦙', color: '#f97316', desc: 'Groq · llama-3.3-70b-versatile · Qualité max' },
  { id: 'llama-8b',  label: 'Llama 8B',  emoji: '⚡', color: '#3b82f6', desc: 'Groq · llama-3.1-8b-instant · Ultra-rapide' },
  { id: 'qwen-32b',  label: 'Qwen 32B',  emoji: '🐉', color: '#a855f7', desc: 'Groq · qwen/qwen3-32b · Alibaba Cloud · Multilingue' },
  { id: 'kimi-k2',   label: 'Kimi K2',   emoji: '🌙', color: '#10b981', desc: 'Groq · moonshotai/kimi-k2-instruct · Créatif & long contexte' },
]

function SettingsView({ settings, setSettings, t }) {
  const modelColors = Object.fromEntries(REAL_MODELS.map(m => [m.id, m.color]))
  const [gauges, setGauges] = useState({ cpu: 67, mem: 45, gpu: 89 })

  useEffect(() => {
    const iv = setInterval(() => {
      setGauges(g => ({
        cpu: Math.min(96, Math.max(18, g.cpu + (Math.random() - 0.48) * 9)),
        mem: Math.min(88, Math.max(28, g.mem + (Math.random() - 0.5) * 5)),
        gpu: Math.min(99, Math.max(35, g.gpu + (Math.random() - 0.45) * 11)),
      }))
    }, 2200)
    return () => clearInterval(iv)
  }, [])

  return (
    <div className="p-8 space-y-8">
      <div>
        <h2 className="text-2xl font-black text-gray-900 dark:text-white">{t.settingsTitle}</h2>
        <p className="text-sm text-gray-500 mt-1">{t.settingsSub}</p>
      </div>

      {/* Cockpit panel */}
      <div className="rounded-3xl p-8 space-y-8 border border-gray-800" style={{ background: 'radial-gradient(ellipse at top, rgba(99,102,241,0.1) 0%, rgba(17,24,39,0.9) 60%)', backdropFilter: 'blur(12px)' }}>

        {/* Power Level — Créativité vs Logique */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-black text-white text-sm uppercase tracking-widest">{t.powerLevel}</p>
              <p className="text-xs text-gray-400 mt-0.5">{t.creativity} ←→ {t.logic}</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-orange-400">{settings.creativity}%</span>
              <div className="w-2 h-2 rounded-full bg-orange-400 animate-pulse" />
            </div>
          </div>
          <div className="relative">
            <div className="h-3 rounded-full bg-gray-800 overflow-hidden">
              <motion.div className="h-full rounded-full" style={{ width: `${settings.creativity}%`, background: 'linear-gradient(90deg, #6366f1, #f97316)' }} />
            </div>
            <input type="range" min="0" max="100" value={settings.creativity}
              onChange={e => setSettings(s => ({ ...s, creativity: Number(e.target.value) }))}
              className="absolute inset-0 w-full opacity-0 cursor-pointer h-3" />
          </div>
          <div className="flex justify-between text-[10px] text-gray-500">
            <span>🎨 {t.creativity}</span><span>🧮 {t.logic}</span>
          </div>
        </div>

        {/* Model Selector — réel */}
        <div className="space-y-3">
          <div>
            <p className="font-black text-white text-sm uppercase tracking-widest">{t.modelSelector}</p>
            <p className="text-[11px] text-emerald-400/80 mt-1 flex items-center gap-1.5">
              <span>✅</span>{t.modelNote}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {REAL_MODELS.map(m => (
              <motion.button key={m.id} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
                onClick={() => setSettings(s => ({ ...s, model: m.id }))}
                className="p-3 rounded-xl border-2 text-left transition-all"
                style={{ borderColor: settings.model === m.id ? m.color : '#374151', background: settings.model === m.id ? `${m.color}18` : 'transparent' }}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-lg">{m.emoji}</span>
                  <span className="font-black text-sm" style={{ color: settings.model === m.id ? m.color : '#e5e7eb' }}>{m.label}</span>
                  {settings.model === m.id && (
                    <span className="ml-auto text-[9px] font-bold px-1.5 py-0.5 rounded-full" style={{ background: `${m.color}30`, color: m.color }}>ACTIF</span>
                  )}
                </div>
                <p className="text-[10px] text-gray-500 leading-tight">{m.desc}</p>
              </motion.button>
            ))}
          </div>
        </div>

        {/* Deep Scan toggle */}
        <div className="flex items-center justify-between p-4 rounded-2xl border" style={{ borderColor: settings.deepScan ? '#6366f188' : '#374151', background: settings.deepScan ? '#6366f118' : 'transparent' }}>
          <div>
            <div className="flex items-center gap-2">
              <p className="font-black text-white text-sm">{t.deepScan}</p>
              {settings.deepScan && (
                <motion.span animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 1.5, repeat: Infinity }}
                  className="text-[10px] font-bold px-2 py-0.5 rounded-full text-indigo-300 border border-indigo-500/50" style={{ background: '#6366f122' }}>
                  {t.deepScanActive}
                </motion.span>
              )}
              {!settings.deepScan && (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full text-gray-500 border border-gray-700">
                  {t.deepScanFast}
                </span>
              )}
            </div>
            <p className="text-xs text-gray-400 mt-0.5">{t.deepScanDesc}</p>
          </div>
          <motion.button onClick={() => setSettings(s => ({ ...s, deepScan: !s.deepScan }))}
            className="w-14 h-7 rounded-full relative transition-colors flex-shrink-0"
            style={{ background: settings.deepScan ? '#6366f1' : '#374151' }}>
            <motion.div className="absolute top-1 w-5 h-5 rounded-full bg-white shadow"
              animate={{ left: settings.deepScan ? 28 : 4 }} transition={{ type: 'spring', stiffness: 500, damping: 30 }} />
          </motion.button>
        </div>

        {/* Gauge visuals — dynamiques */}
        <div className="space-y-2">
          <p className="font-black text-white text-sm uppercase tracking-widest">{t.sysResources}</p>
          <p className="text-xs text-gray-400">{t.sysResourcesSub}</p>
        </div>
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: 'CPU', value: Math.round(gauges.cpu), color: '#3b82f6', icon: '💻' },
            { label: 'MEM', value: Math.round(gauges.mem), color: '#10b981', icon: '🧠' },
            { label: 'GPU', value: Math.round(gauges.gpu), color: '#f97316', icon: '⚡' },
          ].map(g => (
            <div key={g.label} className="flex flex-col items-center gap-2">
              <div className="relative">
                <svg width="80" height="80" viewBox="0 0 80 80">
                  <circle cx="40" cy="40" r="32" fill="none" stroke="#1f2937" strokeWidth="8"/>
                  <motion.circle cx="40" cy="40" r="32" fill="none" stroke={g.color} strokeWidth="8"
                    strokeLinecap="round" strokeDasharray={`${2*Math.PI*32}`}
                    initial={{ strokeDashoffset: 2*Math.PI*32 }}
                    animate={{ strokeDashoffset: 2*Math.PI*32*(1-g.value/100) }}
                    transition={{ duration: 0.8 }}
                    style={{ transformOrigin: '40px 40px', transform: 'rotate(-90deg)', filter: `drop-shadow(0 0 4px ${g.color}88)` }}/>
                  <text x="40" y="40" textAnchor="middle" fill={g.color} fontSize="13" fontWeight="800" dominantBaseline="middle">{g.value}%</text>
                </svg>
                <motion.div className="absolute -top-1 -right-1 w-3 h-3 rounded-full"
                  style={{ background: g.value > 80 ? '#ef4444' : g.value > 60 ? '#f97316' : '#10b981' }}
                  animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 1.2, repeat: Infinity }}/>
              </div>
              <div className="text-center">
                <span className="text-xs font-black text-gray-300">{g.icon} {g.label}</span>
                <div className={`text-[10px] mt-0.5 ${g.value > 80 ? 'text-red-400' : g.value > 60 ? 'text-orange-400' : 'text-green-400'}`}>
                  {g.value > 80 ? t.statusHigh : g.value > 60 ? t.statusMedium : t.statusNormal}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ==================== COMMERCIAL VALIDATION PANEL ====================
function CommercialValidationPanel({ commercialResult, t, lang }) {
  const cr = commercialResult || {}
  const emailDrafts   = cr.email_drafts  || []
  const socialPosts   = cr.social_posts  || {}
  const fbPost        = socialPosts.facebook  || {}
  const igPost        = socialPosts.instagram || {}

  // Local editable state
  const [emails, setEmails]     = useState(() => emailDrafts.map(d => ({ ...d })))
  const [fb, setFb]             = useState(fbPost.post || '')
  const [ig, setIg]             = useState(igPost.caption || '')
  const [igTags, setIgTags]     = useState((igPost.hashtags || []).join(' '))
  const [sending, setSending]   = useState({})
  const [sent, setSent]         = useState({})
  const [error, setError]       = useState({})
  const [copied, setCopied]     = useState({})
  const [postCopied, setPostCopied] = useState({})

  useEffect(() => {
    setEmails(emailDrafts.map(d => ({ ...d })))
    setFb(fbPost.post || '')
    setIg(igPost.caption || '')
    setIgTags((igPost.hashtags || []).join(' '))
  }, [commercialResult])

  const updateEmail = (idx, field, val) =>
    setEmails(prev => prev.map((e, i) => i === idx ? { ...e, [field]: val } : e))

  const handleSendEmail = async (idx) => {
    const draft = emails[idx]
    if (!draft.prospect?.email) return
    setSending(p => ({ ...p, [idx]: true }))
    setError(p => ({ ...p, [idx]: '' }))
    try {
      const res = await fetch('http://localhost:8000/api/send-email/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to_email:  draft.prospect.email,
          subject:   draft.subject,
          body:      draft.body,
          from_name: 'StartWise',
        }),
      })
      const data = await res.json()
      if (data.success) setSent(p => ({ ...p, [idx]: true }))
      else setError(p => ({ ...p, [idx]: data.error || 'Erreur inconnue' }))
    } catch (e) {
      setError(p => ({ ...p, [idx]: e.message }))
    } finally {
      setSending(p => ({ ...p, [idx]: false }))
    }
  }

  const handleCopyAndOpen = async (platform) => {
    const content = platform === 'instagram' ? `${ig}\n\n${igTags}` : fb
    const url = platform === 'facebook'
      ? 'https://www.facebook.com/'
      : 'https://www.instagram.com/'
    try {
      await navigator.clipboard.writeText(content)
      setPostCopied(p => ({ ...p, [platform]: true }))
      setTimeout(() => setPostCopied(p => ({ ...p, [platform]: false })), 3000)
      setTimeout(() => window.open(url, '_blank'), 400)
    } catch (_) {
      window.open(url, '_blank')
    }
  }

  const copyToClipboard = async (key, text) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(p => ({ ...p, [key]: true }))
      setTimeout(() => setCopied(p => ({ ...p, [key]: false })), 2000)
    } catch (_) {}
  }

  if (!emailDrafts.length && !fbPost.post && !igPost.caption) return null

  const tc = t.commercial || {}

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      className="mx-6 mb-8 rounded-3xl border border-pink-200 dark:border-pink-900/40 bg-gradient-to-br from-pink-50/60 to-white dark:from-gray-900 dark:to-gray-950 overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-pink-100 dark:border-pink-900/30 bg-gradient-to-r from-pink-500/10 to-transparent">
        <div className="w-10 h-10 rounded-xl bg-pink-500/15 border border-pink-400/30 flex items-center justify-center text-xl">🤝</div>
        <div>
          <h2 className="font-bold text-gray-900 dark:text-white text-sm">{tc.title || 'Agent Commercial — Tableau de Validation'}</h2>
          <p className="text-xs text-gray-500">{tc.subtitle || 'Vérifiez et approuvez chaque action avant envoi'}</p>
        </div>
        <div className="ml-auto px-3 py-1 rounded-full bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 text-xs font-semibold">
          {tc.awaitingValidation || 'En attente de validation'}
        </div>
      </div>

      <div className="p-6 space-y-8">

        {/* ── EMAILS ─────────────────────────────────────────── */}
        {emails.length > 0 && (
          <div>
            <h3 className="text-sm font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <span className="text-base">📧</span>
              {tc.emailsTitle || `Mails de prospection (${emails.length} prospects)`}
            </h3>
            <div className="grid gap-4">
              {emails.map((draft, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.1 }}
                  className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-5 space-y-3"
                >
                  {/* Prospect badge */}
                  <div className="flex items-start justify-between flex-wrap gap-2">
                    <div>
                      <p className="text-sm font-bold text-gray-900 dark:text-white">{draft.prospect?.name}</p>
                      <p className="text-xs text-gray-500">{draft.prospect?.role} · {draft.prospect?.company}</p>
                      <div className="flex items-center gap-1.5 mt-1">
                        <span className="text-xs text-pink-600 dark:text-pink-400 font-mono">{draft.prospect?.email}</span>
                        {draft.prospect?.email_source === 'hunter.io' && (
                          <span className="px-1.5 py-0.5 rounded bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 text-[10px] font-semibold">Hunter.io ✓</span>
                        )}
                      </div>
                    </div>
                    <p className="text-xs text-gray-400 italic max-w-xs">{draft.prospect?.why_fit}</p>
                  </div>

                  {/* Subject */}
                  <div>
                    <label className="text-xs text-gray-400 uppercase tracking-wide mb-1 block">{tc.subject || 'Objet'}</label>
                    <input
                      type="text"
                      value={draft.subject}
                      onChange={e => updateEmail(idx, 'subject', e.target.value)}
                      disabled={sent[idx]}
                      className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-pink-400 disabled:opacity-60"
                    />
                  </div>

                  {/* Body */}
                  <div>
                    <label className="text-xs text-gray-400 uppercase tracking-wide mb-1 block">{tc.body || 'Corps du mail'}</label>
                    <textarea
                      value={draft.body}
                      onChange={e => updateEmail(idx, 'body', e.target.value)}
                      disabled={sent[idx]}
                      rows={5}
                      className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-pink-400 resize-none disabled:opacity-60"
                    />
                  </div>

                  {/* Actions */}
                  {error[idx] && <p className="text-xs text-red-500">{error[idx]}</p>}
                  <div className="flex items-center gap-3">
                    {sent[idx] ? (
                      <span className="flex items-center gap-1.5 text-green-600 dark:text-green-400 text-sm font-semibold">
                        ✅ {tc.sent || 'Envoyé !'}
                      </span>
                    ) : (
                      <motion.button
                        whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                        onClick={() => handleSendEmail(idx)}
                        disabled={sending[idx] || !draft.subject || !draft.body}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl bg-pink-500 hover:bg-pink-600 text-white text-sm font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {sending[idx] ? (
                          <><motion.span animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 0.8, ease: 'linear' }}>⏳</motion.span> {tc.sending || 'Envoi...'}</>
                        ) : (
                          <><span>📨</span> {tc.sendEmail || 'Envoyer ce mail'}</>
                        )}
                      </motion.button>
                    )}
                    <button
                      onClick={() => copyToClipboard(`email_${idx}`, `${draft.subject}\n\n${draft.body}`)}
                      className="px-3 py-2 rounded-xl border border-gray-200 dark:border-gray-700 text-gray-500 hover:text-gray-900 dark:hover:text-white text-sm transition-colors"
                    >
                      {copied[`email_${idx}`] ? '✓ Copié' : '📋 Copier'}
                    </button>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        )}

        {/* ── SOCIAL POSTS ──────────────────────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

          {/* Facebook */}
          {fb && (
            <div className="rounded-2xl border border-blue-200 dark:border-blue-900/40 bg-white dark:bg-gray-900 p-5 space-y-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-lg">📘</span>
                <span className="font-bold text-sm text-gray-900 dark:text-white">Facebook</span>
                <span className="ml-auto text-xs text-gray-400">{fb.length} {tc.chars || 'car.'}</span>
              </div>
              <textarea
                value={fb}
                onChange={e => setFb(e.target.value)}
                disabled={sent['facebook']}
                rows={7}
                className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none disabled:opacity-60"
              />
              <div className="flex gap-2 flex-wrap">
                <motion.button
                  whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                  onClick={() => handleCopyAndOpen('facebook')}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold transition-colors"
                >
                  {postCopied['facebook']
                    ? '✅ Copié — ouverture Facebook...'
                    : '📋 Copier & ouvrir Facebook'}
                </motion.button>
              </div>
              <p className="text-[11px] text-gray-400 mt-1">Le texte est copié dans le presse-papier, Facebook s'ouvre dans un nouvel onglet — colle et publie.</p>
            </div>
          )}

          {/* Instagram */}
          {ig && (
            <div className="rounded-2xl border border-pink-200 dark:border-pink-900/40 bg-white dark:bg-gray-900 p-5 space-y-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-lg">📸</span>
                <span className="font-bold text-sm text-gray-900 dark:text-white">Instagram</span>
                <span className="ml-auto text-xs text-gray-400">{ig.length} {tc.chars || 'car.'}</span>
              </div>
              <textarea
                value={ig}
                onChange={e => setIg(e.target.value)}
                disabled={sent['instagram']}
                rows={4}
                className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-pink-400 resize-none disabled:opacity-60"
              />
              <div>
                <label className="text-xs text-gray-400 uppercase tracking-wide mb-1 block"># Hashtags</label>
                <input
                  type="text"
                  value={igTags}
                  onChange={e => setIgTags(e.target.value)}
                  disabled={sent['instagram']}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 text-pink-500 dark:text-pink-400 focus:outline-none focus:ring-2 focus:ring-pink-400 disabled:opacity-60"
                  placeholder="#hashtag1 #hashtag2..."
                />
              </div>
              <div className="flex gap-2 flex-wrap">
                <motion.button
                  whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                  onClick={() => handleCopyAndOpen('instagram')}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-pink-500 to-purple-500 hover:from-pink-600 hover:to-purple-600 text-white text-sm font-semibold transition-colors"
                >
                  {postCopied['instagram']
                    ? '✅ Copié — ouverture Instagram...'
                    : '📋 Copier & ouvrir Instagram'}
                </motion.button>
              </div>
              <p className="text-[11px] text-gray-400 mt-1">Le texte est copié dans le presse-papier, Instagram s'ouvre dans un nouvel onglet — colle et publie.</p>
            </div>
          )}
        </div>

        <p className="text-xs text-gray-400 text-center pt-2">
          {tc.disclaimer || '⚠️ Chaque action nécessite votre approbation explicite. Aucun envoi n\'est effectué sans votre validation.'}
        </p>
      </div>
    </motion.div>
  )
}

// ==================== LANGUAGE SELECTOR ====================
function LanguageSelector({ lang, setLang }) {
  const [open, setOpen] = useState(false)
  const langs = [
    { code: 'fr', flag: '🇫🇷', label: 'Français' },
    { code: 'en', flag: '🇬🇧', label: 'English' },
    { code: 'bm', flag: '🇲🇱', label: 'Bambara' },
    { code: 'ar', flag: '🇸🇦', label: 'العربية' },
  ]
  const current = langs.find(l => l.code === lang) || langs[0]
  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
        <span>{current.flag}</span>
        <span className="text-gray-600 dark:text-gray-400 hidden sm:block">{current.label}</span>
        <span className="text-gray-400 text-xs">▾</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
            className="absolute right-0 mt-1 w-36 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 shadow-xl overflow-hidden z-50">
            {langs.map(l => (
              <button key={l.code} onClick={() => { setLang(l.code); setOpen(false) }}
                className={`w-full flex items-center gap-2 px-3 py-2 text-sm transition-colors ${lang === l.code ? 'bg-purple-50 dark:bg-purple-950/30 text-purple-600' : 'hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300'}`}>
                <span>{l.flag}</span><span>{l.label}</span>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ==================== SIDEBAR NAV ITEM ====================
function NavItem({ icon, label, active, onClick }) {
  return (
    <button onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${active ? 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white font-semibold' : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800'}`}>
      <span className="text-base">{icon}</span>
      <span>{label}</span>
    </button>
  )
}

// ==================== MAIN DASHBOARD ====================
export default function Dashboard() {
  const router = useRouter()
  const { lang, setLang, t, isDarkMode, setIsDarkMode, projectDesc, setProjectDesc, isRunning, agentsStatus, agentsResults, currentThoughts, stats, analysisHistory, settings, setSettings, launchAnalysis, loadAnalysis, clearAnalysis, documentText, setDocumentText, documentFileName, setDocumentFileName } = useApp()
  const [activeNav, setActiveNav] = useState('dashboard')
  const [showLaunchOverlay, setShowLaunchOverlay] = useState(false)
  const [showBPlan, setShowBPlan] = useState(false)
  const [showPitch, setShowPitch] = useState(false)

  const launchMessages = [t.launchMsg1, t.launchMsg2, t.launchMsg3, t.launchMsg4]

  const [docUploading, setDocUploading] = useState(false)
  const [docError, setDocError] = useState('')
  const fileInputRef = useRef(null)

  // Sync ideation data — uniquement si l'onboarding a été complété dans cette session
  useEffect(() => {
    const isFreshSession = sessionStorage.getItem('sw_fresh_session') === '1'

    if (!isFreshSession) {
      // Nouvelle session : effacer les données périmées et rediriger vers l'onboarding
      clearAnalysis()
      localStorage.removeItem('sw_ideation_data')
      localStorage.removeItem('sw_ideation_summary')
      localStorage.removeItem('sw_ideation_business_idea')
      router.replace('/onboarding?reset=true')
      return
    }

    // Session fraîche — charger les données d'idéation normalement
    const ideationIdea = localStorage.getItem('sw_ideation_business_idea') || ''
    const ideationSummary = localStorage.getItem('sw_ideation_summary') || ''
    if (ideationIdea && ideationIdea !== projectDesc) {
      setProjectDesc(ideationIdea)
      clearAnalysis()
    }
    if (ideationSummary && ideationSummary !== documentText) {
      setDocumentText(ideationSummary)
      setDocumentFileName('📋 Résumé Idéation')
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleLaunch = () => {
    if (!projectDesc.trim() || isRunning) return
    setShowLaunchOverlay(true)
    setTimeout(() => setShowLaunchOverlay(false), 5000)
    launchAnalysis(projectDesc)
  }

  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    // Reset input so selecting the same file again triggers onChange
    e.target.value = ''

    if (file.size > 5 * 1024 * 1024) {
      setDocError(t.docTooLarge)
      setTimeout(() => setDocError(''), 4000)
      return
    }
    setDocError('')
    setDocUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch('http://localhost:8000/api/upload-document/', {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || t.docError)
      setDocumentText(data.text)
      setDocumentFileName(data.filename)
    } catch (err) {
      setDocError(err.message || t.docError)
      setTimeout(() => setDocError(''), 4000)
    } finally {
      setDocUploading(false)
    }
  }

  const clearDocument = () => {
    setDocumentText('')
    setDocumentFileName('')
    setDocError('')
  }

  const handleAgentClick = (agentId) => {
    const status = agentsStatus[agentId]?.status
    // Permet de naviguer dès que l'agent a un résultat partiel OU est completed
    // Le WebSocket continue en background via le contexte global
    if (status === 'completed' || (status === 'running' && agentsResults[agentId])) {
      router.push(`/agent/${agentId}`)
    }
  }

  const NAV_ITEMS = [
    { id: 'dashboard', icon: '📊', label: t.dashboard },
    { id: 'analyses', icon: '📈', label: t.analyses },
    { id: 'team', icon: '👥', label: t.team },
    { id: 'documentation', icon: '📚', label: t.documentation },
    { id: 'settings', icon: '⚙️', label: t.settings },
  ]

  return (
    <div dir={lang === 'ar' ? 'rtl' : 'ltr'}>
      <AnimatePresence>
        {showLaunchOverlay && <LaunchOverlay messages={launchMessages} t={t} />}
      </AnimatePresence>

      {/* Modals — rendus hors du layout pour éviter overflow hidden */}
      <BusinessPlanModal open={showBPlan} onClose={() => setShowBPlan(false)}
        agentsResults={agentsResults} lang={lang} projectDesc={projectDesc} />
      <PitchDeckModal open={showPitch} onClose={() => setShowPitch(false)}
        agentsResults={agentsResults} lang={lang} projectDesc={projectDesc} />

        {/* PAGES — no mode="wait": AnimatePresence reçoit plusieurs enfants (false inclus) */}
        <AnimatePresence>
          {activeNav === 'dashboard' && (
            <motion.div key="dashboard" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>

              {/* Globe Hero */}
              <div className="relative h-[340px] bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-950 overflow-hidden">
                <div className="absolute inset-0 opacity-70">
                  <GlobeNetwork />
                </div>

                {/* Welcome header — SaaS style */}
                <div className="absolute top-8 left-0 right-0 flex flex-col items-center gap-2">
                  <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
                    <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-white/70 dark:bg-gray-900/70 backdrop-blur-sm border border-gray-200/60 dark:border-gray-700/60 shadow-sm mb-2 mx-auto w-fit">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400">{t.welcome}</span>
                    </div>
                    <h1 className="text-2xl font-bold text-center text-gray-900 dark:text-white tracking-tight">
                      StartWise
                    </h1>
                    <p className="text-sm text-center text-gray-400 mt-1">Votre co-fondateur IA — 5 agents, une stratégie complète</p>
                  </motion.div>
                </div>

                {/* Input */}
                <div className="absolute bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-white dark:from-gray-950 via-white/80 dark:via-gray-950/80 to-transparent">
                  <div className="max-w-2xl mx-auto">
                    <motion.div animate={isRunning ? { boxShadow: ['0 0 0px #a855f7', '0 0 20px #a855f733', '0 0 0px #a855f7'] } : {}}
                      transition={{ duration: 2, repeat: Infinity }}
                      className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-700 shadow-xl overflow-hidden">
                      <div className="p-4">
                        <TypewriterInput value={projectDesc} onChange={setProjectDesc} disabled={isRunning} t={t} />
                        <PromptSuggestions onSelect={setProjectDesc} t={t} />

                        {/* Document badge */}
                        {(documentFileName || docUploading || docError) && (
                          <div className="mt-2">
                            {docUploading && (
                              <div className="flex items-center gap-1.5 text-xs text-purple-500">
                                <motion.span animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }} className="inline-block">⚙️</motion.span>
                                {t.docUploading}
                              </div>
                            )}
                            {docError && (
                              <div className="flex items-center gap-1.5 text-xs text-red-500">
                                <span>⚠️</span> {docError}
                              </div>
                            )}
                            {documentFileName && !docUploading && (
                              <div className="flex items-center gap-2">
                                <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-700 text-emerald-700 dark:text-emerald-400 font-medium">
                                  <span>📄</span>
                                  <span className="max-w-[180px] truncate">{documentFileName}</span>
                                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-500 text-white font-bold ml-1">{t.docAnalyzed}</span>
                                </span>
                                <button onClick={clearDocument} disabled={isRunning}
                                  className="w-4 h-4 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center text-gray-500 hover:bg-red-100 hover:text-red-500 transition-colors text-[10px]">
                                  ×
                                </button>
                              </div>
                            )}
                          </div>
                        )}

                        <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
                          <div className="flex items-center gap-3">
                            <span className="text-xs text-gray-400">{projectDesc.length} {t.chars}</span>
                            {/* File upload button */}
                            <input ref={fileInputRef} type="file" accept=".pdf,.txt" className="hidden" onChange={handleFileSelect} />
                            <motion.button
                              onClick={() => fileInputRef.current?.click()}
                              disabled={isRunning || docUploading}
                              whileHover={{ scale: 1.05 }}
                              whileTap={{ scale: 0.95 }}
                              title={t.uploadDoc}
                              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all
                                ${documentFileName
                                  ? 'border-emerald-400 text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/20'
                                  : 'border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:border-purple-400 hover:text-purple-600'
                                } ${isRunning || docUploading ? 'opacity-50 cursor-not-allowed' : ''}`}>
                              <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                              </svg>
                              {documentFileName ? '✓' : t.uploadDoc}
                            </motion.button>
                          </div>
                          <motion.button onClick={handleLaunch}
                            disabled={isRunning || !projectDesc.trim()}
                            whileHover={!isRunning && projectDesc.trim() ? { scale: 1.04 } : {}}
                            whileTap={!isRunning && projectDesc.trim() ? { scale: 0.96 } : {}}
                            className={`px-6 py-2 rounded-xl text-sm font-bold transition-all ${isRunning || !projectDesc.trim() ? 'bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed' : 'bg-gradient-to-r from-purple-600 to-blue-600 text-white shadow-lg shadow-purple-500/25'}`}>
                            {isRunning ? (
                              <span className="flex items-center gap-2">
                                <motion.span animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }} className="inline-block">⚙️</motion.span>
                                {t.launching}
                              </span>
                            ) : t.launch}
                          </motion.button>
                        </div>
                      </div>
                    </motion.div>
                  </div>
                </div>
              </div>

              {/* Agents + Synthesis */}
              <div className="px-8 py-6 space-y-6">
                {/* Agents Grid — full width */}
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  {Object.keys(AGENT_CONFIG).map(id => (
                    <AgentCard key={id} agentId={id}
                      status={agentsStatus[id]?.status || 'idle'}
                      progress={agentsStatus[id]?.progress || 0}
                      onClick={() => handleAgentClick(id)} t={t} />
                  ))}
                </div>

                {/* Executive Synthesis */}
                <ExecutiveSynthesis agentsResults={agentsResults} agentsStatus={agentsStatus} t={t} lang={lang} isDarkMode={isDarkMode}
                  onOpenBPlan={() => setShowBPlan(true)} onOpenPitch={() => setShowPitch(true)} />
              </div>

              {/* Commercial Agent — résumé compact */}
              {agentsResults?.commercial_agent && (
                <div className="px-8 pb-8">
                  <motion.div
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-2xl border border-pink-200 dark:border-pink-900/40 bg-gradient-to-r from-pink-500/5 to-purple-500/5 p-6"
                  >
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-9 h-9 rounded-xl bg-pink-500/15 border border-pink-400/30 flex items-center justify-center text-lg">🤝</div>
                      <div>
                        <h3 className="font-bold text-gray-900 dark:text-white text-sm">The Dealmaker — Agent Commercial</h3>
                        <p className="text-xs text-gray-500">Prospection, emails et posts validés</p>
                      </div>
                      <button
                        onClick={() => handleAgentClick('commercial_agent')}
                        className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-pink-500 hover:bg-pink-600 text-white transition-colors"
                      >
                        Voir le détail →
                      </button>
                    </div>
                    <div className="grid grid-cols-3 gap-4">
                      {[
                        { icon: '🎯', label: 'Prospects', value: agentsResults.commercial_agent.prospects?.length || 0 },
                        { icon: '📧', label: 'Emails rédigés', value: agentsResults.commercial_agent.email_drafts?.length || 0 },
                        { icon: '📱', label: 'Posts créés', value:
                          (agentsResults.commercial_agent.social_posts?.facebook?.post ? 1 : 0) +
                          (agentsResults.commercial_agent.social_posts?.instagram?.caption ? 1 : 0)
                        },
                      ].map((s, i) => (
                        <div key={i} className="bg-white/60 dark:bg-gray-900/60 rounded-xl p-4 border border-white/80 dark:border-gray-800">
                          <div className="text-2xl mb-1">{s.icon}</div>
                          <div className="text-xl font-black text-gray-900 dark:text-white">{s.value}</div>
                          <p className="text-xs text-gray-500 mt-0.5">{s.label}</p>
                        </div>
                      ))}
                    </div>
                    {agentsResults.commercial_agent.prospects?.[0] && (
                      <p className="mt-3 text-xs text-gray-500 italic">
                        Premier prospect : <span className="text-gray-700 dark:text-gray-300 font-medium">
                          {agentsResults.commercial_agent.prospects[0].name} — {agentsResults.commercial_agent.prospects[0].role} @ {agentsResults.commercial_agent.prospects[0].company}
                        </span>
                      </p>
                    )}
                  </motion.div>
                </div>
              )}
            </motion.div>
          )}

          {activeNav === 'analyses' && (
            <motion.div key="analyses" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <ArchiveView history={analysisHistory} agentsResults={agentsResults} agentsStatus={agentsStatus} t={t}
                onReload={(item) => { loadAnalysis(item); setActiveNav('dashboard') }} />
            </motion.div>
          )}

          {activeNav === 'team' && (
            <motion.div key="team" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <AgentTeamView t={t} />
            </motion.div>
          )}

          {activeNav === 'documentation' && (
            <motion.div key="documentation" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <BrainMapView t={t} lang={lang} />
            </motion.div>
          )}

          {activeNav === 'settings' && (
            <motion.div key="settings" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <SettingsView settings={settings} setSettings={setSettings} t={t} />
            </motion.div>
          )}
        </AnimatePresence>
    </div>
  )
}
