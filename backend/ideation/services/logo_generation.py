from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

from .image_generation import ImageGenerationError, image_generation_service

logger = logging.getLogger(__name__)


class LogoGenerationService:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
        self.timeout = float(os.getenv("A2A_TIMEOUT_SECONDS", "60"))
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"

    # ------------------------------------------------------------------
    # Internal LLM call
    # ------------------------------------------------------------------

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            logger.error("OPENROUTER_API_KEY is not set")
            return ""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://startwise.ai",
            "X-Title": "Startwise",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.openrouter_url, headers=headers, json=payload
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
        except httpx.TimeoutException as exc:
            logger.error("LLM call timed out after %ss: %s", self.timeout, exc)
            return ""
        except httpx.HTTPStatusError as exc:
            logger.error(
                "LLM call returned HTTP %s: %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            return ""
        except Exception as exc:
            logger.error("LLM call failed unexpectedly: %s", exc)
            return ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_brand_names(self, business_description: str) -> List[str]:
        system_prompt = (
            "You are a professional brand naming consultant. "
            "Generate 10 creative, memorable, and industry-appropriate names for a new business. "
            "Return only a JSON array of strings with no preamble or markdown fences."
        )
        user_prompt = f"Business Description: {business_description}"
        raw_output = await self._call_llm(system_prompt, user_prompt)
        result = self._parse_json_list(raw_output)
        if not result:
            logger.warning("Brand name generation returned empty list; using fallback")
        return result

    async def generate_logo_palettes(
        self, business_description: str
    ) -> List[Dict[str, Any]]:
        system_prompt = (
            "You are a color theory expert and brand designer. "
            "Suggest 3 distinct color palettes for this business logo. "
            "For each palette provide: name, colors (hex codes array), description, mood. "
            "Return only a valid JSON array of objects with keys: name, colors, description, mood. "
            "No preamble or markdown fences."
        )
        user_prompt = f"Business Description: {business_description}"
        raw_output = await self._call_llm(system_prompt, user_prompt)
        result = self._parse_json_list(raw_output)
        if not result:
            logger.warning("Palette generation returned empty list; using fallback")
            result = self._fallback_palettes()
        return result

    async def generate_logo_suggestions(
        self, business_description: str
    ) -> Dict[str, Any]:
        system_prompt = (
            "You are a professional logo designer. "
            "Provide 3 creative logo concepts/styles for this business. "
            "Include 'suggested_styles' (list), 'suggested_keywords' (list), "
            "and 'style_descriptions' (dict mapping style name to description). "
            "Return only valid JSON with no preamble or markdown fences."
        )
        user_prompt = f"Business Description: {business_description}"
        raw_output = await self._call_llm(system_prompt, user_prompt)
        return self._parse_json_dict(raw_output) or self._fallback_suggestions()

    async def generate_logo(
        self,
        business_description: str,
        logo_description: str,
        color_palette: List[str],
        style: str = "Modern",
    ) -> Dict[str, Any]:
        # 1. Ask the LLM to craft an optimised visual prompt.
        system_prompt = (
            "You are a professional logo design prompt engineer. "
            "Create a highly detailed, clean logo generation prompt for an AI image generator. "
            "Focus on: minimalist design, vector style, white background, no text, professional aesthetics. "
            "Include specific color instructions from the palette provided. "
            "Return only the final prompt string — no quotes, no intro, no markdown."
        )
        user_prompt = (
            f"Business: {business_description}\n"
            f"Logo Concept: {logo_description}\n"
            f"Color Palette: {', '.join(color_palette)}\n"
            f"Style: {style}"
        )

        visual_prompt = await self._call_llm(system_prompt, user_prompt)
        if not visual_prompt:
            logger.warning("LLM returned empty visual prompt; using fallback")
            visual_prompt = (
                f"Professional minimalist logo for {business_description}, "
                f"{logo_description}, style {style}, "
                f"palette {', '.join(color_palette)}, vector, white background"
            )

        # 2. Append technical quality modifiers.
        final_prompt = (
            f"{visual_prompt}, flat vector logo, minimalist, white background, "
            "high contrast, sharp edges, 4k, professional graphic design, centered"
        )

        # 3. Generate image via the shared image service (OpenAI first, Pollinations fallback).
        try:
            result = image_generation_service.generate_image(
                business_idea=business_description,
                prompt=final_prompt,
            )
            return {
                "success": True,
                "url": result.serve_url,
                "prompt": final_prompt,
                "filename": result.filename,
            }
        except ImageGenerationError as exc:
            logger.error("Logo image generation failed: %s", exc)
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            logger.exception("Unexpected error during logo image generation")
            return {"success": False, "error": "Unexpected image generation error"}

    async def generate_3d_logo(
        self,
        business_description: str,
        logo_description: str,
        color_palette: List[str],
    ) -> Dict[str, Any]:
        return await self.generate_logo(
            business_description=business_description,
            logo_description=f"3D isometric version of {logo_description}",
            color_palette=color_palette,
            style="3D Render",
        )

    # ------------------------------------------------------------------
    # Fallbacks
    # ------------------------------------------------------------------

    def _fallback_palettes(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "Professional Blue",
                "colors": ["#1A73E8", "#FFFFFF", "#F1F3F4"],
                "description": "Clean and corporate.",
                "mood": "Trust",
            },
            {
                "name": "Vibrant Green",
                "colors": ["#34A853", "#FFFFFF", "#E6F4EA"],
                "description": "Fresh and energetic.",
                "mood": "Growth",
            },
            {
                "name": "Bold Dark",
                "colors": ["#202124", "#FFFFFF", "#5F6368"],
                "description": "Sophisticated and modern.",
                "mood": "Confidence",
            },
        ]

    def _fallback_suggestions(self) -> Dict[str, Any]:
        return {
            "suggested_styles": ["Minimalist", "Modern", "Classic"],
            "suggested_keywords": ["Professional", "Trust", "Innovation"],
            "style_descriptions": {
                "Minimalist": "Clean and simple with plenty of white space.",
                "Modern": "Future-oriented with geometric shapes.",
                "Classic": "Timeless design with traditional elements.",
            },
        }

    # ------------------------------------------------------------------
    # JSON helpers
    # ------------------------------------------------------------------

    def _parse_json_list(self, text: str) -> List[Any]:
        if not text:
            return []
        try:
            # Strip markdown fences if present.
            cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
            match = re.search(r"(\[.*\])", cleaned, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        except Exception as exc:
            logger.warning("Failed to parse JSON list: %s — raw: %s", exc, text[:200])
        return []

    def _parse_json_dict(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        try:
            cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        except Exception as exc:
            logger.warning("Failed to parse JSON dict: %s — raw: %s", exc, text[:200])
        return None


logo_generation_service = LogoGenerationService()
