// src/pages/Dashboard.jsx - Version avec progression et persistance
import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import GlobeNetwork from '../components/GlobeNetwork'
import AgentCard from '../components/AgentCard'
import ActivityFeed from '../components/ActivityFeed'

const AGENTS = [
  { id: 'trend_hunter', name: 'Market Intelligence', icon: '📈', description: 'Analyse des tendances et signaux faibles', status: 'idle' },
  { id: 'visual_semiotics', name: 'Visual Analytics', icon: '🎨', description: 'Décodage sémiotique et identité visuelle', status: 'idle' },
  { id: 'emotional_intelligence', name: 'Cognitive Analysis', icon: '🧠', description: 'Psychologie de marque et émotions', status: 'idle' },
  { id: 'creative_director', name: 'Generative Design', icon: '✨', description: 'Concepts créatifs et prototypage', status: 'idle' }
]

export default function Dashboard() {
  const navigate = useNavigate()
  
  // Chargement des données sauvegardées
  const [projectDesc, setProjectDesc] = useState(() => {
    return localStorage.getItem('lastProject') || ''
  })
  const [isRunning, setIsRunning] = useState(false)
  const [agentsStatus, setAgentsStatus] = useState(() => {
    const saved = localStorage.getItem('agentsStatus')
    return saved ? JSON.parse(saved) : {}
  })
  const [agentsResults, setAgentsResults] = useState(() => {
    const saved = localStorage.getItem('agentsResults')
    return saved ? JSON.parse(saved) : {}
  })
  const [currentThoughts, setCurrentThoughts] = useState(() => {
    const saved = localStorage.getItem('currentThoughts')
    return saved ? JSON.parse(saved) : []
  })
  const [isDarkMode, setIsDarkMode] = useState(false)
  const [stats, setStats] = useState(() => {
    const saved = localStorage.getItem('stats')
    return saved ? JSON.parse(saved) : { signals: 0, confidence: 0, concepts: 0 }
  })
  const socketRef = useRef(null)
  
  // Sauvegarde automatique dans localStorage
  useEffect(() => {
    localStorage.setItem('agentsStatus', JSON.stringify(agentsStatus))
    localStorage.setItem('agentsResults', JSON.stringify(agentsResults))
    localStorage.setItem('currentThoughts', JSON.stringify(currentThoughts))
    localStorage.setItem('stats', JSON.stringify(stats))
    if (projectDesc) localStorage.setItem('lastProject', projectDesc)
  }, [agentsStatus, agentsResults, currentThoughts, stats, projectDesc])
  
  useEffect(() => {
    if (socketRef.current) return;

    const socket = new WebSocket('ws://localhost:8000/ws/agents');
    socketRef.current = socket;

    socket.onopen = () => console.log('✅ WebSocket connecté');

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'agent_update') {
        // Mise à jour de l'état de l'agent avec progression
        setAgentsStatus(prev => ({
          ...prev,
          [data.agent]: { 
            status: data.status, 
            progress: data.progress || (data.status === 'completed' ? 100 : 50),
            result: data.result 
          }
        }));

        // Sauvegarde du résultat complet
        if (data.result) {
          setAgentsResults(prev => ({
            ...prev,
            [data.agent]: data.result
          }));
        }

        // Mise à jour du flux de pensées
        if (data.thoughts && data.thoughts.length > 0) {
          setCurrentThoughts(prev => [...prev, {
            id: Date.now(),
            agent: data.agent,
            text: data.thoughts[data.thoughts.length - 1],
            timestamp: new Date()
          }]);
        }

        // Synchronisation des stats
        if (data.agent === 'trend_hunter' && data.result) {
          setStats(prev => ({ 
            ...prev, 
            signals: data.result.weak_signals?.length || 0,
            confidence: Math.round((data.result.score || 5) * 10) // Score 5.3 -> 53%
          }));
        }
        
        if (data.agent === 'creative_director' && data.result) {
          setStats(prev => ({ 
            ...prev, 
            concepts: data.result.ads?.length || 0 
          }));
        }
      }

      if (data.type === 'analysis_complete') {
        setIsRunning(false);
      }
    };

    socket.onerror = (err) => console.error("❌ Erreur Socket:", err);

    return () => {
      if (socket.readyState === 1) socket.close();
      socketRef.current = null;
    };
  }, []);
  
  const handleLaunchAnalysis = () => {
    if (!projectDesc.trim() || isRunning) return;

    // Réinitialiser les données pour la nouvelle analyse
    setIsRunning(true);
    setAgentsStatus({});
    setAgentsResults({});
    setCurrentThoughts([]);
    setStats({ signals: 0, confidence: 0, concepts: 0 });
    
    // Nettoyer localStorage pour la nouvelle analyse
    localStorage.removeItem('agentsStatus');
    localStorage.removeItem('agentsResults');
    localStorage.removeItem('currentThoughts');
    localStorage.removeItem('stats');

    socketRef.current.send(JSON.stringify({
      type: 'start_analysis',
      project: projectDesc
    }));
  };

// Dashboard.jsx - Vérifie que c'est bien ça
const handleAgentClick = (agentId) => {
  const agentData = agentsStatus[agentId];
  const agentResult = agentsResults[agentId];
  
  if (agentData?.status === 'completed' && agentResult) {
    const agentThoughts = agentResult.agent_thoughts || [];
    
    navigate(`/agent/${agentId}`, { 
      state: { 
        result: agentResult,
        thoughts: agentThoughts,  // ← ICI : c'est "thoughts", pas "agentThoughts"
        projectDesc
      } 
    });
  }
};
  
  const getAgentProgress = (agentId) => {
    const agent = agentsStatus[agentId]
    if (agent?.status === 'completed') return 100
    if (agent?.status === 'running') return agent.progress || 50
    return 0
  }
  
  const toggleTheme = () => {
    setIsDarkMode(!isDarkMode)
    if (!isDarkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }
  
  return (
    <div className="flex h-screen bg-white dark:bg-gray-950">
      {/* Sidebar - Navigation professionnelle */}
      <aside className="w-72 border-r border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900">
        <div className="p-6">
          {/* Logo */}
          <div className="flex items-center gap-3 mb-8">
            <div className="w-8 h-8 bg-gray-900 dark:bg-white rounded-lg flex items-center justify-center">
              <span className="text-white dark:text-gray-900 font-bold text-sm">S</span>
            </div>
            <div>
              <h1 className="text-base font-semibold tracking-tight">StartWise</h1>
              <p className="text-xs text-gray-500">Enterprise AI</p>
            </div>
          </div>
          
          {/* Navigation principale */}
          <nav className="space-y-1">
            <NavItem icon="📊" label="Tableau de bord" active />
            <NavItem icon="📈" label="Analyses" />
            <NavItem icon="⚙️" label="Paramètres" />
            <NavItem icon="📚" label="Documentation" />
            <NavItem icon="👥" label="Équipe" />
          </nav>
          
          {/* Section Historique avec le dernier projet */}
          {projectDesc && (
            <div className="mt-8">
              <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Dernière analyse</h3>
              <div className="px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800">
                <p className="text-sm font-medium truncate">{projectDesc}</p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {Object.keys(agentsResults).length} agents complétés
                </p>
              </div>
            </div>
          )}
        </div>
      </aside>
      
      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-white/80 dark:bg-gray-950/80 backdrop-blur-xl border-b border-gray-100 dark:border-gray-800">
          <div className="flex items-center justify-between px-8 py-4">
            <div>
              <h2 className="text-xl font-semibold">Tableau de bord</h2>
              <p className="text-sm text-gray-500 mt-0.5">Intelligence artificielle pour l'analyse marketing</p>
            </div>
            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              {isDarkMode ? '☀️' : '🌙'}
            </button>
          </div>
        </div>
        
        {/* Hero Section - Globe */}
        <div className="relative h-[480px] bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-950">
          <div className="absolute inset-0">
            <GlobeNetwork />
          </div>
          
          {/* Input Panel */}
          <div className="absolute bottom-0 left-0 right-0 p-8 bg-gradient-to-t from-white dark:from-gray-950 via-white/80 dark:via-gray-950/80 to-transparent">
            <div className="max-w-2xl mx-auto">
              <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-lg">
                <div className="p-4">
                  <textarea
                    value={projectDesc}
                    onChange={(e) => setProjectDesc(e.target.value)}
                    placeholder="Décrivez votre vision marketing..."
                    className="w-full bg-transparent border-0 focus:ring-0 text-sm resize-none h-24 placeholder:text-gray-400"
                    disabled={isRunning}
                  />
                  <div className="flex items-center justify-between mt-2 pt-3 border-t border-gray-100 dark:border-gray-800">
                    <span className="text-xs text-gray-400">
                      {projectDesc.length} caractères
                    </span>
                    <button
                      onClick={handleLaunchAnalysis}
                      disabled={isRunning || !projectDesc.trim()}
                      className={`
                        px-5 py-1.5 rounded-lg text-sm font-medium transition-all
                        ${isRunning || !projectDesc.trim()
                          ? 'bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed'
                          : 'bg-gray-900 dark:bg-white text-white dark:text-gray-900 hover:opacity-90'
                        }
                      `}
                    >
                      {isRunning ? 'Analyse en cours...' : 'Lancer l\'analyse'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        {/* Stats & Activity Section */}
        <div className="px-8 py-8">
          <div className="grid grid-cols-3 gap-6 mb-8">
            <StatCard label="Signaux marché" value={stats.signals} unit=" détectés" icon="📈" />
            <StatCard label="Confiance IA" value={stats.confidence} unit="%" icon="🎯" />
            <StatCard label="Concepts générés" value={stats.concepts} unit=" variants" icon="✨" />
          </div>
          
          <div className="grid grid-cols-3 gap-6">
            {/* Activity Feed */}
            <div className="col-span-1">
              <div className="bg-gray-50 dark:bg-gray-900/50 rounded-xl border border-gray-100 dark:border-gray-800 h-[400px] overflow-hidden">
                <div className="p-4 border-b border-gray-100 dark:border-gray-800">
                  <h3 className="text-sm font-medium">Activité en temps réel</h3>
                </div>
                <div className="h-[calc(100%-53px)] overflow-y-auto p-4">
                  <ActivityFeed activities={currentThoughts} />
                </div>
              </div>
            </div>
            
            {/* Agents Grid avec barre de progression */}
            <div className="col-span-2">
              <div className="grid grid-cols-2 gap-4">
                {AGENTS.map((agent) => (
                  <AgentCard
                    key={agent.id}
                    agentId={agent.id}
                    name={agent.name}
                    description={agent.description}
                    icon={agent.icon}
                    status={agentsStatus[agent.id]?.status || 'idle'}
                    progress={getAgentProgress(agent.id)}
                    onClick={() => handleAgentClick(agent.id)}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

// Composants auxiliaires
function NavItem({ icon, label, active }) {
  return (
    <button className={`
      w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors
      ${active 
        ? 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white' 
        : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800'
      }
    `}>
      <span className="text-base">{icon}</span>
      <span>{label}</span>
    </button>
  )
}

function StatCard({ label, value, unit, icon }) {
  return (
    <div className="bg-gray-50 dark:bg-gray-900/50 rounded-xl p-4 border border-gray-100 dark:border-gray-800">
      <div className="flex items-center justify-between mb-2">
        <span className="text-2xl">{icon}</span>
        <span className="text-2xl font-semibold">{value}{unit}</span>
      </div>
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  )
}