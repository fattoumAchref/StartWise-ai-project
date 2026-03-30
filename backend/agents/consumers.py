# backend/consumers.py
import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from .graph import compiled_graph, AgentState

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
                self.analysis_task = asyncio.create_task(
                    self.run_analysis(project_desc)
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
    
    async def run_analysis(self, project_desc):
        try:
            state = AgentState(
                project_description=project_desc,
                trend_result={},
                vision_result={},
                emotion_result={},
                creative_result={},
                self_correction_score=0.0,
                correction_attempts=0,
                messages=[],
                current_thoughts=[]
            )
            
            await self.send(json.dumps({
                "type": "analysis_started",
                "project": project_desc
            }))
            
            # --- MODIFICATION ICI : On passe à 600 secondes (10 min) ---
            try:
                async with asyncio.timeout(600): 
                    async for event in compiled_graph.astream(state):
                        for node_name, node_output in event.items():
                            # Envoi d'un petit message "Keep-Alive" pour Firefox
                            await self.send(json.dumps({"type": "heartbeat", "agent": node_name}))
                            
                            if node_name == "trend_hunter":
                                await asyncio.sleep(1)
                                await self.send_agent_update(
                                    "trend_hunter", "completed",
                                    thoughts=node_output.get("current_thoughts", []),
                                    result=node_output.get("trend_result", {})
                                )
                            elif node_name == "visual_semiotics":
                                await self.send_agent_update(
                                    "visual_semiotics", "completed",
                                    thoughts=node_output.get("current_thoughts", []),
                                    result=node_output.get("vision_result", {})
                                )
                            elif node_name == "emotional_intelligence":
                                raw_result = node_output.get("emotion_result", {})
                                print(f"DEBUG FRONTEND SENDING -> Keys trouvées: {list(raw_result.keys())}")

                                safe_result = {
                                    "sentiment_velocity": raw_result.get("sentiment_velocity", []),
                                    "sentiment_mining": raw_result.get("sentiment_mining", []),
                                    "hall_of_shame_html": raw_result.get("hall_of_shame_html", ""),
                                    "voice_matching": raw_result.get("voice_matching", {}),
                                    "loyalty_audit": raw_result.get("loyalty_audit", {}),
                                    "customer_journey": raw_result.get("customer_journey", []),
                                    "activeTab": "market_emotions"
                                }
                                await self.send_agent_update(
                                    "emotional_intelligence", 
                                    "completed",
                                    thoughts=node_output.get("current_thoughts", []),
                                    result=safe_result
                                )
                                print("✅ Message envoyé au Frontend pour l'Emotional Agent")
                            elif node_name == "self_correction":
                                await self.send_agent_update(
                                    "self_correction", "completed",
                                    thoughts=node_output.get("current_thoughts", []),
                                    result={
                                        "score": node_output.get("self_correction_score", 0),
                                        "attempts": node_output.get("correction_attempts", 0)
                                    }
                                )
                            elif node_name == "creative_director":
                                await asyncio.sleep(1.5) 
                                await self.send_agent_update(
                                    "creative_director", "completed",
                                    thoughts=node_output.get("current_thoughts", []),
                                    result=node_output.get("creative_result", {})
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
