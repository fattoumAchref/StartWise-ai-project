// src/components/KPICards.jsx
import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'

const KPICards = ({ analysisData }) => {
  const [stats, setStats] = useState({
    marketSignals: 0,
    confidence: 0,
    competitors: 0,
    concepts: 0
  })
  
  useEffect(() => {
    // Simulation de données dynamiques
    const interval = setInterval(() => {
      setStats({
        marketSignals: Math.floor(Math.random() * 50) + 10,
        confidence: Math.floor(Math.random() * 30) + 65,
        competitors: Math.floor(Math.random() * 20) + 5,
        concepts: Math.floor(Math.random() * 10) + 3
      })
    }, 2000)
    
    return () => clearInterval(interval)
  }, [])
  
  const cards = [
    { title: 'SIGNAUX MARCHÉ', value: stats.marketSignals, unit: 'signaux', icon: '📊', color: 'from-blue-500 to-cyan-500' },
    { title: 'CONFIANCE IA', value: stats.confidence, unit: '%', icon: '🎯', color: 'from-purple-500 to-pink-500' },
    { title: 'CONCURRENTS', value: stats.competitors, unit: 'identifiés', icon: '🏢', color: 'from-emerald-500 to-teal-500' },
    { title: 'CONCEPTS IA', value: stats.concepts, unit: 'générés', icon: '✨', color: 'from-orange-500 to-red-500' },
  ]
  
  return (
    <div className="grid grid-cols-2 gap-3">
      {cards.map((card, i) => (
        <motion.div
          key={card.title}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.1 }}
          className="glass rounded-xl p-4 card-hover"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-2xl">{card.icon}</span>
            <div className={`w-8 h-8 rounded-full bg-gradient-to-r ${card.color} opacity-20`} />
          </div>
          <p className="text-xs text-gray-500 uppercase tracking-wider">{card.title}</p>
          <p className="text-2xl font-bold mt-1">
            {card.value}<span className="text-sm font-normal text-gray-400">{card.unit}</span>
          </p>
        </motion.div>
      ))}
    </div>
  )
}

export default KPICards