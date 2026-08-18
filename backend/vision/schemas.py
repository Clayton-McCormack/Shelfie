"""Validated data exchanged between a vision provider and the application."""

from pydantic import BaseModel, Field


class SpineRead(BaseModel):
    """Text read from one book spine."""

    title: str = Field(default='')
    author: str = Field(default='')
