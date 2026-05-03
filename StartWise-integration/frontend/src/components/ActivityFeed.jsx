// src/components/ActivityFeed.jsx
import { motion, AnimatePresence } from 'framer-motion'

export default function ActivityFeed({ activities }) {
  // Fonction pour formater la date en toute sécurité
  const formatTime = (timestamp) => {
    if (!timestamp) return '--:--:--'
    try {
      // Si c'est déjà un objet Date
      if (timestamp instanceof Date) {
        return timestamp.toLocaleTimeString()
      }
      // Si c'est une string, on tente de la convertir
      if (typeof timestamp === 'string') {
        const date = new Date(timestamp)
        if (!isNaN(date.getTime())) {
          return date.toLocaleTimeString()
        }
      }
      // Si c'est un objet avec une propriété toLocaleTimeString
      if (timestamp && typeof timestamp === 'object' && timestamp.toLocaleTimeString) {
        return timestamp.toLocaleTimeString()
      }
      return new Date().toLocaleTimeString()
    } catch (e) {
      return new Date().toLocaleTimeString()
    }
  }

  return (
    <div className="space-y-3">
      <AnimatePresence>
        {activities.slice().reverse().map((activity, idx) => (
          <motion.div
            key={`${activity.id}-${idx}`}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex gap-3"
          >
            <div className="w-1.5 h-1.5 rounded-full bg-gray-400 mt-2" />
            <div className="flex-1">
              <p className="text-xs text-gray-500 font-mono">
                {formatTime(activity.timestamp)}
              </p>
              <p className="text-sm mt-0.5 text-gray-700 dark:text-gray-300">
                {activity.text}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                {activity.agent?.replace('_', ' ').toUpperCase()}
              </p>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
      
      {activities.length === 0 && (
        <div className="text-center py-8">
          <p className="text-sm text-gray-400">Aucune activité</p>
          <p className="text-xs text-gray-400 mt-1">Lancez une analyse pour voir les résultats</p>
        </div>
      )}
    </div>
  )
}