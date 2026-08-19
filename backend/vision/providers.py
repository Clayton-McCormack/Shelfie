"""Replaceable sources of title and author reads."""

import base64
import os
from typing import Protocol

import httpx
from pydantic import ValidationError

from .contact_sheet import ContactSheet
from .schemas import ProviderReadResult, ProviderUsage, SpineRead, SpineReadResponse


GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
REQUEST_TIMEOUT_SECONDS = 30
# Gemini 3.1 Flash-Lite paid-tier rates, USD per one million tokens. These
# values make the README estimate reproducible from API-reported token usage.
GEMINI_INPUT_COST_PER_MILLION = 0.25
GEMINI_OUTPUT_COST_PER_MILLION = 1.50


class VisionProviderError(RuntimeError):
    """A hosted vision provider could not produce validated spine reads."""


class VisionProvider(Protocol):
    """Produces one read for each spine the provider can identify."""

    def read_contact_sheets(self, contact_sheets: tuple[ContactSheet, ...]) -> ProviderReadResult:
        ...


class FakeProvider:
    """Deterministic reads used while the upload and review path is developed.

    The uploaded file is accepted by the endpoint but not inspected here. These
    four cases deliberately cover automatic acceptance, an imperfect read,
    title ambiguity, and a book absent from the catalog.
    """

    def read_contact_sheets(self, contact_sheets: tuple[ContactSheet, ...]) -> ProviderReadResult:
        return ProviderReadResult(reads=[
            SpineRead(spine_index=1, title='The Great Gatsby', author='F. Scott Fitzgerald'),
            SpineRead(spine_index=2, title='Hary Poter and the Philosphers Ston', author='J.K. Rowling'),
            SpineRead(spine_index=3, title='Inferno'),
            SpineRead(spine_index=4, title='Advanced Marine Boiler Maintenance', author='K. Oduya'),
        ])


class GeminiProvider:
    """Reads numbered contact sheets through the Gemini Developer API."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def read_contact_sheets(self, contact_sheets: tuple[ContactSheet, ...]) -> ProviderReadResult:
        reads = []
        total_usage = ProviderUsage()
        for sheet in contact_sheets:
            sheet_result = self._read_sheet(sheet)
            reads.extend(sheet_result.reads)
            total_usage.input_tokens += sheet_result.usage.input_tokens
            total_usage.output_tokens += sheet_result.usage.output_tokens
        return ProviderReadResult(reads=reads, usage=total_usage)

    def _read_sheet(self, sheet: ContactSheet) -> ProviderReadResult:
        response_schema = SpineReadResponse.model_json_schema()
        prompt = (
            'This is a numbered sheet of book-spine crops. Read only the visible title and author '
            'for each numbered crop. Return each crop number as spine_index. Do not guess. Use an '
            'empty string when a title or author is unreadable. Return only crop numbers present in '
            f'this sheet: {list(sheet.indices)}.'
        )
        payload = {
            'contents': [{
                'role': 'user',
                'parts': [
                    {'text': prompt},
                    {'inline_data': {
                        'mime_type': 'image/jpeg',
                        'data': base64.b64encode(sheet.image_bytes).decode('ascii'),
                    }},
                ],
            }],
            'generationConfig': {
                'response_mime_type': 'application/json',
                'response_json_schema': response_schema,
                'temperature': 0,
            },
        }
        try:
            response = httpx.post(
                GEMINI_API_URL.format(model=self.model),
                params={'key': self.api_key},
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            body = response.json()
            text = body['candidates'][0]['content']['parts'][0]['text']
            parsed = SpineReadResponse.model_validate_json(text)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, ValidationError) as error:
            raise VisionProviderError('Gemini did not return usable book-spine data.') from error

        allowed_indices = set(sheet.indices)
        usage = body.get('usageMetadata', {})
        return ProviderReadResult(
            reads=[read for read in parsed.reads if read.spine_index in allowed_indices],
            usage=ProviderUsage(
                input_tokens=usage.get('promptTokenCount', 0),
                output_tokens=usage.get('candidatesTokenCount', 0),
            ),
        )


def estimate_gemini_cost_usd(usage: ProviderUsage) -> float:
    """Estimate paid-tier cost from Gemini's token counters."""
    return (
        usage.input_tokens * GEMINI_INPUT_COST_PER_MILLION
        + usage.output_tokens * GEMINI_OUTPUT_COST_PER_MILLION
    ) / 1_000_000


def configured_provider() -> tuple[str, VisionProvider]:
    """Select the provider without making credentials mandatory for local runs."""
    provider_name = os.getenv('VISION_PROVIDER', 'fake').lower()
    if provider_name != 'gemini':
        return 'fake', FakeProvider()

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise VisionProviderError('Gemini is selected but GEMINI_API_KEY is not configured.')
    return 'gemini', GeminiProvider(
        api_key=api_key,
        model=os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite'),
    )
