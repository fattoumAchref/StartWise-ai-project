// src/components/ConfidenceGauge.jsx
import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'

export default function ConfidenceGauge({ value, label = "CONFIDENCE SCORE" }) {
  const [animatedValue, setAnimatedValue] = useState(0)
  
  useEffect(() => {
    const timer = setTimeout(() => {
      setAnimatedValue(value)
    }, 100)
    return () => clearTimeout(timer)
  }, [value])
  
  const percentage = animatedValue
  const angle = (percentage / 100) * 180
  const color = percentage >= 70 ? '#22c55e' : percentage >= 40 ? '#eab308' : '#ef4444'
  
  return (
    <div className="relative w-full">
      <div className="text-center mb-4">
        <div className="text-[10px] font-mono text-gray-400 tracking-wider">{label}</div>
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className="text-3xl font-bold mt-2"
          style={{ color }}
        >
          {Math.round(percentage)}<span className="text-lg">%</span>
        </motion.div>
      </div>
      
      {/* Gauge SVG */}
      <svg viewBox="0 0 200 100" className="w-full">
        {/* Background arc */}
        <path
          d="M 20,100 A 80,80 0 0 1 180,100"
          fill="none"
          stroke="rgba(255,255,255,0.1)"
          strokeWidth="12"
          strokeLinecap="round"
        />
        
        {/* Animated arc */}
        <motion.path
          initial={{ pathLength: 0 }}
          animate={{ pathLength: percentage / 100 }}
          transition={{ duration: 1, ease: "easeOut" }}
          d="M 20,100 A 80,80 0 0 1 180,100"
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
        />
        
        {/* Needle */}
        <motion.line
          initial={{ rotate: -90 }}
          animate={{ rotate: -90 + (percentage / 100) * 180 }}
          transition={{ duration: 1, ease: "easeOut" }}
          x1="100"
          y1="100"
          x2="100"
          y2="40"
          stroke={color}
          strokeWidth="2"
          strokeLinecap="round"
          transform="rotate(-90, 100, 100)"
        />
        
        {/* Center circle */}
        <circle cx="100" cy="100" r="4" fill={color} />
      </svg>
      
      {/* Value markers */}
      <div className="flex justify-between mt-2 text-[8px] text-gray-500 font-mono">
        <span>0%</span>
        <span>25%</span>
        <span>50%</span>
        <span>75%</span>
        <span>100%</span>
      </div>
    </div>
  )
}