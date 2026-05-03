"use client";
import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Scale, Send, Mic, MicOff, RotateCcw, Volume2, VolumeX,
  Building2, Award, Zap, Receipt, FileCode2, Search, Paperclip,
} from "lucide-react";
import { useProject } from "@/context/ProjectContext";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/legal";

function genId() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

interface Msg {
  role: "user" | "bot";
  content: string;
  sources?: string[];
  loading?: boolean;
}

const SUGGESTIONS = [
  { Icon: Building2, text: "Comment créer une SARL en Tunisie ?" },
  { Icon: Award,     text: "Comment déposer une marque à l'INNORPI ?" },
  { Icon: Zap,       text: "Avantages du Startup Act tunisien ?" },
  { Icon: Receipt,   text: "Taux de cotisation CNSS 2024 ?" },
  { Icon: FileCode2, text: "Licence MIT vs GPL pour un SaaS ?" },
  { Icon: Search,    text: "Capital minimum pour créer une SUARL ?" },
];

function formatContent(text: string) {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/---\n*/g, '<hr style="border:none;border-top:1px solid rgba(0,0,0,0.1);margin:12px 0"/>')
    .replace(/\n/g, "<br/>");
}

// ── Avatar ────────────────────────────────────────────────────────────────────
function LexAvatar({ isSpeaking, size = 72 }: { isSpeaking: boolean; size?: number }) {
  const [open, setOpen] = useState(false);
  const [blink, setBlink] = useState(false);

  useEffect(() => {
    if (!isSpeaking) { setOpen(false); return; }
    const t = setInterval(() => setOpen(o => !o), 200);
    return () => clearInterval(t);
  }, [isSpeaking]);

  useEffect(() => {
    let tid: ReturnType<typeof setTimeout>;
    const loop = () => {
      tid = setTimeout(() => {
        setBlink(true);
        setTimeout(() => { setBlink(false); loop(); }, 120);
      }, 3000 + Math.random() * 1800);
    };
    loop();
    return () => clearTimeout(tid);
  }, []);

  return (
    <div style={{ animation: "lexSway 4s ease-in-out infinite", transformOrigin: "bottom center" }}>
      <svg width={size} height={size * 155 / 104} viewBox="0 0 104 155" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M 6 155 L 12 112 L 28 96 L 52 104 L 76 96 L 92 112 L 98 155 Z" fill="#1e3560"/>
        <path d="M 12 112 L 28 96 L 40 102 L 30 155 L 6 155 Z" fill="#162848"/>
        <path d="M 92 112 L 76 96 L 64 102 L 74 155 L 98 155 Z" fill="#162848"/>
        <rect x="44" y="102" width="16" height="34" fill="#eef2ff"/>
        <path d="M 28 96 L 42 103 L 44 96 Z" fill="#1a3050"/>
        <path d="M 76 96 L 62 103 L 60 96 Z" fill="#1a3050"/>
        <polygon points="52,103 56,103 58,124 52,132 46,124 48,103" fill="#8b1a1a"/>
        <ellipse cx="52" cy="103" rx="4.5" ry="3" fill="#a52020"/>
        <rect x="2" y="108" width="13" height="38" rx="6.5" fill="#1e3560"/>
        <rect x="89" y="108" width="13" height="38" rx="6.5" fill="#1e3560"/>
        <rect x="2" y="138" width="13" height="9" rx="4" fill="#eef2ff"/>
        <rect x="89" y="138" width="13" height="9" rx="4" fill="#eef2ff"/>
        <rect x="44" y="83" width="16" height="17" rx="6" fill="#c8844a"/>
        <ellipse cx="52" cy="52" rx="30" ry="34" fill="#d4904c"/>
        <path d="M 24 52 Q 20 38 24 26 Q 34 14 52 12 Q 70 14 80 26 Q 84 38 80 52 Q 76 36 52 32 Q 28 36 24 52 Z" fill="#2a1a0c"/>
        <path d="M 24 52 Q 20 60 20 70 Q 22 76 28 74 Q 24 66 24 54 Z" fill="#2a1a0c"/>
        <path d="M 80 52 Q 84 60 84 70 Q 82 76 76 74 Q 80 66 80 54 Z" fill="#2a1a0c"/>
        <path d="M 28 40 Q 36 30 52 28 Q 68 30 76 40 Q 66 32 52 31 Q 38 32 28 40 Z" fill="#d4904c"/>
        <ellipse cx="52" cy="56" rx="5.5" ry="7" fill="#d4904c"/>
        <ellipse cx="82" cy="56" rx="5.5" ry="7" fill="#d4904c"/>
        <ellipse cx="22" cy="56" rx="3" ry="4" fill="#bb7030"/>
        <ellipse cx="82" cy="56" rx="3" ry="4" fill="#bb7030"/>
        <path d="M 30 42 Q 39 37 46 41" stroke="#3a2010" strokeWidth="3.2" strokeLinecap="round"/>
        <path d="M 58 41 Q 65 37 74 42" stroke="#3a2010" strokeWidth="3.2" strokeLinecap="round"/>
        <ellipse cx="38" cy="52" rx="7" ry={blink ? 1.2 : 8} fill="white"/>
        <ellipse cx="66" cy="52" rx="7" ry={blink ? 1.2 : 8} fill="white"/>
        {!blink && <>
          <circle cx="38" cy="53" r="4.5" fill="#1e2a3a"/>
          <circle cx="66" cy="53" r="4.5" fill="#1e2a3a"/>
          <circle cx="39.5" cy="51" r="1.6" fill="white"/>
          <circle cx="67.5" cy="51" r="1.6" fill="white"/>
        </>}
        <path d="M 31 45 Q 38 41 45 45" stroke="#3a2010" strokeWidth="1.8" fill="none" strokeLinecap="round"/>
        <path d="M 59 45 Q 66 41 73 45" stroke="#3a2010" strokeWidth="1.8" fill="none" strokeLinecap="round"/>
        <ellipse cx="52" cy="65" rx="4" ry="5" fill="#c07840" opacity=".35"/>
        <path d="M 49 68 Q 52 71 55 68" stroke="#b06828" strokeWidth="1.6" fill="none" strokeLinecap="round"/>
        {open ? <>
          <path d="M 41 76 Q 52 85 63 76" fill="#4a0e0e"/>
          <path d="M 41 76 Q 52 80 63 76 L 63 78 Q 52 82 41 78 Z" fill="#f0ece4" opacity=".88"/>
          <path d="M 41 76 Q 52 73 63 76" stroke="#8b3020" strokeWidth="2" fill="none" strokeLinecap="round"/>
        </> : <>
          <path d="M 42 76 Q 52 81 62 76" stroke="#8b3020" strokeWidth="2.2" fill="none" strokeLinecap="round"/>
        </>}
        {isSpeaking && (
          <circle cx="86" cy="18" r="4.5" fill="#10b981">
            <animate attributeName="r" values="4.5;6.5;4.5" dur="0.65s" repeatCount="indefinite"/>
            <animate attributeName="opacity" values="1;.3;1" dur="0.65s" repeatCount="indefinite"/>
          </circle>
        )}
      </svg>
      <style>{`@keyframes lexSway { 0%,100%{transform:rotate(-1deg)} 50%{transform:rotate(1deg) translateY(-3px)} }`}</style>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function LexWisePage() {
  const [msgs, setMsgs]             = useState<Msg[]>([]);
  const [input, setInput]           = useState("");
  const [busy, setBusy]             = useState(false);
  const [sessionId]                 = useState("sess_" + genId());
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [muted, setMuted]           = useState(false);
  const [listening, setListening]   = useState(false);
  const [micSupported, setMicSupported] = useState(false);
  const bottomRef    = useRef<HTMLDivElement>(null);
  const inputRef     = useRef<HTMLTextAreaElement>(null);
  const recogRef     = useRef<any>(null);
  const sendRef      = useRef<(t: string) => void>(() => {});
  const voiceRef     = useRef<SpeechSynthesisVoice | null>(null);
  const resumeTimer  = useRef<ReturnType<typeof setInterval> | null>(null);
  const mutedRef     = useRef(false);
  const speakImplRef = useRef<(text: string) => void>(() => {});
  const { ideation } = useProject();
  const ideationRef = useRef<string>("");

  useEffect(() => {
    const summary =
      ideation?.summary ||
      localStorage.getItem("startwise_summary") ||
      localStorage.getItem("sw_ideation_summary") ||
      "";
    const businessIdea =
      ideation?.businessIdea ||
      localStorage.getItem("startwise_business_idea") ||
      localStorage.getItem("sw_ideation_business_idea") ||
      "";
    ideationRef.current = summary || businessIdea;
  }, [ideation]);

  useEffect(() => {
    setMicSupported(!!(window.SpeechRecognition || (window as any).webkitSpeechRecognition));
    const pick = () => {
      const all = window.speechSynthesis.getVoices();
      const fr  = all.filter(v => v.lang.startsWith("fr"));
      voiceRef.current = fr[0] ?? all[0] ?? null;
    };
    if (window.speechSynthesis.getVoices().length) pick();
    window.speechSynthesis.onvoiceschanged = pick;
    return () => {
      if (resumeTimer.current) clearInterval(resumeTimer.current);
      window.speechSynthesis.cancel();
    };
  }, []);

  useEffect(() => { mutedRef.current = muted; }, [muted]);

  // Always-fresh speak implementation via ref — no stale closure, works after async await
  useEffect(() => {
    speakImplRef.current = (text: string) => {
      if (mutedRef.current || !window?.speechSynthesis) return;
      window.speechSynthesis.cancel();
      if (resumeTimer.current) { clearInterval(resumeTimer.current); resumeTimer.current = null; }
      const clean = text
        .replace(/<[^>]+>/g, " ")
        .replace(/\*\*/g, "")
        .replace(/#{1,6}\s/g, "")
        .replace(/\s+/g, " ")
        .trim();
      if (!clean) return;
      const allVoices = window.speechSynthesis.getVoices();
      const frVoices  = allVoices.filter(v => v.lang.startsWith("fr"));
      const MALE   = ["thomas","paul","guillaume","nicolas","pierre","jean","claude","microsoft paul","microsoft guillaume"];
      const FEMALE = ["hortense","amelie","marie","audrey","zira","eva","julie","microsoft hortense"];
      const frVoice =
        frVoices.find(v => MALE.some(n => v.name.toLowerCase().includes(n))) ??
        frVoices.find(v => !FEMALE.some(n => v.name.toLowerCase().includes(n))) ??
        frVoices[0] ??
        allVoices[0] ??
        null;
      if (frVoice) voiceRef.current = frVoice;
      const utt = new SpeechSynthesisUtterance(clean);
      if (voiceRef.current) { utt.voice = voiceRef.current; utt.lang = voiceRef.current.lang; }
      utt.rate = 0.9; utt.pitch = 1.0; utt.volume = 1.0;
      utt.onstart = () => {
        setIsSpeaking(true);
        resumeTimer.current = setInterval(() => {
          if (window.speechSynthesis.speaking) {
            window.speechSynthesis.pause();
            window.speechSynthesis.resume();
          }
        }, 10000);
      };
      utt.onend = () => {
        if (resumeTimer.current) { clearInterval(resumeTimer.current); resumeTimer.current = null; }
        setIsSpeaking(false);
      };
      utt.onerror = (e) => {
        const err = (e as any).error;
        if (err !== "interrupted" && err !== "canceled") console.error("TTS error:", err);
        if (resumeTimer.current) { clearInterval(resumeTimer.current); resumeTimer.current = null; }
        setIsSpeaking(false);
      };
      window.speechSynthesis.speak(utt);
    };
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);

  const stopSpeak = useCallback(() => {
    if (resumeTimer.current) { clearInterval(resumeTimer.current); resumeTimer.current = null; }
    if (typeof window !== "undefined") window.speechSynthesis?.cancel();
    setIsSpeaking(false);
  }, []);

  const speak = useCallback((text: string) => { speakImplRef.current(text); }, []);

  const send = useCallback(async (q?: string) => {
    const text = (q ?? input).trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setMsgs(p => [...p, { role: "user", content: text }, { role: "bot", content: "", loading: true }]);
    try {
      const res  = await fetch(`${API}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text, session_id: sessionId, startup_context: ideationRef.current }),
      });
      const data = await res.json();
      const answer = data.answer || data.detail || "Aucune réponse.";
      setMsgs(p => {
        const n = [...p];
        n[n.length - 1] = { role: "bot", content: answer, sources: data.sources || [] };
        return n;
      });
      speak(answer);
    } catch {
      setMsgs(p => {
        const n = [...p];
        n[n.length - 1] = { role: "bot", content: "Backend LexWise inaccessible. Vérifiez que le serveur Django tourne sur le port 8000." };
        return n;
      });
    } finally {
      setBusy(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [input, busy, sessionId, speak]);

  useEffect(() => { sendRef.current = (t: string) => send(t); }, [send]);

  const toggleMic = useCallback(() => {
    if (listening) { recogRef.current?.stop(); setListening(false); return; }
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;
    stopSpeak();
    const rec = new SR();
    rec.lang = "fr-FR"; rec.continuous = true; rec.interimResults = true;
    rec.onstart  = () => setListening(true);
    rec.onend    = () => setListening(false);
    rec.onerror  = () => setListening(false);
    rec.onresult = (e: any) => {
      let final = ""; let live = "";
      for (let i = 0; i < e.results.length; i++) {
        e.results[i].isFinal ? (final += e.results[i][0].transcript) : (live += e.results[i][0].transcript);
      }
      if (live)  setInput(live);
      if (final.trim()) { setInput(""); rec.stop(); sendRef.current(final.trim()); }
    };
    recogRef.current = rec;
    rec.start();
  }, [listening, stopSpeak]);

  const clearSession = async () => {
    await fetch(`${API}/session/clear`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    }).catch(() => {});
    setMsgs([]);
    stopSpeak();
  };

  const started = msgs.length > 0;

  return (
    <div className="flex h-[calc(100vh-64px)] overflow-hidden bg-background">

      {/* ── Avatar panel ─────────────────────────────────────────────────────── */}
      <div className="flex-shrink-0 w-40 flex flex-col items-center pt-8 pb-4 gap-4 border-r border-border/60 bg-gradient-to-b from-slate-50/80 to-blue-50/40 dark:from-slate-900/60 dark:to-blue-950/20">
        <LexAvatar isSpeaking={isSpeaking} size={92} />

        {/* Name badge */}
        <div className="flex flex-col items-center gap-0.5">
          <span className="text-[11px] font-bold text-foreground tracking-wide">LexWise</span>
          <span className="text-[9px] text-muted-foreground uppercase tracking-widest">Conseiller juridique</span>
        </div>

        {/* Status dot */}
        <div className="flex items-center gap-1.5">
          <motion.div
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
            className={`w-1.5 h-1.5 rounded-full ${isSpeaking ? "bg-blue-500" : "bg-emerald-500"}`}
          />
          <span className="text-[9px] text-muted-foreground">{isSpeaking ? "Parle…" : "En ligne"}</span>
        </div>

        <div className="w-full px-3 flex flex-col gap-2 mt-1">
          {/* Mute toggle */}
          <button
            onClick={() => { setMuted(m => { if (!m) stopSpeak(); return !m; }); }}
            className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[11px] font-medium border transition-all"
            style={{
              background: muted ? "#f8fafc" : "#eff6ff",
              borderColor: muted ? "#e2e8f0" : "#bfdbfe",
              color: muted ? "#94a3b8" : "#2563eb",
            }}
          >
            {muted
              ? <><VolumeX className="h-3 w-3" /> Muet</>
              : <><Volume2 className="h-3 w-3" /> Voix</>
            }
          </button>

          {/* Reset session */}
          <button
            onClick={clearSession}
            className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[11px] font-medium border border-border text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-all"
          >
            <RotateCcw className="h-3 w-3" /> Réinitialiser
          </button>
        </div>

      </div>

      {/* ── Chat panel ───────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Header */}
        <div className="flex-shrink-0 flex items-center gap-3 px-6 py-3 border-b border-border/60 bg-background/90 backdrop-blur-sm">
          <div
            className="flex items-center justify-center w-8 h-8 rounded-lg"
            style={{ background: "linear-gradient(135deg,#1e3560,#2563eb)" }}
          >
            <Scale className="h-4 w-4 text-white" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-foreground tracking-tight">LexWise</h2>
            <p className="text-[11px] text-muted-foreground">Conseiller juridique IA · Droit tunisien des affaires</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <motion.div
              animate={{ scale: [1, 1.35, 1], opacity: [1, 0.4, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="w-1.5 h-1.5 rounded-full bg-emerald-500"
            />
            <span className="text-[11px] text-muted-foreground">En ligne</span>
          </div>
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <div className="max-w-2xl mx-auto flex flex-col gap-4">

            {/* Welcome screen */}
            <AnimatePresence>
              {!started && (
                <motion.div
                  key="welcome"
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12, transition: { duration: .15 } }}
                  className="py-8"
                >
                  {/* Logo */}
                  <div className="flex flex-col items-center mb-6">
                    <motion.div
                      animate={{ y: [0, -5, 0] }}
                      transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                      className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4"
                      style={{ background: "linear-gradient(135deg,#1e3560,#2563eb)", boxShadow: "0 8px 24px rgba(30,53,96,.2)" }}
                    >
                      <Scale className="h-7 w-7 text-white" />
                    </motion.div>
                    <h3 className="text-xl font-bold text-foreground tracking-tight">Conseiller juridique IA</h3>
                    <p className="text-sm text-muted-foreground mt-1">Droit tunisien des affaires · Startups · IP</p>
                  </div>

                  <p className="text-sm text-muted-foreground mb-6 leading-relaxed text-center">
                    JORT · DGI · CNSS · INNORPI · Startup Act · 1 093 startups tunisiennes
                  </p>

                  {/* Suggestions */}
                  <div className="grid grid-cols-2 gap-2">
                    {SUGGESTIONS.map(({ Icon, text }, i) => (
                      <motion.button
                        key={i}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: .05 + i * .06, duration: .22 }}
                        whileHover={{ scale: 1.02, y: -1 }}
                        whileTap={{ scale: .97 }}
                        onClick={() => send(text)}
                        className="flex items-start gap-2.5 p-3 rounded-xl border border-border bg-background hover:border-blue-200 hover:bg-blue-50/40 dark:hover:bg-blue-950/20 dark:hover:border-blue-800/60 transition-all text-left"
                      >
                        <div className="mt-0.5 flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center"
                          style={{ background: "linear-gradient(135deg,#1e356010,#2563eb15)" }}>
                          <Icon className="h-3 w-3 text-blue-600 dark:text-blue-400" />
                        </div>
                        <span className="text-[12px] text-muted-foreground leading-snug">{text}</span>
                      </motion.button>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Message list */}
            <AnimatePresence initial={false}>
              {msgs.map((m, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 10, scale: .98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ duration: .2, ease: "easeOut" }}
                  className={`flex ${m.role === "user" ? "justify-end" : "justify-start"} items-end gap-2`}
                >
                  {m.role === "bot" && (
                    <div
                      className="w-7 h-7 rounded-lg flex-shrink-0 flex items-center justify-center"
                      style={{ background: "linear-gradient(135deg,#1e3560,#2563eb)" }}
                    >
                      <Scale className="h-3.5 w-3.5 text-white" />
                    </div>
                  )}
                  <div className="max-w-lg">
                    <div
                      className={`px-4 py-2.5 text-sm leading-relaxed ${
                        m.role === "user"
                          ? "rounded-[16px_16px_4px_16px] text-white"
                          : "rounded-[4px_16px_16px_16px] bg-background border border-border text-foreground"
                      }`}
                      style={m.role === "user"
                        ? { background: "linear-gradient(135deg,#1e3560,#2563eb)", boxShadow: "0 4px 14px rgba(30,53,96,.25)" }
                        : {}
                      }
                    >
                      {m.loading ? (
                        <div className="flex gap-1 items-center py-1">
                          {[0, 1, 2].map(j => (
                            <div
                              key={j}
                              className="w-1.5 h-1.5 rounded-full bg-blue-300"
                              style={{ animation: `lexBounce 1.2s ease-in-out ${j * .18}s infinite` }}
                            />
                          ))}
                        </div>
                      ) : (
                        <div dangerouslySetInnerHTML={{ __html: formatContent(m.content) }} />
                      )}
                    </div>

                    {/* Source chips */}
                    {m.sources && m.sources.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {m.sources.slice(0, 3).map((s, si) => (
                          <span
                            key={si}
                            className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400"
                          >
                            <Paperclip className="h-2.5 w-2.5" />
                            {s.slice(0, 38)}{s.length > 38 ? "…" : ""}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
            <div ref={bottomRef} />
          </div>
        </div>

        {/* Input bar */}
        <div className="flex-shrink-0 px-6 py-4 border-t border-border/60 bg-background/90 backdrop-blur-sm">
          <div
            className="max-w-2xl mx-auto flex gap-2 items-end p-3 rounded-2xl border border-border bg-background transition-shadow focus-within:shadow-[0_0_0_2px_rgba(37,99,235,.15)] focus-within:border-blue-200 dark:focus-within:border-blue-800"
            style={{ boxShadow: "0 2px 12px rgba(0,0,0,.04)" }}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
              placeholder={listening ? "Parlez…" : "Posez votre question juridique… (Entrée pour envoyer)"}
              rows={1}
              className="flex-1 bg-transparent border-none outline-none resize-none text-sm text-foreground placeholder:text-muted-foreground leading-relaxed max-h-28 overflow-y-auto"
              onInput={e => {
                const t = e.currentTarget;
                t.style.height = "auto";
                t.style.height = Math.min(t.scrollHeight, 112) + "px";
              }}
            />
            {micSupported && (
              <motion.button
                whileHover={{ scale: 1.08 }} whileTap={{ scale: .92 }}
                onClick={toggleMic}
                className="w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center transition-all"
                style={{
                  background: listening ? "linear-gradient(135deg,#dc2626,#b91c1c)" : "#f1f5f9",
                  color: listening ? "#fff" : "#64748b",
                  boxShadow: listening ? "0 0 0 3px rgba(220,38,38,.18)" : "none",
                }}
              >
                {listening ? <MicOff className="h-3.5 w-3.5" /> : <Mic className="h-3.5 w-3.5" />}
              </motion.button>
            )}
            <motion.button
              whileHover={{ scale: 1.08 }} whileTap={{ scale: .92 }}
              onClick={() => send()}
              disabled={busy || !input.trim()}
              className="w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center transition-all"
              style={{
                background: busy || !input.trim() ? "#f1f5f9" : "linear-gradient(135deg,#1e3560,#2563eb)",
                color: busy || !input.trim() ? "#94a3b8" : "#fff",
                boxShadow: busy || !input.trim() ? "none" : "0 2px 10px rgba(30,53,96,.3)",
              }}
            >
              {busy
                ? <div className="w-3 h-3 rounded-full border-2 border-blue-200 border-t-blue-500" style={{ animation: "spin .7s linear infinite" }} />
                : <Send className="h-3.5 w-3.5" />
              }
            </motion.button>
          </div>
          <p className="text-center text-[10px] text-muted-foreground/60 mt-2">
            Sources : JORT · DGI · CNSS · INNORPI · SPDX · 1 093 startups tunisiennes
          </p>
        </div>
      </div>

      <style>{`
        @keyframes lexBounce { 0%,80%,100%{transform:translateY(0);opacity:.35} 40%{transform:translateY(-6px);opacity:1} }
        @keyframes spin { to{transform:rotate(360deg)} }
      `}</style>
    </div>
  );
}
