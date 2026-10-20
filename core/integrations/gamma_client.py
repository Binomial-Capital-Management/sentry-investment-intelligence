"""
Gamma API Client - Minimal Integration
Status: Production
Created: January 2025

PURPOSE: Generate professional presentations using Gamma AI API.
Gracefully falls back to free Playwright PDF if unavailable or fails.

CRITICAL: No hardcoding - all parameters configurable via env vars or function args.
"""
import os
import logging
from typing import Optional, Dict, Any
import aiohttp
import asyncio

logger = logging.getLogger(__name__)


def build_instructions_from_settings(
    base_prompt: Optional[str],
    verbosity: str,
    tone: str,
    audience: str
) -> str:
    """
    Convert export settings into natural language instructions for Gamma API.

    Gamma doesn't accept structured parameters like verbosity/tone/audience directly.
    Instead, we inject these preferences as natural language instructions in the
    additionalInstructions parameter.

    Args:
        base_prompt: User's custom prompt (or None for defaults)
        verbosity: "brief", "low", "mid", "high"
        tone: e.g., "formal", "conversational", "technical", "persuasive"
        audience: e.g., "C-suite executives", "Institutional analysts", "Individual investors"

    Returns:
        Combined instruction string with settings-based guidance
    """
    # Verbosity mapping with specific word count guidance
    verbosity_instructions = {
        "brief": "Keep the response concise and focused. Aim for 200-300 words per section. Prioritize key insights over exhaustive detail.",
        "low": "Provide moderate detail with clear explanations. Target 300-500 words per section. Include essential context and supporting evidence.",
        "mid": "Provide balanced, detailed analysis. Aim for 500-800 words per section. Cover all relevant aspects with appropriate depth.",
        "high": "Provide comprehensive, in-depth analysis with extensive detail. 1000+ words per section when appropriate. Include thorough explanations, multiple perspectives, and complete context."
    }

    # Tone-specific instructions
    tone_instructions = {
        "formal": "Use formal, professional language throughout. Maintain a serious, authoritative tone. Avoid colloquialisms and casual expressions.",
        "conversational": "Use approachable, conversational language. Explain concepts in a friendly, accessible manner while maintaining professionalism.",
        "technical": "Use precise technical and financial terminology. Include specific calculations, methodologies, and quantitative details. Assume expert-level understanding.",
        "academic": "Maintain scholarly objectivity and rigor. Use academic structure with clear methodology. Cite approaches and include limitations.",
        "persuasive": "Use confident, compelling language. Emphasize opportunities and potential. Build a clear narrative that leads to actionable recommendations.",
        "neutral": "Maintain balanced, factual tone. Present information objectively without advocacy. Use measured language.",
        "engaging": "Use dynamic, interesting language that holds attention. Vary sentence structure. Include relevant examples and analogies.",
        "strategic": "Focus on forward-looking implications and strategic options. Emphasize competitive positioning and long-term trends.",
        "direct": "Use clear, no-nonsense language. Get straight to the point. Minimize elaboration."
    }

    # Audience-specific context
    audience_instructions = {
        "C-suite executives": "Target C-suite executives. Focus on strategic implications, high-level takeaways, and business impact. Minimize technical jargon. Lead with conclusions.",
        "Institutional analysts": "Target institutional analysts and portfolio managers. Include detailed calculations, methodologies, and data sources. Use precise financial terminology.",
        "Potential investors": "Target potential investors. Emphasize investment opportunity and value proposition. Highlight competitive advantages and growth potential. Include clear investment thesis.",
        "Board of directors": "Target board of directors. Focus on governance implications, risk factors, and fiduciary considerations. Address material risks and compliance matters.",
        "Conference attendees": "Target conference attendees. Use presentation-friendly language. Break complex ideas into clear, digestible concepts. Include speaking points.",
        "Shareholders": "Target shareholders. Follow clear reporting structure. Use year-over-year and quarter-over-quarter comparisons. Balance transparency with strategic messaging.",
        "Individual investors": "Target individual investors. Explain complex topics in plain language. Use analogies and examples. Define technical terms clearly. Focus on practical implications.",
        "Leadership team": "Target senior leadership. Balance strategic vision with operational detail. Include scenario analysis and actionable recommendations.",
        "Research teams": "Target research professionals. Use academic rigor and complete methodology. Maintain objectivity. Include data sources and limitations.",
        "Busy executives": "Target time-constrained executives. Use bullet points and clear structure. Highlight only critical information. Assume reader has limited time."
    }

    # Build the combined instructions
    instructions_parts = []

    # Start with base prompt if provided
    if base_prompt and base_prompt.strip():
        instructions_parts.append(base_prompt.strip())

    # Add settings-based guidance
    settings_guidance = []

    # Add verbosity instruction
    if verbosity in verbosity_instructions:
        settings_guidance.append(verbosity_instructions[verbosity])

    # Add tone instruction
    if tone in tone_instructions:
        settings_guidance.append(tone_instructions[tone])
    elif tone:  # Custom tone not in our map
        settings_guidance.append(f"Use a {tone} tone throughout the document.")

    # Add audience instruction
    if audience in audience_instructions:
        settings_guidance.append(audience_instructions[audience])
    elif audience:  # Custom audience not in our map
        settings_guidance.append(f"Target this content for: {audience}.")

    # Combine all instructions
    if settings_guidance:
        if instructions_parts:
            # Append to existing custom prompt
            instructions_parts.append("\n\nAdditional formatting preferences:")
            instructions_parts.append(" ".join(settings_guidance))
        else:
            # No custom prompt, just use settings
            instructions_parts.append(" ".join(settings_guidance))

    # Return combined instructions (or default if nothing specified)
    return "\n".join(instructions_parts) if instructions_parts else GammaClient.DEFAULT_INSTITUTIONAL_PROMPT


class GammaClient:
    """
    Minimal Gamma API client with graceful degradation.

    Features:
    - Returns None on any failure (caller handles fallback)
    - No hardcoded themes, formats, or parameters
    - Respects user configuration via env vars
    - Proper async/await patterns
    """

    BASE_URL = "https://public-api.gamma.app/v1.0"

    # Institutional defaults for Binomial
    DEFAULT_INSTITUTIONAL_PROMPT = (
        "Use a professional institutional investment analysis tone with data-driven insights. "
        "Include specific metrics and calculations where relevant. "
        "Maintain clear, authoritative language appropriate for institutional investors. "
        "Emphasize actionable recommendations supported by evidence."
    )

    def __init__(self):
        """Initialize with optional API key from environment."""
        self.api_key = os.getenv("GAMMA_API_KEY")
        self.enabled = bool(self.api_key) and os.getenv("GAMMA_ENABLED", "false").lower() == "true"

        # Configurable defaults (no hardcoding)
        self.default_timeout = int(os.getenv("GAMMA_TIMEOUT_SECONDS", "900"))

        # Logo configuration (optional)
        # Use "themeLogo" to use the logo from your Gamma theme (recommended)
        # Or provide a public URL for "custom" logo source
        self.logo_source = os.getenv("GAMMA_LOGO_SOURCE", "themeLogo")  # Options: "themeLogo" or "custom"
        self.logo_url = os.getenv("GAMMA_LOGO_URL")  # Public URL (required if source="custom")
        self.logo_position = os.getenv("GAMMA_LOGO_POSITION", "topRight")  # topLeft, topRight, topCenter, bottomLeft, bottomRight, bottomCenter
        self.logo_size = os.getenv("GAMMA_LOGO_SIZE", "md")  # sm, md, lg, xl
        self.logo_enabled = os.getenv("GAMMA_LOGO_ENABLED", "true").lower() == "true"

        # Validate logo configuration
        if self.logo_enabled:
            if self.logo_source == "custom" and not self.logo_url:
                logger.warning("GAMMA_LOGO_SOURCE=custom but GAMMA_LOGO_URL not set - logo disabled")
                self.logo_enabled = False
            elif self.logo_source == "themeLogo":
                logger.info("Gamma logo configured to use theme logo")
            elif self.logo_source == "custom":
                logger.info(f"Gamma logo configured with custom URL: {self.logo_url[:50]}...")

        if self.enabled:
            logger.info("Gamma API client initialized (enabled)")
        else:
            logger.info("Gamma API client initialized (disabled - missing API key or not enabled)")

    async def generate_presentation(
        self,
        content: str,
        format: str = "presentation",
        export_as: str = "pdf",
        num_cards: Optional[int] = None,
        theme_id: Optional[str] = None,
        text_options: Optional[Dict[str, Any]] = None,
        image_options: Optional[Dict[str, Any]] = None,
        additional_instructions: Optional[str] = None,
        cardOptions: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Optional[bytes]:
        """
        Generate presentation using Gamma API.

        Args:
            content: The text content to generate from
            format: "presentation" or "document"
            export_as: "pdf" or "pptx"
            num_cards: Number of slides/cards (auto if None)
            theme_id: Theme ID (uses Gamma default if None)
            text_options: Dict with amount, tone, audience, language
            image_options: Dict with source (noImages, basic, advanced, etc)
            additional_instructions: Extra instructions for generation
            cardOptions: Dict with headerFooter configuration (logo, page numbers)
            **kwargs: Additional parameters passed to API

        Returns:
            bytes: PDF/PPTX file bytes
            None: If API call fails (caller should use fallback)

        Raises:
            None - all errors are caught and logged, returns None for graceful degradation
        """
        if not self.enabled:
            logger.debug("Gamma API disabled, skipping")
            return None

        if not content or not isinstance(content, str):
            logger.warning("Invalid content for Gamma API, skipping")
            return None

        try:
            # Apply institutional defaults if not provided
            if text_options is None:
                text_options = {
                    "amount": "detailed",
                    "tone": "professional",
                    "audience": "expert",
                    "language": "en"
                }

            if image_options is None:
                image_options = {"source": "noImages"}

            if additional_instructions is None:
                additional_instructions = self.DEFAULT_INSTITUTIONAL_PROMPT

            if cardOptions is None:
                # Build default header/footer with optional logo
                header_footer = {
                    "bottomRight": {"type": "cardNumber"},
                    "hideFromFirstCard": True
                }

                # Add logo if enabled
                if self.logo_enabled:
                    logo_config = {
                        "type": "image",
                        "source": self.logo_source,
                        "size": self.logo_size
                    }

                    # Add src only if using custom logo (not for themeLogo)
                    if self.logo_source == "custom" and self.logo_url:
                        logo_config["src"] = self.logo_url

                    header_footer[self.logo_position] = logo_config

                cardOptions = {"headerFooter": header_footer}

            # Build request payload
            payload = {
                "inputText": content,
                "textMode": "generate",
                "format": format,
                "exportAs": export_as,
                "textOptions": text_options,
                "imageOptions": image_options,
                "additionalInstructions": additional_instructions,
                "cardOptions": cardOptions,
            }

            # Add optional parameters only if they have values
            if theme_id is not None:
                payload["themeId"] = theme_id
            if num_cards is not None:
                payload["numCards"] = num_cards

            # Add any extra kwargs (future-proof, no hardcoding)
            for key, value in kwargs.items():
                if key not in payload and value is not None:
                    payload[key] = value

            logger.info(f"Calling Gamma API: format={format}, export={export_as}, cards={num_cards}")
            logger.info(f"DEBUG: Full payload: {payload}")

            # Call API with timeout
            generation_id = await self._create_generation(payload)

            if not generation_id:
                logger.warning("Gamma API did not return generation ID")
                return None

            # Poll for completion and download result
            result_bytes = await self._poll_and_download(generation_id, export_as)

            if result_bytes:
                logger.info(f"Gamma API success: {len(result_bytes)} bytes")
                return result_bytes
            else:
                logger.warning("Gamma API completed but no file returned")
                return None

        except Exception as e:
            logger.error(f"Gamma API error: {e}", exc_info=True)
            return None  # Graceful degradation

    async def _create_generation(self, payload: Dict[str, Any]) -> Optional[str]:
        """
        Create a new generation and return the generation ID.

        Returns:
            str: Generation ID to poll for results
            None: If request fails
        """
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

        timeout = aiohttp.ClientTimeout(total=self.default_timeout)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.BASE_URL}/generations",
                    json=payload,
                    headers=headers
                ) as response:

                    if response.status == 401:
                        logger.error("Gamma API authentication failed - check API key")
                        return None

                    if response.status == 403:
                        logger.error("Gamma API forbidden - check credits or subscription")
                        return None

                    if response.status == 429:
                        logger.error("Gamma API rate limit exceeded (50/hour)")
                        return None

                    if response.status != 200 and response.status != 201:
                        error_text = await response.text()
                        logger.error(f"Gamma API error {response.status}: {error_text}")
                        return None

                    result = await response.json()
                    generation_id = result.get("id") or result.get("generationId")

                    return generation_id

        except asyncio.TimeoutError:
            logger.error(f"Gamma API timeout after {self.default_timeout}s")
            return None
        except Exception as e:
            logger.error(f"Gamma API request failed: {e}")
            return None

    async def _poll_and_download(
        self,
        generation_id: str,
        export_format: str,
        max_wait_seconds: int = 900,  # 15 minutes for extensive institutional content
        poll_interval: int = 5
    ) -> Optional[bytes]:
        """
        Poll for generation completion and download the result.

        Args:
            generation_id: The generation ID to poll
            export_format: "pdf" or "pptx"
            max_wait_seconds: Maximum time to wait for completion (default 15 minutes)
            poll_interval: Seconds between poll attempts (default 5 seconds)

        Returns:
            bytes: The generated file
            None: If polling times out or download fails
        """
        headers = {
            "X-API-KEY": self.api_key,
        }

        timeout = aiohttp.ClientTimeout(total=max_wait_seconds)
        elapsed = 0

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Poll for completion
                while elapsed < max_wait_seconds:
                    async with session.get(
                        f"{self.BASE_URL}/generations/{generation_id}",
                        headers=headers
                    ) as response:

                        if response.status != 200:
                            logger.error(f"Gamma poll failed: {response.status}")
                            return None

                        status_data = await response.json()
                        status = status_data.get("status")

                        if status == "completed":
                            # Get download URL - Gamma API returns 'exportUrl' field
                            download_url = status_data.get("exportUrl")

                            if not download_url:
                                logger.error(f"Gamma completed but no exportUrl field. Response: {status_data}")
                                return None

                            # Download the file
                            return await self._download_file(download_url, session)

                        elif status == "failed" or status == "error":
                            error_msg = status_data.get("error", "Unknown error")
                            logger.error(f"Gamma generation failed: {error_msg}")
                            return None

                        elif status in ("pending", "processing", "queued"):
                            # Still processing, wait and retry
                            await asyncio.sleep(poll_interval)
                            elapsed += poll_interval

                        else:
                            logger.warning(f"Unknown Gamma status: {status}")
                            await asyncio.sleep(poll_interval)
                            elapsed += poll_interval

                logger.error(f"Gamma polling timeout after {max_wait_seconds}s")
                return None

        except Exception as e:
            logger.error(f"Gamma polling error: {e}")
            return None

    async def _download_file(self, url: str, session: aiohttp.ClientSession) -> Optional[bytes]:
        """
        Download file from URL.

        Args:
            url: Download URL
            session: Active aiohttp session

        Returns:
            bytes: File contents
            None: If download fails
        """
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Gamma download failed: {response.status}")
                    return None

                return await response.read()

        except Exception as e:
            logger.error(f"Gamma download error: {e}")
            return None

    async def check_credits(self) -> Optional[Dict[str, Any]]:
        """
        Check remaining Gamma API credits.

        Returns:
            Dict with credit info: {"remaining": int, "total": int}
            None: If check fails
        """
        if not self.enabled:
            return None

        headers = {
            "X-API-KEY": self.api_key,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/user/credits",
                    headers=headers
                ) as response:

                    if response.status != 200:
                        return None

                    return await response.json()

        except Exception as e:
            logger.error(f"Gamma credit check failed: {e}")
            return None


# Singleton instance
_gamma_client: Optional[GammaClient] = None


def get_gamma_client() -> GammaClient:
    """Get or create global Gamma client instance."""
    global _gamma_client
    if _gamma_client is None:
        _gamma_client = GammaClient()
    return _gamma_client
