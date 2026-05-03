// src/components/ThoughtStream.jsx
import { motion, AnimatePresence } from 'framer-motion'
import { useEffect, useRef } from 'react'

export default function ThoughtStream({ thoughts, isStreaming }) {
  const containerRef = useRef(null)
  
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [thoughts])
  
  const getThoughtIcon = (text) => {
    if (text.includes('DECISION') || text.includes('✅')) return '🎯'
    if (text.includes('SEARCH') || text.includes('🔍')) return '🔍'
    if (text.includes('CRITIQUE') || text.includes('❌')) return '⚠️'
    if (text.includes('ANALYSE')) return '🧠'
    if (text.includes('GÉNÉRATION')) return '✨'
    return '💭'
  }
  
  const getThoughtClass = (text) => {
    if (text.includes('DECISION') || text.includes('✅')) return 'text-green-400 border-l-green-400'
    if (text.includes('SEARCH') || text.includes('🔍')) return 'text-blue-400 border-l-blue-400'
    if (text.includes('CRITIQUE') || text.includes('❌')) return 'text-red-400 border-l-red-400'
    if (text.includes('ANALYSE')) return 'text-purple-400 border-l-purple-400'
    return 'text-gray-300 border-l-gray-500'
  }
  
  return (
    <div className="h-full flex flex-col bg-black/20 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-dark-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
          <span className="text-xs font-mono text-gray-400 tracking-wider">
            INTERNAL REASONING / CHAIN-OF-THOUGHT
          </span>
        </div>
        {isStreaming && (
          <div className="flex gap-1">
            <div className="w-1 h-1 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '0s' }} />
            <div className="w-1 h-1 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
            <div className="w-1 h-1 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }} />
          </div>
        )}
      </div>
      
      <div ref={containerRef} className="flex-1 overflow-y-auto p-4 space-y-3 font-mono text-xs">
        <AnimatePresence>
          {thoughts.map((thought, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.05 }}
              className={`flex gap-3 border-l-2 pl-3 ${getThoughtClass(thought.text)}`}
            >
              <div className="text-gray-500 select-none">
                {getThoughtIcon(thought.text)}
              </div>
              <div className="flex-1">
                <div className="text-gray-400 text-[10px] mb-1">
                  [{new Date().toLocaleTimeString()}]
                </div>
                <div className="leading-relaxed">
                  {thought.text}
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        
        {isStreaming && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex gap-2 items-center text-gray-500"
          >
            <span className="animate-blink">▊</span>
            <span className="text-[10px]">Agent en cours de réflexion...</span>
          </motion.div>
        )}
      </div>
    </div>
  )
}