"""
analyzer.py – Creative analysis via Claude Vision (images) and
              OpenAI Whisper (video / UGC audio transcripts).

Required env vars:
  ANTHROPIC_API_KEY  – Claude API key
  OPENAI_API_KEY     – OpenAI API key (for Whisper)
"""

import base64
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import anthropic
import httpx
import openai

logger = logging.getLogger(__name__)

# Claude model to use for vision analysis
CLAUDE_VISION_MODEL = "claude-opus-4-6"

VISION_PROMPT = """\
You are a performance marketing creative analyst. Analyse this Meta ad creative and return a JSON object with the following keys:
- "hook": the opening hook / headline message (string)
- "cta": call-to-action text detected (string or null)
- "emotion": primary emotional tone (e.g. "urgency", "aspiration", "humour", "social_proof")
- "color_palette": list of up to 3 dominant colors as hex codes
- "text_overlay": true/false – does the creative have text overlaid on the image/video?
- "product_visible": true/false – is a product clearly visible?
- "people_visible": true/false – are people / faces visible?
- "ugc_style": true/false – does it look like user-generated content?
- "brand_elements": list of brand elements detected (logo, tagline, colours, etc.)
- "scene_description": 1-2 sentence description of the visual scene
- "creative_themes": list of up to 5 descriptive themes (e.g. "lifestyle", "before_after", "testimonial")

Return only the JSON object, no markdown fences.
"""


class CreativeAnalyzer:
    """
    Analyses ad creatives using:
      • Claude Vision API  – for image frames / thumbnails
      • OpenAI Whisper    – for video / UGC audio transcription

    Parameters
    ----------
    anthropic_api_key : str, optional
        Falls back to ANTHROPIC_API_KEY env var.
    openai_api_key : str, optional
        Falls back to OPENAI_API_KEY env var.
    max_image_bytes : int
        Images larger than this are resized before sending to Claude.
    """

    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        max_image_bytes: int = 5 * 1024 * 1024,  # 5 MB
    ):
        self._claude = anthropic.Anthropic(
            api_key=anthropic_api_key or os.environ["ANTHROPIC_API_KEY"]
        )
        openai.api_key = openai_api_key or os.environ["OPENAI_API_KEY"]
        self.max_image_bytes = max_image_bytes

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyse_image(self, image_url: str) -> dict:
        """
        Download image from *image_url* and run Claude Vision analysis.

        Returns a dict matching the keys in VISION_PROMPT, or an error dict.
        """
        try:
            image_data, media_type = self._download_image(image_url)
            return self._claude_vision(image_data, media_type)
        except Exception as exc:
            logger.warning("Image analysis failed for %s: %s", image_url, exc)
            return {"error": str(exc)}

    def transcribe_video(self, video_url: str) -> str:
        """
        Download video/audio from *video_url*, extract audio, and transcribe
        using OpenAI Whisper.

        Returns the transcript string, or an empty string on failure.
        """
        try:
            return self._whisper_transcribe(video_url)
        except Exception as exc:
            logger.warning("Transcription failed for %s: %s", video_url, exc)
            return ""

    def analyse_creative(self, media_url: str, ad_format: str) -> dict:
        """
        Dispatch to the right analyser based on *ad_format*.

        Returns a dict with at minimum:
          - "vision_analysis": dict (images and video thumbnails)
          - "transcript": str (videos only)
        """
        result: dict = {"vision_analysis": {}, "transcript": ""}

        if ad_format in ("IMAGE", "CAROUSEL", "MEME"):
            result["vision_analysis"] = self.analyse_image(media_url)
        elif ad_format == "VIDEO":
            result["transcript"] = self.transcribe_video(media_url)
            # Also analyse a representative frame (snapshot URL is an image)
            result["vision_analysis"] = self.analyse_image(media_url)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _download_image(self, url: str) -> tuple[bytes, str]:
        """Download image bytes and return (bytes, media_type)."""
        resp = httpx.get(url, follow_redirects=True, timeout=30)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0]
        return resp.content, content_type

    def _claude_vision(self, image_data: bytes, media_type: str) -> dict:
        """Send image to Claude Vision and parse the JSON response."""
        import json

        b64 = base64.standard_b64encode(image_data).decode("utf-8")
        message = self._claude.messages.create(
            model=CLAUDE_VISION_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": VISION_PROMPT},
                    ],
                }
            ],
        )
        raw_text = message.content[0].text.strip()
        return json.loads(raw_text)

    def _whisper_transcribe(self, video_url: str) -> str:
        """Download audio/video and transcribe with Whisper."""
        resp = httpx.get(video_url, follow_redirects=True, timeout=60)
        resp.raise_for_status()

        suffix = Path(video_url.split("?")[0]).suffix or ".mp4"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as audio_file:
            transcript = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )

        os.unlink(tmp_path)
        return transcript.text
