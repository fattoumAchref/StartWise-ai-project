# backend/consumers.py
import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from .graph import compiled_graph, AgentState
from .inference import prompt_guard

class AgentConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        print("WEB_SOCKET CONNECTÉ AU BACKEND")
        self.analysis_task = None
        
    async def disconnect(self, close_code):
        print(f"WEB_SOCKET DÉCONNECTÉ")
        if self.analysis_task and not self.analysis_task.done():
            self.analysis_task.cancel()
            
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data.get("type") == "start_analysis":
                project_desc = data.get("project", "")
                deep_scan = bool(data.get("deep_scan", False))
                creativity = int(data.get("creativity", 50))
                lang = data.get("lang", "fr")
                model = data.get("model", "llama-70b")
                document_text = str(data.get("document_text", ""))[:8000]  # sécurité taille

                # ── Prompt Guard — sécurisation avant exécution ──────
                print(f"[PROMPT GUARD] 🛡️  Analyse de sécurité du prompt...")
                is_safe, guard_reason = await prompt_guard.acheck(project_desc)
                if not is_safe:
                    print(f"[PROMPT GUARD] 🚫 Prompt bloqué : {guard_reason}")
                    await self.send(json.dumps({
                        "type": "error",
                        "message": f"🛡️ Analyse refusée : {guard_reason}",
                        "guard_blocked": True,
                    }))
                    return

                self.analysis_task = asyncio.create_task(
                    self.run_analysis(project_desc, deep_scan=deep_scan, creativity=creativity, lang=lang, model=model, document_text=document_text)
                )
        except Exception as e:
            await self.send(json.dumps({
                "type": "error",
                "message": str(e)
            }))
    
    async def send_agent_update(self, agent, status, thoughts=None, progress=None, result=None):
        await self.send(json.dumps({
            "type": "agent_update",
            "agent": agent,
            "status": status,
            "thoughts": thoughts or [],
            "progress": progress,
            "result": result
        }))
    
    async def run_analysis(self, project_desc, deep_scan=False, creativity=50, lang='fr', model='llama-70b', document_text=''):
        if document_text:
            print(f"[RAG] 📄 Document utilisateur injecté — {len(document_text)} chars")
        try:
            state = AgentState(
                project_description=project_desc,
                document_text=document_text,
                lang=lang,
                creativity=creativity,
                model=model,
                trend_result={},
                vision_result={},
                emotion_result={},
                creative_result={},
                self_correction_score=0.0,
                correction_attempts=0,
                messages=[],
                current_thoughts=[]
            )

            # Deep Scan = 15 min timeout, analyse normale = 10 min
            timeout_seconds = 900 if deep_scan else 600
            scan_mode = "DEEP SCAN" if deep_scan else "ANALYSE RAPIDE"
            print(f"🔍 Mode : {scan_mode} | Créativité : {creativity}% | Timeout : {timeout_seconds}s")

            await self.send(json.dumps({
                "type": "analysis_started",
                "project": project_desc,
                "deep_scan": deep_scan,
                "creativity": creativity,
            }))

            try:
                async with asyncio.timeout(timeout_seconds):
                    async for event in compiled_graph.astream(state):
                        for node_name, node_output in event.items():
                            # Envoi d'un petit message "Keep-Alive" pour Firefox
                            await self.send(json.dumps({"type": "heartbeat", "agent": node_name}))
                            
                            if node_name == "parallel_scout":
                                # ── Trend Hunter ──────────────────────────────
                                await asyncio.sleep(0.5)
                                trend_result = node_output.get("trend_result", {})
                                images = trend_result.get("images", {})
                                total_img_bytes = sum(len(v.encode()) for v in images.values() if v)
                                if total_img_bytes > 1_000_000 and images:
                                    await self.send_agent_update(
                                        "trend_hunter", "completed",
                                        thoughts=trend_result.get("agent_thoughts", []),
                                        result={k: v for k, v in trend_result.items() if k != "images"}
                                    )
                                    await asyncio.sleep(0.2)
                                    await self.send(json.dumps({
                                        "type": "agent_images", "agent": "trend_hunter", "images": images
                                    }))
                                    print(f"[WS] Trend images envoyées séparément — {total_img_bytes // 1024}KB")
                                else:
                                    await self.send_agent_update(
                                        "trend_hunter", "completed",
                                        thoughts=trend_result.get("agent_thoughts", []),
                                        result=trend_result
                                    )

                                # ── Visual Semiotics ──────────────────────────
                                vision_result = node_output.get("vision_result", {})
                                vision_images = vision_result.get("images", {})
                                total_vision_bytes = sum(len(v.encode()) for v in vision_images.values() if v)
                                if total_vision_bytes > 1_000_000 and vision_images:
                                    await self.send_agent_update(
                                        "visual_semiotics", "completed",
                                        thoughts=vision_result.get("agent_thoughts", []),
                                        result={k: v for k, v in vision_result.items() if k != "images"}
                                    )
                                    await asyncio.sleep(0.2)
                                    await self.send(json.dumps({
                                        "type": "agent_images", "agent": "visual_semiotics", "images": vision_images
                                    }))
                                    print(f"[WS] Vision images envoyées séparément — {total_vision_bytes // 1024}KB")
                                else:
                                    await self.send_agent_update(
                                        "visual_semiotics", "completed",
                                        thoughts=vision_result.get("agent_thoughts", []),
                                        result=vision_result
                                    )

                                # ── Emotional Intelligence ────────────────────
                                raw_result = node_output.get("emotion_result", {})
                                print(f"DEBUG FRONTEND SENDING -> Keys trouvées: {list(raw_result.keys())}")
                                safe_result = {
                                    "sentiment_velocity": raw_result.get("sentiment_velocity", []),
                                    "sentiment_mining": raw_result.get("sentiment_mining", []),
                                    "hall_of_shame_html": raw_result.get("hall_of_shame_html", ""),
                                    "voice_matching": raw_result.get("voice_matching", {}),
                                    "loyalty_audit": raw_result.get("loyalty_audit", {}),
                                    "customer_journey": raw_result.get("customer_journey", []),
                                    "cognitive_strategy": raw_result.get("cognitive_strategy", {}),
                                    "ocean_profile": raw_result.get("ocean_profile", {}),
                                    "tone_of_voice": raw_result.get("tone_of_voice", {}),
                                    "behavioral_nudges": raw_result.get("behavioral_nudges", []),
                                    "ethical_hook": raw_result.get("ethical_hook", {}),
                                    "cognitive_load": raw_result.get("cognitive_load", {}),
                                    "agent_thoughts": raw_result.get("agent_thoughts", []),
                                    "activeTab": "market_emotions"
                                }
                                await self.send_agent_update(
                                    "emotional_intelligence", "completed",
                                    thoughts=raw_result.get("agent_thoughts", []),
                                    result=safe_result
                                )
                                print("✅ Messages envoyés au Frontend pour les 3 agents parallèles")

                            elif node_name == "creative_director":
                                await asyncio.sleep(1.5)
                                creative_result = node_output.get("creative_result", {})
                                # Adaptive split: extract roadmap images if too large
                                roadmap_phases = creative_result.get("roadmap_phases", [])
                                phase_images = {f"phase_{i}": p.get("image", "") for i, p in enumerate(roadmap_phases)}
                                total_img_bytes = sum(len(v) for v in phase_images.values() if v)
                                if total_img_bytes > 800_000 and any(phase_images.values()):
                                    # Strip images from phases before sending
                                    light_phases = [{k: v for k, v in p.items() if k != "image"} for p in roadmap_phases]
                                    light_result = {**creative_result, "roadmap_phases": light_phases}
                                    await self.send_agent_update(
                                        "creative_director", "completed",
                                        thoughts=node_output.get("current_thoughts", []),
                                        result=light_result
                                    )
                                    await self.send(json.dumps({
                                        "type": "agent_images",
                                        "agent": "creative_director",
                                        "images": phase_images
                                    }))
                                else:
                                    await self.send_agent_update(
                                        "creative_director", "completed",
                                        thoughts=node_output.get("current_thoughts", []),
                                        result=creative_result
                                    )
                            

            except asyncio.TimeoutError:
                print("⚠️ Analyse trop longue - Timeout Python")
                await self.send(json.dumps({
                    "type": "error",
                    "message": "Connexion lente : le délai a été dépassé."
                }))
                return
                    
            await self.send(json.dumps({"type": "analysis_complete"}))
            
        except asyncio.CancelledError:
            print("Analyse annulée")
        except Exception as e:
            print(f"Erreur durant l'analyse: {e}")
            await self.send(json.dumps({"type": "error", "message": str(e)}))
