"""Scoring a spine read against the catalog and deciding how much to trust it.

The catalog is built to defeat exact string comparison: it holds two editions of
one work, one work under two titles, distinct works sharing a title, omnibuses
beside their volumes, titles that are substrings of others, and author names in
several forms. Every constant below exists to answer one of those cases, and
each is named and commented rather than inlined, because the thresholds are the
part of this system most likely to need tuning against real photographs.
"""

from dataclasses import dataclass

from rapidfuzz import fuzz

from .catalog import load_catalog
from .normalize import author_last_name, normalize_author, normalize_title, strip_leading_article

# --- Scoring weights -------------------------------------------------------
#
# The title carries most of the signal: it is longer, more distinctive, and
# printed larger on a spine, so it survives a poor photograph better than the
# author does. The author is a corroborating signal rather than an equal one.
TITLE_WEIGHT = 0.75
AUTHOR_WEIGHT = 0.25

# A confidently read author partially rescues a badly read title. A spine caught
# at an angle may yield 'Hary Poter and the Philosphers Ston' with a clean
# 'J.K. Rowling' beside it, and that pairing is better evidence than the title
# score alone suggests.
STRONG_AUTHOR_SIMILARITY = 0.85
AUTHOR_RESCUE_BONUS = 0.05

# The rescue is withheld below this title score, otherwise every book by a
# correctly read author would be lifted towards acceptance regardless of title.
MIN_TITLE_FOR_AUTHOR_RESCUE = 0.40

# An exact surname agreement is treated as near-certain author identity, since
# surnames survive almost every rendering while first names decay to initials.
SURNAME_MATCH_SIMILARITY = 0.90

# --- Penalties -------------------------------------------------------------
#
# 'It' is a catalog entry and also the opening word of 'It Ends with Us'.
# token_sort_ratio already punishes the length difference, but a containment
# check is a second, explicit guard on the case the catalog was built to expose.
SUBSTRING_PENALTY = 0.20

# Containment only looks suspicious when the lengths differ substantially.
# 'The Sign of Four' inside 'The Sign of the Four' is a spelling variant, not a
# different book, and should not be penalised.
SUBSTRING_LENGTH_RATIO = 0.70

# An entry matched only through an alternate title is slightly weaker evidence
# than one matched on its main title. This is what separates the US and UK
# Harry Potter entries, each of which lists the other's title as an alternate.
ALT_TITLE_PENALTY = 0.03

# --- Confidence and routing ------------------------------------------------
#
# The margin between best and second-best is the core idea. Two entries scoring
# 0.90 and 0.89 describe an ambiguous read, not a confident one: the score says
# the text was read cleanly, the margin says it does not identify one book.
# Confidence is the top score scaled by how decisively it won.
AMBIGUITY_MARGIN = 0.10
AMBIGUITY_FLOOR = 0.60

# Below this the best candidate is not a plausible reading of the spine at all,
# and offering it for confirmation would be noise rather than help.
MIN_PLAUSIBLE_SCORE = 0.45

# Above this a match is added without asking. Deliberately high: the cost of a
# wrong silent addition is a corrupted library the user did not consent to,
# while the cost of an unnecessary question is one tap.
AUTO_ACCEPT_CONFIDENCE = 0.85

# How many alternatives the review screen is offered.
CANDIDATES_RETURNED = 3

AUTO = 'auto'
REVIEW = 'review'
UNMATCHED = 'unmatched'


@dataclass(frozen=True)
class Candidate:
    entry: object
    score: float
    title_similarity: float
    author_similarity: float


@dataclass(frozen=True)
class MatchResult:
    """The outcome for one spine, including why it landed where it did.

    `reasons` exists for the review screen. Asking someone to confirm a match
    without telling them what the doubt is makes the question unanswerable, so
    the conditions that lowered confidence are recorded as they are applied.
    """

    status: str
    confidence: float
    candidates: tuple
    reasons: tuple
    read_title: str
    read_author: str

    @property
    def best(self):
        return self.candidates[0] if self.candidates else None


def _title_similarity(read_norm, entry):
    """Best similarity between the read title and any recorded title form.

    token_sort_ratio is deliberate. token_set_ratio would score 'It' against
    'It Ends with Us' at 100, because the read's tokens are a subset of the
    candidate's; token_sort_ratio compares the full sorted strings and so keeps
    the length difference in play, scoring the same pair near 30.
    """
    best = 0.0
    matched_via_alt = False

    for form in entry.norm_primary_titles:
        best = max(best, fuzz.token_sort_ratio(read_norm, form) / 100)

    for form in entry.norm_alt_titles:
        score = fuzz.token_sort_ratio(read_norm, form) / 100
        if score > best:
            best = score
            matched_via_alt = True

    return best, matched_via_alt


def _author_similarity(read_norm, read_surname, entry):
    """Best similarity between the read author and any recorded name form."""
    if not read_norm:
        return None

    best = max(
        (fuzz.token_sort_ratio(read_norm, form) / 100 for form in entry.norm_authors),
        default=0.0,
    )

    if read_surname and read_surname in entry.norm_surnames:
        best = max(best, SURNAME_MATCH_SIMILARITY)

    return best


def _substring_penalty(read_norm, entry):
    """Penalise a match where one title merely contains the other.

    Applies in both directions: reading 'It' against the entry 'It Ends with
    Us', and reading 'It Ends with Us' against the entry 'It', are the same
    error seen from opposite sides.
    """
    for form in entry.all_norm_titles:
        if not form or not read_norm or form == read_norm:
            continue

        shorter, longer = sorted((read_norm, form), key=len)
        if shorter in longer and len(shorter) / len(longer) < SUBSTRING_LENGTH_RATIO:
            return SUBSTRING_PENALTY

    return 0.0


def _score_entry(read_title_norm, read_author_norm, read_surname, entry):
    title_sim, via_alt = _title_similarity(read_title_norm, entry)
    author_sim = _author_similarity(read_author_norm, read_surname, entry)

    if author_sim is None:
        # No author was read. Scoring on title alone is preferable to treating
        # the missing author as disagreement, which would penalise every entry
        # equally and simply depress all scores.
        score = title_sim
    else:
        score = TITLE_WEIGHT * title_sim + AUTHOR_WEIGHT * author_sim
        if author_sim >= STRONG_AUTHOR_SIMILARITY and title_sim >= MIN_TITLE_FOR_AUTHOR_RESCUE:
            score += AUTHOR_RESCUE_BONUS

    if via_alt:
        score -= ALT_TITLE_PENALTY

    score -= _substring_penalty(read_title_norm, entry)

    return Candidate(
        entry=entry,
        score=max(0.0, min(1.0, score)),
        title_similarity=title_sim,
        author_similarity=0.0 if author_sim is None else author_sim,
    )


def _build_reasons(candidates, read_author, margin):
    reasons = []

    if not read_author:
        reasons.append('No author was read from this spine, so only the title was compared.')

    if len(candidates) > 1 and margin < AMBIGUITY_MARGIN:
        runner_up = candidates[1].entry
        reasons.append(
            f'{runner_up.display_title} by {runner_up.author} scored almost as highly '
            f'(within {margin:.2f}).'
        )

    best = candidates[0]
    if best.title_similarity < 0.80:
        reasons.append('The title read from the spine differs noticeably from the catalog entry.')

    if read_author and best.author_similarity < 0.50:
        reasons.append('The author read from the spine does not match this entry.')

    return tuple(reasons)


def match_spine(title, author=None, catalog=None):
    """Match one spine read against the catalog and decide how to route it.

    Every entry is scored rather than pre-filtered. At catalog sizes in the low
    hundreds an exhaustive pass costs well under a millisecond, and a blocking
    index would risk discarding the badly read titles that most need matching.
    """
    entries = catalog if catalog is not None else load_catalog()

    read_title_norm = normalize_title(title or '')
    read_author_norm = normalize_author(author or '')
    read_surname = author_last_name(author or '')

    if not read_title_norm and not read_author_norm:
        # Nothing legible came back for this spine. It is reported rather than
        # dropped, so the user sees that a book was detected but not read.
        return MatchResult(
            status=UNMATCHED,
            confidence=0.0,
            candidates=(),
            reasons=('Nothing readable was returned for this spine.',),
            read_title=title or '',
            read_author=author or '',
        )

    scored = [
        _score_entry(read_title_norm, read_author_norm, read_surname, entry) for entry in entries
    ]

    # An article-stripped retry catches spines that print 'Road, The' or drop a
    # leading article the catalog records.
    stripped = strip_leading_article(read_title_norm)
    if stripped != read_title_norm:
        alternate = [
            _score_entry(stripped, read_author_norm, read_surname, entry) for entry in entries
        ]
        scored = [max(a, b, key=lambda c: c.score) for a, b in zip(scored, alternate)]

    scored.sort(key=lambda c: c.score, reverse=True)
    candidates = tuple(scored[:CANDIDATES_RETURNED])
    best = candidates[0]

    if best.score < MIN_PLAUSIBLE_SCORE:
        return MatchResult(
            status=UNMATCHED,
            confidence=best.score,
            candidates=(),
            reasons=('No catalog entry resembles this spine closely enough to suggest.',),
            read_title=title or '',
            read_author=author or '',
        )

    runner_up = candidates[1].score if len(candidates) > 1 else 0.0
    margin = best.score - runner_up

    # A decisive win keeps the full score; a dead heat is scaled to the floor.
    decisiveness = min(1.0, margin / AMBIGUITY_MARGIN)
    confidence = best.score * (AMBIGUITY_FLOOR + (1 - AMBIGUITY_FLOOR) * decisiveness)

    reasons = _build_reasons(candidates, read_author_norm, margin)
    status = AUTO if confidence >= AUTO_ACCEPT_CONFIDENCE else REVIEW

    return MatchResult(
        status=status,
        confidence=round(confidence, 3),
        candidates=candidates,
        reasons=reasons,
        read_title=title or '',
        read_author=author or '',
    )
