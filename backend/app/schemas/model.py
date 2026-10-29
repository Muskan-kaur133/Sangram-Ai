"""AI Model and Archetype Catalog Schemas.

Defines the 6 combatant profiles and 6 cognitive archetypes recognized in Sangram AI.
Matches frontend src/data/models.js and src/data/archetypes.js.
"""

from typing import List, Optional
from pydantic import Field

from app.schemas.common import BaseSchema


class ModelAccent(BaseSchema):
    """CSS accent colors for fighter visualization."""

    color: str = Field(..., description="Primary hex accent color")
    soft: str = Field(..., description="Low-opacity rgba background accent")
    line: str = Field(..., description="Mid-opacity rgba border accent")


class ModelProfile(BaseSchema):
    """Fighter model profile."""

    id: str = Field(..., description="Catalog model identifier (chatgpt, gemini, claude, llama, mistral, grok)")
    name: str = Field(..., description="Display model title")
    provider: str = Field(..., description="Provider organization (OpenAI, Google, Anthropic, Meta, Mistral AI, xAI)")
    modelLabel: str = Field(..., description="Display generation label (e.g. GPT-5, Claude Sonnet 4.5)")
    apiModel: Optional[str] = Field(None, description="Backend provider API identifier (mapped by Developer 3)")
    desc: str = Field(..., description="Short cognitive summary")
    accent: ModelAccent = Field(..., description="Design system color tokens")
    is_available: bool = Field(True, description="Whether this model is active in the provider gateway")


class ArchetypeProfile(BaseSchema):
    """Cognitive persona archetype that modulates model argumentation style."""

    id: str = Field(..., description="Archetype identifier (logician, visionary, pragmatist, skeptic, synthesizer, provocateur)")
    name: str = Field(..., description="Full descriptive title")
    shortName: str = Field(..., description="Abbreviated title for pills and badges")
    tag: str = Field(..., description="Philosophical category tag")
    motto: str = Field(..., description="Guiding dialectic axiom")
    description: str = Field(..., description="Detailed cognitive explanation")
    traits: List[str] = Field(..., description="Key reasoning traits")
    debateStyle: str = Field(..., description="Arena argument methodology")
    accent: ModelAccent = Field(..., description="Design system color tokens")
