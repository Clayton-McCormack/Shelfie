"""Replaceable sources of title and author reads."""

from typing import Protocol

from .contact_sheet import ContactSheet
from .schemas import SpineRead


class VisionProvider(Protocol):
    """Produces one read for each spine the provider can identify."""

    def read_contact_sheets(self, contact_sheets: tuple[ContactSheet, ...]) -> list[SpineRead]:
        ...


class FakeProvider:
    """Deterministic reads used while the upload and review path is developed.

    The uploaded file is accepted by the endpoint but not inspected here. These
    four cases deliberately cover automatic acceptance, an imperfect read,
    title ambiguity, and a book absent from the catalog.
    """

    def read_contact_sheets(self, contact_sheets: tuple[ContactSheet, ...]) -> list[SpineRead]:
        return [
            SpineRead(title='The Great Gatsby', author='F. Scott Fitzgerald'),
            SpineRead(title='Hary Poter and the Philosphers Ston', author='J.K. Rowling'),
            SpineRead(title='Inferno'),
            SpineRead(title='Advanced Marine Boiler Maintenance', author='K. Oduya'),
        ]
