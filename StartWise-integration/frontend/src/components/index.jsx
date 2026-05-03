import { motion } from "framer-motion"

export function EmotionMatrix({ matrix }) {
  return (
    <div className="bg-[#0f0f1a] border border-[#1D9E75]/40 rounded-xl p-5">
      <div className="text-sm font-medium text-[#5DCAA5] mb-4">Matrice émotionnelle</div>
      <div className="flex gap-3">
        {matrix.map((item, i) => (
          <motion.div
            key={item.emotion}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className="flex-1 bg-[#0a0a0f] rounded-lg p-3 text-center"
          >
            <div className="text-xs text-[#6b6b9a] mb-1">{item.marketing_term}</div>
            <div className="text-xl font-medium text-[#c4b8ff]">{item.percentage}%</div>
            <div className="text-xs text-[#6b6b9a] mt-1 leading-tight">{item.tone?.split(",")[0]}</div>
            <div className="h-0.5 rounded-full mt-2" style={{ background: item.color }} />
          </motion.div>
        ))}
      </div>
    </div>
  )
}

export function SelfCorrectBar({ score }) {
  const pct = (score / 10) * 100
  const color = score >= 8 ? "#1D9E75" : score >= 6 ? "#BA7517" : "#D85A30"
  const label = score >= 8 ? "Analyse approuvée ✓" : "Corrections en cours..."

  return (
    <div className="bg-[#12121a] border border-[#534AB7]/40 rounded-xl px-5 py-4 flex items-center gap-4">
      <div className="flex-1">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-[#7F77DD] font-medium">Agent Self-Correction</span>
          <span className="text-xs" style={{ color }}>{label}</span>
        </div>
        <div className="h-1.5 bg-[#2a2a4a] rounded-full overflow-hidden">
          <motion.div
            className="h-full rounded-full"
            style={{ background: color }}
            initial={{ width: "0%" }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 1, ease: "easeOut" }}
          />
        </div>
      </div>
      <div className="text-2xl font-medium text-[#AFA9EC] shrink-0">
        {score.toFixed(1)}<span className="text-sm text-[#6b6b9a]">/10</span>
      </div>
    </div>
  )
}

export function CreativeResults({ ads }) {
  return (
    <div className="bg-[#0f0f1a] border border-[#2a2a4a] rounded-xl p-5">
      <div className="text-sm font-medium text-[#c4b8ff] mb-4">Maquettes générées · Stable Diffusion XL</div>
      <div className="grid grid-cols-3 gap-3">
        {ads.map((ad, i) => (
          <motion.div
            key={ad.variant}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.15 }}
            className="bg-[#0a0a0f] border border-[#2a2a4a] rounded-lg overflow-hidden"
          >
            {ad.image_base64 ? (
              <img
                src={`data:image/png;base64,${ad.image_base64}`}
                alt={ad.variant}
                className="w-full h-32 object-cover"
              />
            ) : (
              <div className="w-full h-32 flex items-center justify-center text-[#4a4a6a] text-xs">
                Image générée ici
              </div>
            )}
            <div className="p-3">
              <div className="text-xs font-medium text-[#c4b8ff] capitalize mb-1">
                {ad.variant.replace("_", " ")}
              </div>
              <div className="text-xs text-[#6b6b9a] leading-relaxed">
                {ad.copywriting_suggestion}
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

export default EmotionMatrix