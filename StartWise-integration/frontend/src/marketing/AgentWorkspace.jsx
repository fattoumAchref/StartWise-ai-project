// src/pages/AgentWorkspace.jsx
import { motion, AnimatePresence } from 'framer-motion'
import { useState } from 'react'
import ThoughtStream from '../components/ThoughtStream'
import ConfidenceGauge from '../components/ConfidenceGauge'

const AGENT_CONFIG = {
  trend_hunter: {
    name: 'TREND HUNTER',
    icon: '📡',
    subtitle: 'MARKET INTELLIGENCE UNIT',
    color: 'from-purple-500 to-pink-500',
    tech: 'Mistral Large 2 + FAISS Vector DB',
    metrics: ['Market Signals', 'Competitor Analysis', 'Risk Assessment']
  },
  visual_semiotics: {
    name: 'VISUAL SEMIOTICS',
    icon: '👁️',
    subtitle: 'BRAND IDENTITY ANALYZER',
    color: 'from-emerald-500 to-teal-500',
    tech: 'Pixtral Large + CLIP Embeddings',
    metrics: ['Archetype Detection', 'Color Psychology', 'Attention Heatmap']
  },
  emotional_intelligence: {
    name: 'EMOTIONAL INTELLIGENCE',
    icon: '🧠',
    subtitle: 'COGNITIVE PATTERN ANALYZER',
    color: 'from-amber-500 to-orange-500',
    tech: 'DeepSeek + GoEmotions Model',
    metrics: ['Emotional Triggers', 'User Journey', 'Brand Resonance']
  },
  creative_director: {
    name: 'CREATIVE DIRECTOR',
    icon: '✨',
    subtitle: 'GENERATIVE DESIGN UNIT',
    color: 'from-indigo-500 to-purple-500',
    tech: 'Stable Diffusion XL + Flux.1',
    metrics: ['Concept Generation', 'Visual Prototypes', 'Campaign Strategy']
  }
}

export default function AgentWorkspace({ agentId, data, thoughts, onClose }) {
  const [activeTab, setActiveTab] = useState('reasoning')
  const config = AGENT_CONFIG[agentId]
  const confidenceScore = data?.confidence_score || 85
  
  const formattedThoughts = thoughts?.map(text => ({ text })) || []
  
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="fixed inset-4 z-50 bg-dark-bg/95 backdrop-blur-xl rounded-2xl border border-dark-border shadow-2xl overflow-hidden"
    >
      {/* Header with gradient */}
      <div className={`relative bg-gradient-to-r ${config.color} p-6`}>
        <div className="absolute inset-0 bg-black/50" />
        <div className="relative z-10 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/10 rounded-lg transition-all"
            >
              ← Retour au Dashboard
            </button>
            <div className="text-3xl">{config.icon}</div>
            <div>
              <h2 className="text-xl font-bold tracking-wider">{config.name}</h2>
              <p className="text-xs text-white/60 font-mono">{config.subtitle}</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] font-mono text-white/40">TECH STACK</div>
            <div className="text-xs font-mono">{config.tech}</div>
          </div>
        </div>
      </div>
      
      {/* Tabs */}
      <div className="border-b border-dark-border px-6">
        <div className="flex gap-6">
          {['reasoning', 'metrics', 'results'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`
                py-3 text-sm font-mono transition-all relative
                ${activeTab === tab ? 'text-primary-400' : 'text-gray-500 hover:text-gray-300'}
              `}
            >
              {tab.toUpperCase()}
              {activeTab === tab && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary-500"
                />
              )}
            </button>
          ))}
        </div>
      </div>
      
      {/* Content */}
      <div className="flex-1 flex overflow-hidden p-6 gap-6">
        <AnimatePresence mode="wait">
          {activeTab === 'reasoning' && (
            <motion.div
              key="reasoning"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="flex-1"
            >
              <ThoughtStream thoughts={formattedThoughts} isStreaming={false} />
            </motion.div>
          )}
          
          {activeTab === 'metrics' && (
            <motion.div
              key="metrics"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="flex-1 grid grid-cols-2 gap-6"
            >
              <div className="glass rounded-xl p-6">
                <ConfidenceGauge value={confidenceScore} />
              </div>
              <div className="glass rounded-xl p-6">
                <h3 className="text-xs font-mono text-gray-400 mb-4">KEY METRICS</h3>
                <div className="space-y-3">
                  {config.metrics.map((metric, i) => (
                    <div key={i} className="flex justify-between items-center">
                      <span className="text-sm">{metric}</span>
                      <div className="w-24 h-1 bg-dark-border rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary-500 rounded-full"
                          style={{ width: `${Math.random() * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}
          
          {activeTab === 'results' && (
            <motion.div
              key="results"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="flex-1 overflow-y-auto"
            >
              {data ? (
                <pre className="glass rounded-xl p-6 text-xs font-mono overflow-auto">
                  {JSON.stringify(data, null, 2)}
                </pre>
              ) : (
                <div className="text-center text-gray-500 py-12">
                  Aucun résultat disponible pour le moment
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}