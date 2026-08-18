"""Loading of catalog.csv into immutable entries with normalised forms attached.

Normalisation happens once at load rather than per comparison. A single spine
read is scored against every catalog entry, so recomputing normalised strings
inside the scoring loop would repeat the same work thousands of times per photo.
"""

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .normalize import author_last_name, normalize_author, normalize_title, strip_leading_article

# catalog.csv lives at the repository root so it is visible as a deliverable
# rather than buried inside the backend package.
CATALOG_PATH = Path(__file__).resolve().parents[2] / 'catalog.csv'

# Multi-valued cells use '|' because titles and author names both contain
# commas, which the CSV format has already claimed as its own delimiter.
MULTI_VALUE_SEPARATOR = '|'


@dataclass(frozen=True)
class CatalogEntry:
    """One canonical book, with every string the matcher compares against."""

    id: str
    title: str
    alt_titles: tuple
    author: str
    author_variants: tuple
    year: str
    edition: str
    series: str
    volume_of: str
    notes: str

    # Primary and alternate title forms are kept apart so the matcher can prefer
    # an entry whose main title matches over one that matches only via a
    # synonym. Both US and UK Harry Potter entries list the other's title as an
    # alternate, so without that distinction they score identically.
    norm_primary_titles: tuple
    norm_alt_titles: tuple

    norm_authors: tuple
    norm_surnames: frozenset

    @property
    def all_norm_titles(self):
        return self.norm_primary_titles + self.norm_alt_titles

    @property
    def display_title(self):
        """Title plus the detail that distinguishes near-identical entries.

        Two editions of The Hobbit are indistinguishable by title alone, so a
        review screen listing bare titles would offer the user a choice whose
        options look identical.
        """
        if self.edition:
            return f'{self.title} ({self.edition})'
        if self.year:
            return f'{self.title} ({self.year})'
        return self.title


def _split_multi(value):
    return tuple(part.strip() for part in value.split(MULTI_VALUE_SEPARATOR) if part.strip())


def _title_forms(titles):
    """Normalise titles, keeping both the full and article-stripped variants.

    Spines add and drop leading articles freely ('Joy of Cooking' shelved as
    'The Joy of Cooking'), and that difference should not cost similarity.
    """
    forms = set()
    for title in titles:
        normalized = normalize_title(title)
        if normalized:
            forms.add(normalized)
            forms.add(strip_leading_article(normalized))
    return tuple(sorted(forms))


def _build_entry(row):
    alt_titles = _split_multi(row['alt_titles'])
    primary_forms = _title_forms([row['title']])
    alt_forms = tuple(f for f in _title_forms(alt_titles) if f not in primary_forms)

    authors = (row['author'],) + _split_multi(row['author_variants'])
    norm_authors = {normalize_author(a) for a in authors if normalize_author(a)}
    surnames = {author_last_name(a) for a in authors if author_last_name(a)}

    return CatalogEntry(
        id=row['id'],
        title=row['title'],
        alt_titles=alt_titles,
        author=row['author'],
        author_variants=_split_multi(row['author_variants']),
        year=row['year'],
        edition=row['edition'],
        series=row['series'],
        volume_of=row['volume_of'],
        notes=row['notes'],
        norm_primary_titles=primary_forms,
        norm_alt_titles=alt_forms,
        norm_authors=tuple(sorted(norm_authors)),
        norm_surnames=frozenset(surnames),
    )


@lru_cache(maxsize=None)
def load_catalog(path=None):
    """Read the catalog once per process and reuse it.

    The file is static for the lifetime of the server and small enough that the
    whole thing sits comfortably in memory, so caching avoids a disk read and a
    full re-normalisation on every upload.
    """
    source = Path(path) if path else CATALOG_PATH

    with open(source, newline='', encoding='utf-8') as handle:
        return tuple(_build_entry(row) for row in csv.DictReader(handle))
