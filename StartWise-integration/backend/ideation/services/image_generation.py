from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from random import randint
from time import sleep
from typing import Optional

import httpx

# ---------------------------------------------------------------------------
# PIL / Pillow — optional but strongly recommended
# ---------------------------------------------------------------------------
try:
    from PIL import Image as PilImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = logging.getLogger(__name__)

if not PIL_AVAILABLE:
    logger.warning(
        "Pillow is not installed — image format conversion (RGBA→RGB) will be "
        "skipped. Install it with: pip install Pillow"
    )

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
IMAGES_DIR = OUTPUT_DIR / "images"
SUMMARY_FILE = OUTPUT_DIR / "business_summary.txt"
IMAGE_OUTPUT_FILE = OUTPUT_DIR / "image_generation_output.json"

CONTENT_TYPE_SUFFIXES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

# Pollinations model fallback order — flux-schnell is fastest and most stable
_MODEL_FALLBACK_CHAIN = ["flux-schnell", "turbo", "flux"]
_POLLINATIONS_RETRYABLE_QUEUE_MARKERS = (
    "queue full",
    "too many requests",
)


class ImageGenerationError(RuntimeError):
    pass


@dataclass
class ImageGenerationResult:
    image_url: str
    business_idea: str
    generated_at: str
    status: str
    prompt: Optional[str] = None
    filename: Optional[str] = None
    local_path: Optional[str] = None
    file_size: Optional[int] = None
    serve_url: Optional[str] = None
    content_type: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {key: value for key, value in asdict(self).items() if value is not None}


class ImageGenerationService:
    def __init__(self) -> None:
        self.timeout_seconds = float(os.getenv("IMAGE_TIMEOUT_SECONDS", "60"))
        self.backend_base_url = os.getenv("BACKEND_URL", "http://localhost:8001").rstrip("/")
        self.default_width = int(os.getenv("IDEATION_IMAGE_WIDTH", "1344"))
        self.default_height = int(os.getenv("IDEATION_IMAGE_HEIGHT", "640"))
        self.default_model = os.getenv("IDEATION_IMAGE_MODEL", "flux-schnell")
        self.image_provider = os.getenv("IDEATION_IMAGE_PROVIDER", "auto").strip().lower()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.openai_image_model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1").strip()
        self.openai_image_quality = os.getenv("OPENAI_IMAGE_QUALITY", "low").strip().lower()
        self.openai_image_size = os.getenv("OPENAI_IMAGE_SIZE", "1536x1024").strip()
        self.openai_image_output_format = os.getenv("OPENAI_IMAGE_FORMAT", "jpeg").strip().lower()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_image(self, business_idea: str, prompt: str) -> ImageGenerationResult:
        cleaned_prompt = self._sanitize_prompt(prompt, business_idea)
        providers_to_try = self._resolve_provider_order()

        last_error: Exception | None = None
        for provider in providers_to_try:
            try:
                if provider == "openai":
                    image_bytes, content_type, source_ref = self._generate_with_openai(
                        cleaned_prompt
                    )
                    return self._persist_image(
                        business_idea=business_idea,
                        prompt=cleaned_prompt,
                        source_ref=source_ref,
                        image_bytes=image_bytes,
                        content_type=content_type,
                    )

                image_bytes, content_type, source_ref = self._generate_with_pollinations(
                    cleaned_prompt
                )
                return self._persist_image(
                    business_idea=business_idea,
                    prompt=cleaned_prompt,
                    source_ref=source_ref,
                    image_bytes=image_bytes,
                    content_type=content_type,
                )
            except Exception as exc:
                last_error = exc
                logger.warning("Image generation provider '%s' failed: %s", provider, exc)

        raise last_error or ImageGenerationError("All image providers failed")

    def _persist_image(
        self,
        *,
        business_idea: str,
        prompt: str,
        source_ref: str,
        image_bytes: bytes,
        content_type: str,
    ) -> ImageGenerationResult:

        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        suffix = CONTENT_TYPE_SUFFIXES.get(content_type, ".jpg")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        filename = f"{self._slugify(business_idea)}_{timestamp}{suffix}"
        file_path = IMAGES_DIR / filename

        try:
            file_path.write_bytes(image_bytes)
        except OSError as exc:
            raise ImageGenerationError(f"Failed to save image to disk: {exc}") from exc

        result = ImageGenerationResult(
            image_url=source_ref,
            business_idea=business_idea,
            generated_at=datetime.now(timezone.utc).isoformat(),
            status="success",
            prompt=prompt,
            filename=filename,
            local_path=str(file_path),
            file_size=file_path.stat().st_size,
            serve_url=f"{self.backend_base_url}/images/{filename}",
            content_type=content_type,
        )
        self._write_latest_image_output(result)
        return result

    def persist_summary(self, summary: str) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        SUMMARY_FILE.write_text(summary, encoding="utf-8")

    def append_metadata_to_summary(self, summary: str, asset: dict) -> str:
        clean_summary = self.strip_image_metadata(summary)
        if not asset:
            return clean_summary

        metadata_lines = [
            "",
            "---",
            "",
            "## Generated Visual Assets",
            "",
        ]
        background_image_url = asset.get("serve_url") or asset.get("image_url")
        if background_image_url:
            metadata_lines.append(f"**Background Image URL:** {background_image_url}")
        if asset.get("filename"):
            metadata_lines.append(f"**Image Filename:** {asset['filename']}")
        if asset.get("generated_at"):
            metadata_lines.append(f"**Generated:** {asset['generated_at']}")
        if asset.get("image_url"):
            metadata_lines.append(f"**Original Source:** {asset['image_url']}")

        return clean_summary.rstrip() + "\n" + "\n".join(metadata_lines)

    def strip_image_metadata(self, summary: str) -> str:
        if not summary:
            return summary
        return re.sub(
            r"\n\n---\n\n## Generated Visual Assets[\s\S]*$",
            "",
            summary,
        ).rstrip()

    def resolve_image_path(self, filename: str) -> Path:
        if not filename or filename != Path(filename).name:
            raise ImageGenerationError("Invalid image filename")
        path = IMAGES_DIR / filename
        if not path.exists() or not path.is_file():
            raise ImageGenerationError("Image not found")
        return path

    def guess_content_type(self, filename: str) -> str:
        guessed, _ = mimetypes.guess_type(filename)
        return guessed or "application/octet-stream"

    def latest_image_output(self) -> Optional[dict]:
        if not IMAGE_OUTPUT_FILE.exists():
            return None
        try:
            return json.loads(IMAGE_OUTPUT_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Could not parse %s", IMAGE_OUTPUT_FILE)
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_provider_order(self) -> list[str]:
        provider = self.image_provider or "auto"
        if provider == "openai":
            return ["openai", "pollinations"]
        if provider == "pollinations":
            return ["pollinations", "openai"]
        if self.openai_api_key:
            return ["openai", "pollinations"]
        return ["pollinations"]

    def _generate_with_openai(self, prompt: str) -> tuple[bytes, str, str]:
        if not self.openai_api_key:
            raise ImageGenerationError("OPENAI_API_KEY is not configured for image generation")

        payload = {
            "model": self.openai_image_model,
            "prompt": prompt,
            "size": self.openai_image_size,
            "quality": self.openai_image_quality,
            "output_format": self.openai_image_output_format,
        }

        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    "https://api.openai.com/v1/images/generations",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise ImageGenerationError(
                f"OpenAI image generation timed out after {self.timeout_seconds}s"
            ) from exc
        except httpx.HTTPStatusError as exc:
            body_preview = exc.response.text[:400]
            raise ImageGenerationError(
                f"OpenAI image generation returned HTTP {exc.response.status_code}: {body_preview}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ImageGenerationError(f"OpenAI image generation failed: {exc}") from exc

        images = data.get("data") or []
        if not images or not isinstance(images, list):
            raise ImageGenerationError("OpenAI image generation returned no image data")

        first = images[0] or {}
        encoded = first.get("b64_json")
        if not isinstance(encoded, str) or not encoded.strip():
            raise ImageGenerationError("OpenAI image generation did not return base64 image data")

        try:
            image_bytes = base64.b64decode(encoded)
        except Exception as exc:
            raise ImageGenerationError("Failed to decode OpenAI image bytes") from exc

        format_name = self.openai_image_output_format or "png"
        content_type = f"image/{format_name}"
        return image_bytes, content_type, f"openai:{self.openai_image_model}"

    def _generate_with_pollinations(self, prompt: str) -> tuple[bytes, str, str]:
        models_to_try = [self.default_model] + [
            m for m in _MODEL_FALLBACK_CHAIN if m != self.default_model
        ]

        last_error: Exception | None = None
        for model in models_to_try:
            source_url = self._build_provider_url(prompt, model=model)
            logger.info("Trying Pollinations model '%s' — URL: %s", model, source_url)
            try:
                image_bytes, content_type = self._download_image(source_url)
                logger.info("Image downloaded successfully with Pollinations model '%s'", model)
                return image_bytes, content_type, source_url
            except ImageGenerationError as exc:
                last_error = exc
                is_last = model == models_to_try[-1]
                logger.warning(
                    "Pollinations model '%s' failed: %s — %s",
                    model,
                    exc,
                    "no more models to try" if is_last else "trying next model",
                )

        raise last_error or ImageGenerationError("All Pollinations models failed")

    def _build_provider_url(self, prompt: str, model: str | None = None) -> str:
        """Build a Pollinations URL using proven hyphen-based encoding.

        Key insight from working projects: replace spaces with hyphens and strip
        ALL special characters before embedding the prompt in the URL path.
        This avoids %20/%22 encoding explosions that cause Pollinations 500 errors.
        Hard cap at 200 chars for the prompt segment.
        """
        active_model = model or self.default_model
        seed = randint(1, 1_000_000)

        # Replace spaces with hyphens (not %20)
        url_prompt = prompt.replace(" ", "-")
        # Strip everything Pollinations chokes on in the URL path
        url_prompt = re.sub(r'[,\.\'\"\\/:;!?@#$%^&*()\[\]{}<>|=+~`]', "", url_prompt)
        # Collapse multiple consecutive hyphens into one
        url_prompt = re.sub(r"-{2,}", "-", url_prompt)
        url_prompt = url_prompt.strip("-")
        # Hard cap — Pollinations 500s on very long path segments
        url_prompt = url_prompt[:200]

        return (
            f"https://image.pollinations.ai/prompt/{url_prompt}"
            f"?width={self.default_width}&height={self.default_height}"
            f"&model={active_model}&nologo=true&private=true&seed={seed}"
        )

    def _download_image(self, image_url: str, _depth: int = 0) -> tuple[bytes, str]:
        """Download and validate an image from *image_url*.

        *_depth* guards against infinite redirect recursion when Pollinations
        returns an HTML page that itself contains another HTML page.
        """
        if _depth > 2:
            raise ImageGenerationError("Too many redirects while resolving image URL")

        headers = {
            "Accept": "image/*, */*",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            ),
        }

        retries_remaining = 2
        while True:
            try:
                with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
                    response = client.get(image_url, headers=headers)
                    response.raise_for_status()
                break
            except httpx.TimeoutException as exc:
                raise ImageGenerationError(
                    f"Image download timed out after {self.timeout_seconds}s"
                ) from exc
            except httpx.HTTPStatusError as exc:
                body_preview = ""
                try:
                    body_preview = exc.response.text[:400]
                except Exception:
                    pass
                if (
                    exc.response.status_code == 429
                    and retries_remaining > 0
                    and any(marker in body_preview.lower() for marker in _POLLINATIONS_RETRYABLE_QUEUE_MARKERS)
                ):
                    retries_remaining -= 1
                    sleep(2.0)
                    continue
                logger.warning(
                    "Pollinations returned HTTP %s. Body: %s",
                    exc.response.status_code,
                    body_preview,
                )
                raise ImageGenerationError(
                    f"Image provider returned HTTP {exc.response.status_code}: {body_preview}"
                ) from exc
            except httpx.HTTPError as exc:
                raise ImageGenerationError(f"Image download failed: {exc}") from exc

        content_type = (
            response.headers.get("content-type", "").split(";")[0].strip().lower()
        )
        content = response.content

        # Pollinations sometimes returns an HTML landing page instead of an image.
        # Try to extract a direct image URL from it and retry.
        if "html" in content_type or (
            content and content[:15].lower().lstrip().startswith(b"<!doctype")
        ):
            logger.warning("Got HTML response — attempting to extract direct image URL")
            extracted_url = self._extract_image_url(response.text)
            if extracted_url and extracted_url != image_url:
                logger.info("Retrying with extracted URL: %s", extracted_url)
                return self._download_image(extracted_url, _depth=_depth + 1)
            raise ImageGenerationError(
                "Image provider returned HTML — no direct image URL could be extracted"
            )

        # Sanity check: real images are always at least 1 KB
        if not content or len(content) < 1000:
            raise ImageGenerationError(
                f"Response too small ({len(content)} bytes) — expected image data"
            )

        # ------------------------------------------------------------------
        # PIL validation & colour-mode conversion
        # ------------------------------------------------------------------
        if PIL_AVAILABLE:
            try:
                image = PilImage.open(BytesIO(content))
                # verify() fully decodes to catch corruption early; it exhausts
                # the file pointer so we must re-open afterward.
                image.verify()
                image = PilImage.open(BytesIO(content))

                if image.mode in ("RGBA", "LA", "P"):
                    logger.info("Converting image from mode '%s' to RGB", image.mode)
                    rgb_image = PilImage.new("RGB", image.size, (255, 255, 255))
                    if image.mode == "P":
                        image = image.convert("RGBA")
                    mask = image.split()[-1] if image.mode in ("RGBA", "LA") else None
                    rgb_image.paste(image, mask=mask)

                    buffer = BytesIO()
                    rgb_image.save(buffer, format="JPEG", quality=95)
                    content = buffer.getvalue()
                    content_type = "image/jpeg"
                    logger.info("Image converted to RGB JPEG successfully")

            except ImageGenerationError:
                raise
            except Exception as exc:
                raise ImageGenerationError(
                    f"Image validation/conversion failed: {exc}"
                ) from exc
        else:
            logger.debug("Skipping PIL validation (Pillow not installed)")

        return content, content_type

    def _extract_image_url(self, html: str) -> Optional[str]:
        patterns = [
            r'<img[^>]+src=["\']([^"\']+)["\']',
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, flags=re.IGNORECASE)
            if match:
                return match.group(1).replace("&amp;", "&")
        return None

    def _sanitize_prompt(self, prompt: str, business_idea: str) -> str:
        """Normalise the raw LLM prompt before URL building.

        _build_provider_url handles URL-specific cleaning (hyphens, char
        stripping). This step just normalises whitespace, strips quotes, and
        enforces a sensible length so the LLM can't send a 500-word paragraph.
        """
        text = re.sub(r"\s+", " ", (prompt or "").strip())
        text = re.sub(r"^(prompt|image prompt)\s*:\s*", "", text, flags=re.IGNORECASE)
        # Strip all flavours of quotation marks
        text = re.sub(r'[\"""\'\'\'`\u2018\u2019\u201c\u201d]', "", text)
        # Remove common list/bullet prefixes
        text = re.sub(r"^[\-\*\d\.\)\s]+", "", text).strip()
        if not text:
            text = self._fallback_prompt(business_idea)
        # 150 chars is plenty — _build_provider_url hard-caps at 200 anyway
        if len(text) > 150:
            text = text[:150].rsplit(" ", 1)[0].strip()
        return text

    def _fallback_prompt(self, business_idea: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9 ]", "", business_idea).strip()
        return (
            f"editorial hero image of a restaurant DIY meal kit service, {safe}, "
            "fresh ingredients on a kitchen counter, chef-prepared components, warm natural light, "
            "modern home cooking atmosphere, realistic food photography, wide website header composition"
        )

    def _slugify(self, value: str) -> str:
        text = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip().lower())
        text = re.sub(r"_+", "_", text).strip("_")
        return text[:60] or "business_visual"

    def _write_latest_image_output(self, result: ImageGenerationResult) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        IMAGE_OUTPUT_FILE.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


image_generation_service = ImageGenerationService()
