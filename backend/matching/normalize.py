"""Text normalisation shared by the catalog loader and the matcher.

Spine reads arrive with inconsistent casing, accents, punctuation and name
order. Reducing both sides to the same form removes differences that carry no
information, so the similarity scores that follow reflect genuine disagreement
rather than typography.
"""

import re

from unidecode import unidecode

_AMPERSAND = re.compile(r'\s*&\s*')
_PUNCTUATION = re.compile(r'[^a-z0-9\s]')
_WHITESPACE = re.compile(r'\s+')
_LEADING_ARTICLE = re.compile(r'^(the|a|an)\s+')


def normalize_title(value):
    """Reduce a title to lowercase alphanumerics and single spaces.

    unidecode folds accented and transliterated characters onto ASCII, so
    'Cien anos' and 'Cien años' converge. '&' becomes 'and' before punctuation
    is stripped, otherwise 'Angels & Demons' would lose the conjunction
    entirely and score worse than it should against 'Angels and Demons'.
    """
    if not value:
        return ''

    text = unidecode(value).lower()
    text = _AMPERSAND.sub(' and ', text)
    text = _PUNCTUATION.sub(' ', text)
    return _WHITESPACE.sub(' ', text).strip()


def strip_leading_article(value):
    """Drop a leading 'the', 'a' or 'an'.

    Spines frequently omit or add a leading article relative to the catalog
    ('Joy of Cooking' shelved as 'The Joy of Cooking'). Comparing both the
    full and article-stripped forms keeps that from costing similarity.
    """
    return _LEADING_ARTICLE.sub('', value, count=1)


def normalize_author(value):
    """Reduce an author name to a canonical 'firstname lastname' word order.

    Catalog and spine disagree on order ('Tolkien, J. R. R.' against
    'J.R.R. Tolkien') and on whether initials carry periods. Swapping on the
    comma and stripping punctuation collapses both forms to 'j r r tolkien'.
    """
    if not value:
        return ''

    text = unidecode(value).strip()

    # A single comma nearly always marks 'Lastname, Firstname' in bibliographic
    # data. Suffixes such as 'Jr.' produce a second comma, which this ignores
    # rather than mis-swapping.
    if text.count(',') == 1:
        last, first = text.split(',')
        text = f'{first.strip()} {last.strip()}'

    text = text.lower()
    text = _PUNCTUATION.sub(' ', text)
    return _WHITESPACE.sub(' ', text).strip()


def author_last_name(value):
    """Extract the surname, which is the most stable part of an author name.

    First names degrade to initials and initials are frequently dropped
    altogether, but the surname survives almost every rendering. An exact
    surname agreement is therefore treated as strong evidence even when the
    rest of the name disagrees.

    Compound surnames such as 'Garcia Marquez' are not split, because taking
    only the final token would reduce them to 'marquez' and lose the match
    against catalogues that record the full compound.
    """
    if not value:
        return ''

    text = unidecode(value).strip()

    if text.count(',') == 1:
        return normalize_author(text.split(',')[0])

    normalized = normalize_author(text)
    if not normalized:
        return ''

    # Trailing token is the surname once the name is in natural order. Initials
    # are single characters, so anything longer is taken as the surname start.
    tokens = normalized.split()
    surname_tokens = [t for t in tokens if len(t) > 1]
    return surname_tokens[-1] if surname_tokens else tokens[-1]
