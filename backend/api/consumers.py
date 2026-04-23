"""
api/consumers.py
================
WebSocket consumer — pushes A2A state to the Next.js frontend every 2 s.
Replaces Streamlit's st.rerun() polling loop.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class A2AConsumer(AsyncWebsocketConsumer):
    async def connect(self) -> None:
        await self.accept()
        self._running = True
        asyncio.ensure_future(self._push_loop())

    async def disconnect(self, close_code: int) -> None:
        self._running = False

    async def receive(self, text_data: str) -> None:
        # Client can send {"type": "stop"} to halt the loop
        try:
            msg = json.loads(text_data)
            if msg.get("type") == "stop":
                self._running = False
        except Exception:
            pass

    async def _push_loop(self) -> None:
        from api.session_utils import get_comm_agent

        while self._running:
            try:
                comm = get_comm_agent()
                if comm and os.getenv("A2A_BUS_URL"):
                    state = await asyncio.get_event_loop().run_in_executor(
                        None, comm.get_state
                    )
                    await self.send(
                        json.dumps(
                            {
                                "type": "a2a_state",
                                "state": state,
                                "ts": time.time(),
                            },
                            ensure_ascii=False,
                            default=str,
                        )
                    )
            except Exception as exc:
                logger.debug("[WS] push error: %s", exc)

            await asyncio.sleep(2)
