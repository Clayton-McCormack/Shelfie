"""Validated data exchanged between a vision provider and the application."""

from pydantic import BaseModel, Field, field_validator


class SpineRead(BaseModel):
    """Text read from one book spine."""

    spine_index: int = Field(ge=1)
    title: str = Field(default='')
    author: str = Field(default='')

    @field_validator('title', 'author', mode='before')
    @classmethod
    def coerce_text(cls, value):
        return '' if value is None else str(value).strip()


class SpineReadResponse(BaseModel):
    """The schema requested from a hosted provider for one contact sheet."""

    reads: list[SpineRead] = Field(default_factory=list)


class ProviderUsage(BaseModel):
    """Token counts reported by one hosted-model run."""

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class ProviderReadResult(BaseModel):
    """Validated reads and aggregate usage from all contact-sheet batches."""

    reads: list[SpineRead] = Field(default_factory=list)
    usage: ProviderUsage = Field(default_factory=ProviderUsage)
