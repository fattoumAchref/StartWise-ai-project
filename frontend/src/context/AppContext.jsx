// src/context/AppContext.jsx — WebSocket global + Language + State persistant
import { createContext, useContext, useState, useRef, useEffect, useCallback } from 'react'

// ==================== TRADUCTIONS ====================
export const TRANSLATIONS = {
  fr: {
    // Nav
    dashboard: 'Tableau de bord', analyses: 'Analyses', settings: 'Paramètres',
    documentation: 'Documentation', team: 'Équipe',
    // Header
    dashboardTitle: 'Tableau de bord', dashboardSub: 'Intelligence artificielle pour l\'analyse stratégique',
    // Input
    launch: 'Lancer l\'analyse', launching: 'Analyse en cours...', chars: 'caractères',
    placeholder: 'Décrivez votre projet ou startup...',
    welcome: 'Bonjour, quelle startup voulez-vous analyser ?',
    // Stats
    marketSignals: 'Signaux marché', aiConfidence: 'Confiance IA', concepts: 'Concepts générés',
    detected: 'détectés', variants: 'variants',
    // Agents
    ready: 'Prêt', running: 'Analyse en cours', completed: 'Terminé',
    // Sidebar
    lastAnalysis: 'Dernière analyse', agentsCompleted: 'agents complétés',
    history: 'Historique',
    // Archive
    archiveTitle: 'L\'Archive Holographique', archiveSub: 'Toutes vos analyses précédentes',
    noArchive: 'Aucune analyse sauvegardée. Lancez votre première analyse !',
    riskScore: 'Risque', confidence: 'Confiance', signals: 'Signaux',
    openAnalysis: 'Ouvrir l\'analyse', reloadAnalysis: 'Recharger',
    // Team
    teamTitle: 'La Ruche des Agents', teamSub: 'Sélectionnez un agent pour voir ses compétences',
    skills: 'Compétences', model: 'Modèle', speed: 'Vitesse',
    // Docs
    docsTitle: 'Le Codex Interactif', docsSub: 'Carte mentale de l\'architecture StartWise',
    clickNode: 'Cliquez sur un nœud pour l\'explorer',
    // Settings
    settingsTitle: 'Engine Room', settingsSub: 'Panneau de contrôle des agents',
    creativity: 'Créativité', logic: 'Logique', deepScan: 'Deep Scan',
    deepScanDesc: 'Analyse approfondie (2 min) vs rapide (30s)',
    modelSelector: 'Sélecteur de Modèle',
    powerLevel: 'Niveau de Puissance',
    sysResources: 'Ressources Système', sysResourcesSub: 'Charge serveur en temps réel',
    deepScanActive: 'ACTIF — 8 MIN', deepScanFast: 'RAPIDE — 4 MIN',
    statusHigh: 'ÉLEVÉ', statusMedium: 'MOYEN', statusNormal: 'NORMAL',
    modelNote: 'Modèle actif sur Groq — s\'applique à tous les agents dès la prochaine analyse.',
    // RAG Upload
    uploadDoc: 'Joindre un document', docAnalyzed: 'Document analysé',
    docTooLarge: 'Fichier trop volumineux (max 5 Mo)',
    docError: 'Erreur lors de l\'extraction du texte',
    docUploading: 'Extraction en cours...',
    // Synthesis
    synthTitle: 'Executive AI Synthesis', synthWaiting: 'En attente des 4 agents...',
    synthReady: 'Synthèse prête', masterScore: 'Master Score',
    nextStep1: 'Générer le Business Plan', nextStep2: 'Créer le Pitch Deck', nextStep3: 'Contacter des fournisseurs',
    // Launch anim
    launchMsg1: 'Initialisation des agents IA...', launchMsg2: 'Connexion aux sources de données...',
    launchMsg3: 'Démarrage du pipeline LangGraph...', launchMsg4: 'Les agents travaillent, patientez...',
    // Suggestions
    suggestions: [
      'Une app mobile de livraison de repas healthy pour étudiants',
      'Plateforme SaaS de gestion RH pour PME africaines',
      'Marketplace de freelances tech en Afrique de l\'Ouest',
      'Application d\'épargne et micro-crédit pour femmes entrepreneurs',
      'Solution IoT de suivi agricole pour petits exploitants',
    ],
  },
  en: {
    dashboard: 'Dashboard', analyses: 'Analyses', settings: 'Settings',
    documentation: 'Documentation', team: 'Team',
    dashboardTitle: 'Dashboard', dashboardSub: 'Artificial intelligence for strategic analysis',
    launch: 'Launch Analysis', launching: 'Analyzing...', chars: 'characters',
    placeholder: 'Describe your project or startup...',
    welcome: 'Hello, which startup do you want to analyze?',
    marketSignals: 'Market Signals', aiConfidence: 'AI Confidence', concepts: 'Generated Concepts',
    detected: 'detected', variants: 'variants',
    ready: 'Ready', running: 'Analyzing', completed: 'Completed',
    lastAnalysis: 'Last Analysis', agentsCompleted: 'agents completed',
    history: 'History',
    archiveTitle: 'The Holographic Archive', archiveSub: 'All your previous analyses',
    noArchive: 'No saved analyses. Launch your first analysis!',
    riskScore: 'Risk', confidence: 'Confidence', signals: 'Signals',
    openAnalysis: 'Open Analysis', reloadAnalysis: 'Reload',
    teamTitle: 'The Agent Hive', teamSub: 'Select an agent to see its skills',
    skills: 'Skills', model: 'Model', speed: 'Speed',
    docsTitle: 'The Interactive Codex', docsSub: 'StartWise architecture mind map',
    clickNode: 'Click a node to explore it',
    settingsTitle: 'Engine Room', settingsSub: 'Agent control panel',
    creativity: 'Creativity', logic: 'Logic', deepScan: 'Deep Scan',
    deepScanDesc: 'Deep analysis (2 min) vs fast (30s)',
    modelSelector: 'Model Selector',
    powerLevel: 'Power Level',
    sysResources: 'System Resources', sysResourcesSub: 'Live server load',
    deepScanActive: 'ACTIVE — 8 MIN', deepScanFast: 'FAST — 4 MIN',
    statusHigh: 'HIGH', statusMedium: 'MEDIUM', statusNormal: 'NORMAL',
    modelNote: 'Active model on Groq — applies to all agents on the next analysis.',
    uploadDoc: 'Attach a document', docAnalyzed: 'Document analyzed',
    docTooLarge: 'File too large (max 5 MB)',
    docError: 'Error extracting text',
    docUploading: 'Extracting...',
    synthTitle: 'Executive AI Synthesis', synthWaiting: 'Waiting for 4 agents...',
    synthReady: 'Synthesis ready', masterScore: 'Master Score',
    nextStep1: 'Generate Business Plan', nextStep2: 'Create Pitch Deck', nextStep3: 'Contact Suppliers',
    launchMsg1: 'Initializing AI agents...', launchMsg2: 'Connecting to data sources...',
    launchMsg3: 'Starting LangGraph pipeline...', launchMsg4: 'Agents working, please wait...',
    suggestions: [
      'A mobile app for healthy meal delivery for students',
      'SaaS platform for HR management for African SMEs',
      'Tech freelance marketplace in West Africa',
      'Savings and micro-credit app for women entrepreneurs',
      'IoT crop monitoring solution for small farmers',
    ],
  },
  bm: {
    dashboard: 'Kongolifanga', analyses: 'Sèbèniw', settings: 'Labɛnni',
    documentation: 'Kalan', team: 'Baarakɛlaw',
    dashboardTitle: 'Kongolifanga', dashboardSub: 'Hakilimanw ka baara kɛ sèbèni kama',
    launch: 'Daminɛ', launching: 'Sèbèni bɛ kɛ...', chars: 'sɛbɛnni',
    placeholder: 'I ka projet fɔ...',
    welcome: 'I ni ce, mun startup ye i bɛ sèbèn?',
    marketSignals: 'Marchɛ sinyaliw', aiConfidence: 'AI dɛmɛ', concepts: 'Hadamanw',
    detected: 'sɔrɔlen', variants: 'suguya',
    ready: 'A bɛ fen', running: 'Sèbèni bɛ kɛ', completed: 'A banna',
    lastAnalysis: 'Kɔrɔ sèbèni', agentsCompleted: 'agentw bannen',
    history: 'Kɔrɔ kow',
    archiveTitle: 'Sèbèni Blon', archiveSub: 'I ka kɔrɔ sèbèniw bɛɛ',
    noArchive: 'Sèbèni foyi ma sɔrɔ. I ka fɔlɔ sèbèni daminɛ!',
    riskScore: 'Bɔnya', confidence: 'Dɛmɛ', signals: 'Sinyaliw',
    openAnalysis: 'Sèbèni yɛlɛ', reloadAnalysis: 'Segin',
    teamTitle: 'Agentw Sigida', teamSub: 'Agent dɔ sugandi ka a baara ye',
    skills: 'Dɔnniw', model: 'Modɛli', speed: 'Joona',
    docsTitle: 'Gɛlɛya Jira', docsSub: 'StartWise sigida',
    clickNode: 'Nɔdi dɔ digi ka a lajɛ',
    settingsTitle: 'Jɛkulu Fanga', settingsSub: 'Agentw labɛnni',
    creativity: 'Haminɛ', logic: 'Miiriya', deepScan: 'Kɔrɔfɛ sèbèni',
    deepScanDesc: 'Kɔrɔfɛ sèbèni (2 min) walima joona (30s)',
    modelSelector: 'Modɛli sugandi',
    powerLevel: 'Fanga cogoya',
    sysResources: 'Sɛrɛvɛri Fanga', sysResourcesSub: 'Waati kɔnɔ jira',
    deepScanActive: 'KƐLEN — 8 MIN', deepScanFast: 'JOONA — 4 MIN',
    statusHigh: 'GƐLƐN', statusMedium: 'CƐMANCƐ', statusNormal: 'DƆGƆMAN',
    modelNote: 'Groq modɛli kɛlen — agent bɛɛ ka sèbèni kɔfɛ a bɛ kɛ.',
    uploadDoc: 'Sɛbɛnni lase', docAnalyzed: 'Sɛbɛnni sɛgɛsɛgɛlen',
    docTooLarge: 'Dosiye ka belebeleba (max 5 Mo)',
    docError: 'Sɛbɛnni bɔ sababu',
    docUploading: 'Sɛgɛsɛgɛli bɛ kɛ...',
    synthTitle: 'AI Farafin Sèbèni', synthWaiting: 'Agentw 4 kɔnni...',
    synthReady: 'Sèbèni sigilen', masterScore: 'Hakɛ Gɛlɛn',
    nextStep1: 'Business Plan kɛ', nextStep2: 'Pitch Deck kɛ', nextStep3: 'Jɔyɔrɔw wele',
    launchMsg1: 'AI agentw daminɛ...', launchMsg2: 'Kunnafoniw sɔrɔ...', launchMsg3: 'Pipeline daminɛ...', launchMsg4: 'Agentw bɛ baara kɛ...',
    suggestions: [
      'Mɔbili app dɔ dumuni labɛnni kama',
      'SaaS platform RH kama Afiriki ka PME ma',
      'Freelance marketplace Afiriki Tilɛnfɛ fɛ',
      'Musow ka mara ni kunnafoni app',
      'IoT solution sogo farali kama',
    ],
  },
  ar: {
    dashboard: 'لوحة التحكم', analyses: 'التحليلات', settings: 'الإعدادات',
    documentation: 'التوثيق', team: 'الفريق',
    dashboardTitle: 'لوحة التحكم', dashboardSub: 'الذكاء الاصطناعي للتحليل الاستراتيجي',
    launch: 'إطلاق التحليل', launching: 'جارٍ التحليل...', chars: 'حرف',
    placeholder: 'صف مشروعك أو شركتك الناشئة...',
    welcome: 'مرحباً، ما المشروع الذي تريد تحليله؟',
    marketSignals: 'إشارات السوق', aiConfidence: 'ثقة الذكاء الاصطناعي', concepts: 'المفاهيم المولّدة',
    detected: 'مكتشف', variants: 'نماذج',
    ready: 'جاهز', running: 'جارٍ التحليل', completed: 'مكتمل',
    lastAnalysis: 'آخر تحليل', agentsCompleted: 'وكلاء مكتملون',
    history: 'السجل',
    archiveTitle: 'الأرشيف الهولوغرافي', archiveSub: 'جميع تحليلاتك السابقة',
    noArchive: 'لا توجد تحليلات محفوظة. أطلق تحليلك الأول!',
    riskScore: 'المخاطر', confidence: 'الثقة', signals: 'الإشارات',
    openAnalysis: 'فتح التحليل', reloadAnalysis: 'إعادة التحميل',
    teamTitle: 'خلية الوكلاء', teamSub: 'اختر وكيلاً لرؤية مهاراته',
    skills: 'المهارات', model: 'النموذج', speed: 'السرعة',
    docsTitle: 'الكودكس التفاعلي', docsSub: 'خريطة بنية StartWise',
    clickNode: 'انقر على عقدة لاستكشافها',
    settingsTitle: 'غرفة المحرك', settingsSub: 'لوحة تحكم الوكلاء',
    creativity: 'الإبداع', logic: 'المنطق', deepScan: 'المسح العميق',
    deepScanDesc: 'تحليل عميق (دقيقتان) مقابل سريع (30 ثانية)',
    modelSelector: 'محدد النموذج',
    powerLevel: 'مستوى الطاقة',
    sysResources: 'موارد النظام', sysResourcesSub: 'الحمل المباشر للخادم',
    deepScanActive: 'نشط — 8 دقائق', deepScanFast: 'سريع — 4 دقائق',
    statusHigh: 'مرتفع', statusMedium: 'متوسط', statusNormal: 'طبيعي',
    modelNote: 'النموذج النشط على Groq — يُطبَّق على جميع الوكلاء في التحليل القادم.',
    uploadDoc: 'إرفاق مستند', docAnalyzed: 'تم تحليل المستند',
    docTooLarge: 'الملف كبير جداً (الحد الأقصى 5 ميجابايت)',
    docError: 'خطأ في استخراج النص',
    docUploading: 'جارٍ الاستخراج...',
    synthTitle: 'التوليف التنفيذي بالذكاء الاصطناعي', synthWaiting: 'في انتظار الوكلاء الأربعة...',
    synthReady: 'التوليف جاهز', masterScore: 'النتيجة الرئيسية',
    nextStep1: 'إنشاء خطة عمل', nextStep2: 'إنشاء عرض تقديمي', nextStep3: 'التواصل مع الموردين',
    launchMsg1: 'تهيئة وكلاء الذكاء الاصطناعي...', launchMsg2: 'الاتصال بمصادر البيانات...', launchMsg3: 'بدء خط أنابيب LangGraph...', launchMsg4: 'الوكلاء يعملون، يرجى الانتظار...',
    suggestions: [
      'تطبيق جوال لتوصيل الوجبات الصحية للطلاب',
      'منصة SaaS لإدارة الموارد البشرية للشركات الصغيرة الأفريقية',
      'سوق مستقلين تقنيين في غرب أفريقيا',
      'تطبيق ادخار وقروض صغيرة لرائدات الأعمال',
      'حل إنترنت الأشياء لمراقبة المحاصيل',
    ],
  },
}

const AppContext = createContext(null)

export function AppProvider({ children }) {
  const [lang, setLang] = useState(() => localStorage.getItem('swLang') || 'fr')
  const [isDarkMode, setIsDarkMode] = useState(() => {
    const saved = localStorage.getItem('swDark')
    return saved === 'true'
  })
  const [projectDesc, setProjectDesc] = useState(() => localStorage.getItem('lastProject') || '')
  const [isRunning, setIsRunning] = useState(false)
  const [documentText, setDocumentText] = useState('')
  const [documentFileName, setDocumentFileName] = useState('')
  const [agentsStatus, setAgentsStatus] = useState(() => {
    try { return JSON.parse(localStorage.getItem('agentsStatus') || '{}') } catch { return {} }
  })
  const [agentsResults, setAgentsResults] = useState(() => {
    try { return JSON.parse(localStorage.getItem('agentsResults') || '{}') } catch { return {} }
  })
  const [currentThoughts, setCurrentThoughts] = useState(() => {
    try { return JSON.parse(localStorage.getItem('currentThoughts') || '[]') } catch { return [] }
  })
  const [stats, setStats] = useState(() => {
    try { return JSON.parse(localStorage.getItem('stats') || '{"signals":0,"confidence":0,"concepts":0}') } catch { return { signals: 0, confidence: 0, concepts: 0 } }
  })
  const [analysisHistory, setAnalysisHistory] = useState(() => {
    try {
      const raw = JSON.parse(localStorage.getItem('analysisHistory') || '[]')
      // Deduplicate by id on load (cleans up any duplicates from previous sessions)
      const seen = new Set()
      return raw.filter(item => {
        if (!item?.id || seen.has(item.id)) return false
        seen.add(item.id)
        return true
      })
    } catch { return [] }
  })
  const [settings, setSettings] = useState(() => {
    try {
      const s = JSON.parse(localStorage.getItem('swSettings') || '{"creativity":50,"model":"llama-70b","deepScan":false}')
      const validModels = ['llama-70b', 'llama-8b', 'qwen-32b', 'kimi-k2']
      if (!validModels.includes(s.model)) s.model = 'llama-70b'
      return s
    } catch { return { creativity: 50, model: 'llama-70b', deepScan: false } }
  })
  const [securityToast, setSecurityToast] = useState(null) // { message: string } | null
  const socketRef = useRef(null)
  const agentsResultsRef = useRef({})
  const projectDescRef = useRef(projectDesc)
  const toastTimerRef = useRef(null)
  const t = TRANSLATIONS[lang] || TRANSLATIONS.fr

  useEffect(() => { agentsResultsRef.current = agentsResults }, [agentsResults])
  useEffect(() => { projectDescRef.current = projectDesc }, [projectDesc])

  // Dark mode effect
  useEffect(() => {
    if (isDarkMode) document.documentElement.classList.add('dark')
    else document.documentElement.classList.remove('dark')
    localStorage.setItem('swDark', isDarkMode)
  }, [isDarkMode])

  useEffect(() => { localStorage.setItem('swLang', lang) }, [lang])

  // Persist state
  useEffect(() => {
    // Non-critical items first
    try { localStorage.setItem('agentsStatus', JSON.stringify(agentsStatus)) } catch (_) {}
    try { localStorage.setItem('currentThoughts', JSON.stringify(currentThoughts.slice(-50))) } catch (_) {}
    try { localStorage.setItem('stats', JSON.stringify(stats)) } catch (_) {}
    try { if (projectDesc) localStorage.setItem('lastProject', projectDesc) } catch (_) {}
    try { localStorage.setItem('swSettings', JSON.stringify(settings)) } catch (_) {}

    // agentsResults — strip images before saving
    try {
      const resultsLight = Object.fromEntries(
        Object.entries(agentsResults).map(([agent, result]) => {
          if (!result || typeof result !== 'object') return [agent, result]
          const { images, roadmap_phases, ...rest } = result
          const lightPhases = (roadmap_phases || []).map(({ image, ...p }) => p)
          return [agent, { ...rest, roadmap_phases: lightPhases }]
        })
      )
      localStorage.setItem('agentsResults', JSON.stringify(resultsLight))
    } catch (_) {
      try { localStorage.removeItem('agentsResults') } catch (__) {}
    }

    // analysisHistory — try full (with results), fallback to summary-only
    try {
      localStorage.setItem('analysisHistory', JSON.stringify(analysisHistory.slice(0, 10)))
    } catch (_) {
      try {
        // Fallback: save without results fields to stay under quota
        const slim = analysisHistory.slice(0, 10).map(({ results, ...rest }) => rest)
        localStorage.setItem('analysisHistory', JSON.stringify(slim))
      } catch (__) {}
    }
  }, [agentsStatus, agentsResults, currentThoughts, stats, projectDesc, analysisHistory, settings])

  // WebSocket global — persiste à travers les navigations
  useEffect(() => {
    if (socketRef.current) return
    const socket = new WebSocket('ws://localhost:8000/ws/agents')
    socketRef.current = socket

    socket.onopen = () => console.log('✅ WebSocket global connecté')

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'agent_update') {
        setAgentsStatus(prev => ({
          ...prev,
          [data.agent]: { status: data.status, progress: data.progress || (data.status === 'completed' ? 100 : 50) }
        }))
        if (data.result) {
          setAgentsResults(prev => ({ ...prev, [data.agent]: data.result }))
        }
        if (data.thoughts?.length > 0) {
          setCurrentThoughts(prev => [...prev, { id: Date.now(), agent: data.agent, text: data.thoughts[data.thoughts.length - 1], timestamp: new Date() }])
        }
        if (data.agent === 'trend_hunter' && data.result) {
          setStats(prev => ({ ...prev, signals: data.result.weak_signals?.length || 0, confidence: Math.round((data.result.score || 5) * 10) }))
        }
        if (data.agent === 'creative_director' && data.result) {
          setStats(prev => ({ ...prev, concepts: data.result.killer_features?.length || 0 }))
        }
      }

      if (data.type === 'agent_images') {
        setAgentsResults(prev => {
          const current = prev[data.agent] || {}
          if (data.agent === 'creative_director') {
            const phases = (current.roadmap_phases || []).map((p, i) => ({ ...p, image: data.images[`phase_${i}`] || p.image || '' }))
            return { ...prev, [data.agent]: { ...current, roadmap_phases: phases } }
          }
          return { ...prev, [data.agent]: { ...current, images: data.images } }
        })
      }

      if (data.type === 'error') {
        setIsRunning(false)
        if (data.guard_blocked) {
          if (toastTimerRef.current) clearTimeout(toastTimerRef.current)
          setSecurityToast({ message: data.message })
          toastTimerRef.current = setTimeout(() => setSecurityToast(null), 4000)
        }
      }

      if (data.type === 'analysis_complete') {
        setIsRunning(false)
        const project = projectDescRef.current || localStorage.getItem('lastProject') || ''

        // Use functional setter to guarantee we read the LATEST agentsResults
        // (agentsResultsRef.current may lag by one render cycle)
        setAgentsResults(currentResults => {
          const trendR = currentResults.trend_hunter || {}
          const creativeR = currentResults.creative_director || {}
          const visionR = currentResults.visual_semiotics || {}
          const emotionR = currentResults.emotional_intelligence || {}

          // Strip base64 images before storing
          const lightResults = Object.fromEntries(
            Object.entries(currentResults).map(([agent, result]) => {
              if (!result || typeof result !== 'object') return [agent, result]
              const { images, roadmap_phases, ...rest } = result
              const lightPhases = (roadmap_phases || []).map(({ image, ...p }) => p)
              return [agent, { ...rest, roadmap_phases: lightPhases }]
            })
          )

          setAnalysisHistory(prev => {
            const twoMinAgo = Date.now() - 2 * 60 * 1000
            const isDuplicate = prev.some(h => h.project === project && h.id > twoMinAgo)
            if (isDuplicate) return prev
            return [{
              id: Date.now(),
              project,
              date: new Date().toISOString(),
              confidence: Math.round((trendR.score || 5) * 10),
              riskScore: creativeR.disruption_scores?.risque ?? Math.max(0, 10 - Math.round(trendR.score || 5)),
              signals: trendR.weak_signals?.length || 0,
              innovation: creativeR.disruption_scores?.innovation || 0,
              archetype: visionR.semiotics_analysis?.recommended_archetype || '',
              persona: emotionR.cognitive_strategy?.target_persona?.name || '',
              results: lightResults,
            }, ...prev].slice(0, 15)
          })

          return currentResults // no change to agentsResults itself
        })
      }
    }

    socket.onerror = (err) => console.error('❌ WebSocket error:', err)

    // Ne PAS fermer le socket au unmount — il doit persister
    return () => {}
  }, [])

  const launchAnalysis = useCallback((desc) => {
    if (!desc.trim() || isRunning || !socketRef.current) return
    setIsRunning(true)
    setAgentsStatus({})
    setAgentsResults({})
    setCurrentThoughts([])
    setStats({ signals: 0, confidence: 0, concepts: 0 })
    localStorage.removeItem('agentsStatus')
    localStorage.removeItem('agentsResults')
    socketRef.current.send(JSON.stringify({
      type: 'start_analysis',
      project: desc,
      deep_scan: settings.deepScan,
      creativity: settings.creativity,
      model: settings.model,
      lang,
      document_text: documentText,
    }))
  }, [isRunning, settings])

  const loadAnalysis = useCallback((historyItem) => {
    if (!historyItem) return
    setProjectDesc(historyItem.project)
    setIsRunning(false)

    if (historyItem.results && Object.keys(historyItem.results).length > 0) {
      setAgentsResults(historyItem.results)

      // Rebuild agentsStatus — ensure all 4 known agents are marked completed
      const restoredStatus = {}
      Object.keys(historyItem.results).forEach(agentId => {
        const r = historyItem.results[agentId]
        if (r && typeof r === 'object' && Object.keys(r).length > 0) {
          restoredStatus[agentId] = { status: 'completed', progress: 100 }
        }
      })
      setAgentsStatus(restoredStatus)

      const trendR = historyItem.results.trend_hunter || {}
      const creativeR = historyItem.results.creative_director || {}
      setStats({
        signals: historyItem.signals ?? trendR.weak_signals?.length ?? 0,
        confidence: historyItem.confidence ?? Math.round((trendR.score || 5) * 10),
        concepts: creativeR.killer_features?.length ?? 0,
      })
      setCurrentThoughts([{
        id: Date.now(),
        agent: 'system',
        text: `📂 Analyse du ${new Date(historyItem.date).toLocaleDateString()} rechargée — ${Object.keys(historyItem.results).length} agents restaurés`,
        timestamp: new Date(),
      }])
    } else {
      // Old entry without stored results — clear state and notify
      setAgentsResults({})
      setAgentsStatus({})
      setStats({ signals: historyItem.signals ?? 0, confidence: historyItem.confidence ?? 0, concepts: 0 })
      setCurrentThoughts([{
        id: Date.now(),
        agent: 'system',
        text: `⚠️ Données complètes non disponibles pour cette analyse (sauvegardée avant la mise à jour). Relancez l'analyse pour obtenir les résultats.`,
        timestamp: new Date(),
      }])
    }
  }, [])

  return (
    <AppContext.Provider value={{
      lang, setLang, t, isDarkMode, setIsDarkMode,
      projectDesc, setProjectDesc,
      isRunning, agentsStatus, agentsResults, currentThoughts,
      stats, analysisHistory, settings, setSettings,
      launchAnalysis, loadAnalysis, socketRef,
      securityToast, setSecurityToast,
      documentText, setDocumentText,
      documentFileName, setDocumentFileName,
    }}>
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used inside AppProvider')
  return ctx
}
