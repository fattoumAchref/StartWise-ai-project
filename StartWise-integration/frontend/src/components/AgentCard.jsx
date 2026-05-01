// src/components/AgentCard.jsx
import { motion } from 'framer-motion'

export default function AgentCard({ agentId, name, description, icon, status, progress = 0, onClick }) {
  const statusConfig = {
    idle: { text: 'Prêt', color: 'text-gray-400', bg: 'bg-gray-100 dark:bg-gray-800' },
    running: { text: 'Analyse en cours', color: 'text-blue-500', bg: 'bg-blue-50 dark:bg-blue-950/20' },
    completed: { text: 'Terminé', color: 'text-emerald-500', bg: 'bg-emerald-50 dark:bg-emerald-950/20' }
  }
  
  const currentStatus = statusConfig[status] || statusConfig.idle
  
  return (
    <motion.button
      whileHover={{ y: -2 }}
      onClick={onClick}
      className={`
        w-full text-left p-5 rounded-xl border transition-all
        ${status === 'completed' 
          ? 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600' 
          : 'border-gray-100 dark:border-gray-800 hover:border-gray-200 dark:hover:border-gray-700'
        }
        bg-white dark:bg-gray-900
      `}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="w-10 h-10 bg-gray-100 dark:bg-gray-800 rounded-lg flex items-center justify-center text-xl">
          {icon}
        </div>
        <div className={`px-2 py-0.5 rounded-full text-xs ${currentStatus.color} ${currentStatus.bg}`}>
          {currentStatus.text}
        </div>
      </div>
      
      <h3 className="text-base font-semibold mb-1">{name}</h3>
      <p className="text-sm text-gray-500 mb-3">{description}</p>
      
      {/* Barre de progression */}
      {status === 'running' && (
        <div className="mt-2">
          <div className="h-1 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-blue-500 rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
          <p className="text-xs text-gray-400 mt-1">{Math.round(progress)}%</p>
        </div>
      )}
      
      {status === 'completed' && (
        <div className="mt-2">
          <div className="h-1 bg-emerald-200 dark:bg-emerald-900/50 rounded-full overflow-hidden">
            <div className="h-full w-full bg-emerald-500 rounded-full" />
          </div>
          <p className="text-xs text-emerald-500 mt-1">Analyse complétée</p>
        </div>
      )}
    </motion.button>
  )
}